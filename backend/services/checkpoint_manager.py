"""
Checkpoint Management Service

Centralizes checkpoint lifecycle management, eliminating duplication
across checkpoint nodes.
"""

import logging
import uuid
import json
from datetime import datetime
from typing import Dict, Any, Optional, List
from langgraph.types import interrupt

from backend.db.connection import db

logger = logging.getLogger(__name__)


class CheckpointManager:
    """
    Manages checkpoint lifecycle: creation, presentation, and resolution.

    Eliminates duplication across checkpoint nodes by providing a unified
    interface for checkpoint handling.
    """

    async def create_checkpoint(
        self,
        workflow_id: str,
        checkpoint_number: int,
        step_name: str,
        editable_content: str,
        instructions: str,
        actions: Dict[str, Any],
        agent_outputs: Optional[List[Dict]] = None,
        iteration: int = 0,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a checkpoint and pause workflow execution.

        Args:
            workflow_id: The workflow ID
            checkpoint_number: Sequential checkpoint number
            step_name: Name of the checkpoint step
            editable_content: Content that user can edit
            instructions: Instructions shown to user
            actions: Available actions (primary and secondary)
            agent_outputs: Optional list of agent outputs
            iteration: Current iteration number
            context: Optional additional context

        Returns:
            Checkpoint data dictionary
        """
        checkpoint_id = str(uuid.uuid4())
        checkpoint_data = {
            "checkpoint_id": checkpoint_id,
            "checkpoint_number": checkpoint_number,
            "step_name": step_name,
            "workflow_id": workflow_id,
            "iteration": iteration,
            "agent_outputs": agent_outputs or [],
            "instructions": instructions,
            "actions": actions,
            "editable_content": editable_content,
            "context": context or {}
        }

        logger.info(
            f"Creating checkpoint {checkpoint_id} for workflow {workflow_id}, "
            f"step: {step_name}, number: {checkpoint_number}"
        )

        # Save to database for audit trail
        try:
            await self._save_checkpoint_to_db(checkpoint_data)
            logger.debug(f"Checkpoint {checkpoint_id} saved to database")
        except Exception as e:
            logger.error(f"Failed to save checkpoint {checkpoint_id} to database: {e}")
            # Don't fail checkpoint creation if DB save fails

        # Pause workflow execution (LangGraph interrupt)
        logger.debug(f"Interrupting workflow for checkpoint {checkpoint_id}")
        human_input = interrupt(checkpoint_data)

        logger.info(f"Checkpoint {checkpoint_id} resolved with action: {human_input.get('action')}")

        # Save resolution to database
        try:
            await self._save_checkpoint_resolution(
                checkpoint_id=checkpoint_id,
                action=human_input.get("action", "unknown"),
                edited_content=human_input.get("edited_content"),
                user_notes=human_input.get("user_notes")
            )
            logger.debug(f"Checkpoint {checkpoint_id} resolution saved to database")
        except Exception as e:
            logger.error(f"Failed to save checkpoint resolution for {checkpoint_id}: {e}")

        return human_input

    async def create_plan_review_checkpoint(
        self,
        state: Dict[str, Any],
        plan: str
    ) -> Dict[str, Any]:
        """
        Create a checkpoint for plan review.

        Args:
            state: Current workflow state
            plan: The plan to review

        Returns:
            State updates based on user action
        """
        from langchain_core.messages import HumanMessage

        human_input = await self.create_checkpoint(
            workflow_id=state["workflow_id"],
            checkpoint_number=state["checkpoint_number"],
            step_name="plan_ready_for_review",
            editable_content=plan,
            instructions=(
                "The PLANNING AGENT has created a plan. "
                "Review and edit if needed before sending to REVIEW AGENTS."
            ),
            actions={
                "primary": "send_to_reviewers",
                "secondary": ["edit_and_continue", "cancel"]
            },
            agent_outputs=[{
                "agent_name": "planning_agent",
                "agent_type": "planning",
                "output": plan,
                "timestamp": datetime.now().isoformat()
            }],
            iteration=state.get("iteration_count", 0)
        )

        # Process user decision
        action = human_input.get("action", "send_to_reviewers")
        edited_plan = human_input.get("edited_content", plan)

        if action == "send_to_reviewers":
            return {
                "user_edits": edited_plan,
                "status": "ready_for_review",
                "next_step": "review_agents",
                "messages": [HumanMessage(
                    content="[User approved plan for review]",
                    name="user"
                )]
            }
        elif action == "edit_and_continue":
            return {
                "user_edits": edited_plan,
                "status": "editing_reviewer_prompt",
                "next_step": "edit_reviewer_prompt",
                "messages": [HumanMessage(
                    content="[User wants to edit full reviewer prompt]",
                    name="user"
                )]
            }
        else:  # cancel
            return {
                "status": "cancelled",
                "next_step": "end",
                "messages": [HumanMessage(
                    content="[User cancelled workflow]",
                    name="user"
                )]
            }

    async def create_prompt_edit_checkpoint(
        self,
        state: Dict[str, Any],
        prompt: str,
        step_name: str,
        primary_action: str,
        instructions: str
    ) -> Dict[str, Any]:
        """
        Create a checkpoint for editing prompts sent to agents.

        Args:
            state: Current workflow state
            prompt: The default prompt to edit
            step_name: Checkpoint step name
            primary_action: Primary action name
            instructions: Instructions for the user

        Returns:
            State updates based on user action
        """
        from langchain_core.messages import HumanMessage

        human_input = await self.create_checkpoint(
            workflow_id=state["workflow_id"],
            checkpoint_number=state["checkpoint_number"],
            step_name=step_name,
            editable_content=prompt,
            instructions=instructions,
            actions={
                "primary": primary_action,
                "secondary": ["cancel"]
            },
            iteration=state.get("iteration_count", 0)
        )

        action = human_input.get("action", primary_action)
        edited_prompt = human_input.get("edited_content", prompt)

        if action == "cancel":
            return {
                "status": "cancelled",
                "next_step": "end",
                "messages": [HumanMessage(
                    content="[User cancelled workflow]",
                    name="user"
                )]
            }

        # Return appropriate state based on step
        if step_name == "edit_reviewer_prompt":
            return {
                "reviewer_prompt": edited_prompt,
                "status": "ready_for_review",
                "messages": [HumanMessage(
                    content="[User edited reviewer prompt and approved for review]",
                    name="user"
                )],
                "checkpoint_number": state["checkpoint_number"] + 1
            }
        elif step_name == "edit_planner_prompt":
            return {
                "planner_prompt": edited_prompt,
                "status": "revision_needed",
                "iteration_count": state.get("iteration_count", 0) + 1,
                "messages": [HumanMessage(
                    content="[User edited planner prompt and requested revision]",
                    name="user"
                )],
                "checkpoint_number": state["checkpoint_number"] + 1
            }

        return {}

    async def create_review_consolidation_checkpoint(
        self,
        state: Dict[str, Any],
        consolidated_feedback: str
    ) -> Dict[str, Any]:
        """
        Create a checkpoint for consolidating review feedback.

        Args:
            state: Current workflow state
            consolidated_feedback: The consolidated feedback

        Returns:
            State updates based on user action
        """
        from langchain_core.messages import HumanMessage

        human_input = await self.create_checkpoint(
            workflow_id=state["workflow_id"],
            checkpoint_number=state["checkpoint_number"],
            step_name="reviews_ready_for_consolidation",
            editable_content=consolidated_feedback,
            instructions=(
                "Review feedback from all REVIEW AGENTS has been consolidated. "
                "Edit if needed, then choose whether to revise the plan or complete the workflow."
            ),
            actions={
                "primary": "request_revision",
                "secondary": ["edit_prompt_and_revise", "approve_plan", "cancel"]
            },
            iteration=state.get("iteration_count", 0)
        )

        action = human_input.get("action", "request_revision")
        edited_feedback = human_input.get("edited_content", consolidated_feedback)

        if action == "request_revision":
            return {
                "consolidated_feedback": edited_feedback,
                "status": "revision_needed",
                "next_step": "planning_agent",
                "messages": [HumanMessage(
                    content="[User requested plan revision based on reviews]",
                    name="user"
                )]
            }
        elif action == "edit_prompt_and_revise":
            return {
                "consolidated_feedback": edited_feedback,
                "status": "editing_planner_prompt",
                "next_step": "edit_planner_prompt",
                "messages": [HumanMessage(
                    content="[User wants to edit planner prompt before revision]",
                    name="user"
                )]
            }
        elif action == "approve_plan":
            return {
                "status": "completed",
                "next_step": "end",
                "messages": [HumanMessage(
                    content="[User approved plan without revision]",
                    name="user"
                )]
            }
        else:  # cancel
            return {
                "status": "cancelled",
                "next_step": "end",
                "messages": [HumanMessage(
                    content="[User cancelled workflow]",
                    name="user"
                )]
            }

    async def _save_checkpoint_to_db(self, checkpoint_data: Dict[str, Any]) -> None:
        """Save checkpoint creation to database"""
        async with db.get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO user_checkpoints (
                    id, workflow_id, checkpoint_number, step_name,
                    agent_outputs, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    checkpoint_data.get("checkpoint_id"),
                    checkpoint_data.get("workflow_id"),
                    checkpoint_data.get("checkpoint_number", 0),
                    checkpoint_data.get("step_name", "unknown"),
                    json.dumps(checkpoint_data.get("agent_outputs", [])),
                    "pending",
                    datetime.now().isoformat()
                )
            )
            await conn.commit()

    async def _save_checkpoint_resolution(
        self,
        checkpoint_id: str,
        action: str,
        edited_content: Optional[str] = None,
        user_notes: Optional[str] = None
    ) -> None:
        """Save checkpoint resolution to database"""
        # Determine status based on action
        status_map = {
            "send_to_reviewers": "approved",
            "send_to_planner_for_revision": "approved",
            "request_revision": "approved",
            "approve_plan": "approved",
            "approve": "approved",
            "edit_and_continue": "edited",
            "edit_prompt_and_revise": "edited",
            "cancel": "rejected"
        }
        status = status_map.get(action, "approved")

        async with db.get_connection() as conn:
            await conn.execute(
                """
                UPDATE user_checkpoints
                SET user_edited_content = ?,
                    user_notes = ?,
                    status = ?,
                    resolved_at = ?
                WHERE id = ?
                """,
                (
                    edited_content,
                    user_notes,
                    status,
                    datetime.now().isoformat(),
                    checkpoint_id
                )
            )
            await conn.commit()
