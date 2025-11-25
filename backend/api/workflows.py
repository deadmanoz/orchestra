from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Optional
import uuid
from datetime import datetime
import json
import aiosqlite
import os
from pathlib import Path

from backend.models.workflow import (
    WorkflowCreate, WorkflowResponse, WorkflowStateSnapshot, WorkflowStatus
)
from backend.workflows.plan_review import PlanReviewWorkflow
from backend.agents.factory import agent_factory
from backend.db.connection import db
from backend.settings import settings
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from backend.services.workflow_manager import WorkflowStatusManager
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/workflows", tags=["workflows"])

# In-memory store for active workflows (replace with Redis in production)
active_workflows = {}

# Initialize Workflow Status Manager
status_manager = WorkflowStatusManager(active_workflows)

# === Legacy Checkpoint Persistence Functions ===
# TODO: Phase 4 - Move these to CheckpointManager
async def save_checkpoint_created(checkpoint_data: dict) -> None:
    """
    Save checkpoint creation to database for audit trail.
    Uses INSERT OR IGNORE to handle duplicate checkpoint IDs from polling.

    Args:
        checkpoint_data: Checkpoint data from LangGraph interrupt
    """
    async with db.get_connection() as conn:
        await conn.execute(
            """
            INSERT OR IGNORE INTO user_checkpoints (
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

async def save_checkpoint_resolution(
    checkpoint_id: str,
    action: str,
    edited_content: Optional[str] = None,
    user_notes: Optional[str] = None
) -> None:
    """
    Save checkpoint resolution to database for audit trail.

    Args:
        checkpoint_id: The checkpoint ID
        action: The action taken (e.g., 'send_to_reviewers', 'edit_and_continue')
        edited_content: User's edited content if any
        user_notes: User's notes if any
    """
    # Determine status based on action
    # NOTE: Keep this in sync with checkpoint_manager.py status_map
    status_map = {
        "send_to_reviewers": "approved",
        "send_to_planner_for_revision": "approved",
        "request_revision": "approved",
        "approve_plan": "approved",
        "approve": "approved",
        "edit_and_continue": "edited",
        "edit_prompt_and_revise": "edited",
        "edit_full_prompt": "edited",
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

def validate_workspace_path(workspace_path: Optional[str]) -> str:
    """
    Validate and resolve workspace path.

    If no path provided, use the working_directory from settings.
    Creates the directory if it doesn't exist.

    Returns:
        Absolute path to workspace directory
    """
    # Use default workspace if none provided
    if not workspace_path:
        workspace_path = settings.working_directory

    # Resolve to absolute path
    resolved_path = Path(workspace_path).resolve()

    # Create directory if it doesn't exist
    if not resolved_path.exists():
        logger.info(f"Creating workspace directory: {resolved_path}")
        try:
            resolved_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create workspace directory {workspace_path}: {str(e)}"
            )

    # Check if it's a directory
    if not resolved_path.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"Workspace path is not a directory: {workspace_path}"
        )

    # Check if writable
    if not os.access(resolved_path, os.W_OK):
        raise HTTPException(
            status_code=403,
            detail=f"Workspace directory is not writable: {resolved_path}"
        )

    # Convert to string
    return str(resolved_path)

@router.post("", response_model=WorkflowResponse)
async def create_workflow(
    workflow_create: WorkflowCreate,
    background_tasks: BackgroundTasks
):
    """Create and start a new workflow"""
    workflow_id = f"wf-{uuid.uuid4().hex[:12]}"

    # Validate workspace path
    workspace_path = validate_workspace_path(workflow_create.workspace_path)

    # Save to database
    async with db.get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO workflows (id, name, type, status, workspace_path, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                workflow_id,
                workflow_create.name,
                workflow_create.type.value,
                WorkflowStatus.RUNNING.value,
                workspace_path,
                datetime.now().isoformat(),
                datetime.now().isoformat()
            )
        )
        await conn.commit()

    # Create workflow instance
    if workflow_create.type.value == "plan_review":
        workflow = PlanReviewWorkflow(agent_factory, workspace_path=workspace_path)
        await workflow.setup()  # Initialize async checkpointer
        compiled_workflow = workflow.compile()
    else:
        raise HTTPException(status_code=400, detail="Unsupported workflow type")

    # Store in active workflows
    active_workflows[workflow_id] = {
        "compiled": compiled_workflow,
        "instance": workflow,
        "status": WorkflowStatus.RUNNING.value
    }

    # Start workflow execution in background
    background_tasks.add_task(
        execute_workflow,
        workflow_id,
        compiled_workflow,
        workflow_create.initial_prompt
    )

    return WorkflowResponse(
        id=workflow_id,
        name=workflow_create.name,
        type=workflow_create.type.value,
        status=WorkflowStatus.RUNNING.value,
        workspace_path=workspace_path,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )

async def execute_workflow(
    workflow_id: str,
    compiled_workflow,
    initial_prompt: str
):
    """Execute workflow until first checkpoint"""
    try:
        config = {"configurable": {"thread_id": workflow_id}}

        initial_state = {
            "workflow_id": workflow_id,
            "messages": [HumanMessage(content=initial_prompt)],
            "iteration_count": 0,
            "checkpoint_number": 0,
            "status": "starting"
        }

        # This will run until first interrupt() - use async API
        result = await compiled_workflow.ainvoke(
            initial_state,
            config
        )

        # Mark workflow as awaiting checkpoint (atomic update with validation)
        await status_manager.mark_awaiting_checkpoint(workflow_id, result, validate=False)

    except Exception as e:
        logger.error(f"Workflow {workflow_id} failed: {e}", exc_info=True)
        await status_manager.mark_failed(workflow_id, e, validate=False)

@router.get("/{workflow_id}", response_model=WorkflowStateSnapshot)
async def get_workflow(workflow_id: str):
    """Get current workflow state including pending checkpoint"""

    # Get workflow from database
    async with db.get_connection() as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT * FROM workflows WHERE id = ?",
            (workflow_id,)
        )
        workflow_row = await cursor.fetchone()

        if not workflow_row:
            raise HTTPException(status_code=404, detail="Workflow not found")

    # Get LangGraph checkpoint data
    pending_checkpoint = None
    current_iteration = 0
    if workflow_id in active_workflows:
        workflow_data = active_workflows[workflow_id]
        compiled_workflow = workflow_data["compiled"]
        config = {"configurable": {"thread_id": workflow_id}}

        # Get current state from LangGraph checkpoint
        try:
            # Use async method since we're using AsyncSqliteSaver
            state = await compiled_workflow.aget_state(config)
            logger.debug(f"[API] State for {workflow_id}: has interrupts={bool(state.interrupts if state else False)}")

            # Extract current iteration from state values (available even when agents are running)
            if state and hasattr(state, 'values') and state.values:
                current_iteration = state.values.get("iteration_count", 0)
                logger.debug(f"[API] Current iteration for {workflow_id}: {current_iteration}")

            # LangGraph stores interrupt data in state.interrupts (tuple of Interrupt objects)
            # NOT in state.values['__interrupt__']
            if state and hasattr(state, 'interrupts') and state.interrupts:
                # interrupts is a tuple, take the first one
                interrupt_obj = state.interrupts[0]
                logger.debug(f"[API] Found interrupt object: {type(interrupt_obj)}")

                # Extract the value from the Interrupt object
                if hasattr(interrupt_obj, 'value'):
                    pending_checkpoint = interrupt_obj.value
                    logger.debug(f"[API] ✓ Extracted checkpoint data, keys: {pending_checkpoint.keys() if isinstance(pending_checkpoint, dict) else 'not a dict'}")

                    # Save checkpoint to database for audit trail
                    if isinstance(pending_checkpoint, dict) and pending_checkpoint.get("checkpoint_id"):
                        try:
                            await save_checkpoint_created(pending_checkpoint)
                            logger.debug(f"[API] ✓ Saved checkpoint {pending_checkpoint.get('checkpoint_id')} to database")
                        except Exception as checkpoint_error:
                            logger.warning(f"[API] Failed to save checkpoint to database: {checkpoint_error}")
                            # Don't fail the request if checkpoint save fails
                else:
                    logger.debug(f"[API] Interrupt object has no 'value' attribute")
            else:
                logger.debug(f"[API] No interrupts in state (state={state is not None}, has_attr={hasattr(state, 'interrupts') if state else False}, interrupts={state.interrupts if state and hasattr(state, 'interrupts') else None})")
        except Exception as e:
            logger.error(f"[API] Error getting checkpoint state: {e}", exc_info=True)

    workflow_dict = dict(workflow_row)
    # Convert string timestamps to datetime
    workflow_dict['created_at'] = datetime.fromisoformat(workflow_dict['created_at'])
    workflow_dict['updated_at'] = datetime.fromisoformat(workflow_dict['updated_at'])

    # Fetch agent executions for this workflow
    agent_executions = []
    async with db.get_connection() as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            """
            SELECT * FROM agent_executions
            WHERE workflow_id = ?
            ORDER BY started_at ASC
            """,
            (workflow_id,)
        )
        rows = await cursor.fetchall()
        agent_executions = [dict(row) for row in rows]

    # Add approval status to review agents
    from backend.services.review_analyzer import analyze_review_approval
    for execution in agent_executions:
        if execution.get('agent_type') == 'review' and execution.get('output_content'):
            execution['approval_status'] = analyze_review_approval(execution['output_content'])
        else:
            execution['approval_status'] = None

    return WorkflowStateSnapshot(
        workflow=WorkflowResponse(**workflow_dict),
        pending_checkpoint=pending_checkpoint,
        recent_messages=[],
        agent_executions=agent_executions,
        current_iteration=current_iteration
    )

@router.post("/{workflow_id}/resume")
async def resume_workflow(
    workflow_id: str,
    resolution: dict,
    background_tasks: BackgroundTasks
):
    """Resume workflow after checkpoint resolution"""

    if workflow_id not in active_workflows:
        raise HTTPException(status_code=404, detail="Workflow not found")

    compiled_workflow = active_workflows[workflow_id]["compiled"]
    config = {"configurable": {"thread_id": workflow_id}}

    # Resume with user input
    background_tasks.add_task(
        resume_workflow_execution,
        workflow_id,
        compiled_workflow,
        config,
        resolution
    )

    return {"status": "resuming", "workflow_id": workflow_id}

async def resume_workflow_execution(
    workflow_id: str,
    compiled_workflow,
    config: dict,
    resolution: dict
):
    """Resume workflow execution after human input"""
    try:
        # Mark workflow as running before executing agents
        await status_manager.mark_running(workflow_id, validate=False)
        logger.info(f"Workflow {workflow_id} resumed and marked as running")

        # Save checkpoint resolution to database for audit trail
        try:
            # Get current checkpoint ID from LangGraph state
            state = await compiled_workflow.aget_state(config)
            if state and hasattr(state, 'interrupts') and state.interrupts:
                interrupt_obj = state.interrupts[0]
                if hasattr(interrupt_obj, 'value'):
                    checkpoint_data = interrupt_obj.value
                    if isinstance(checkpoint_data, dict):
                        checkpoint_id = checkpoint_data.get("checkpoint_id")
                        if checkpoint_id:
                            await save_checkpoint_resolution(
                                checkpoint_id=checkpoint_id,
                                action=resolution.get("action", "unknown"),
                                edited_content=resolution.get("edited_content"),
                                user_notes=resolution.get("user_notes")
                            )
                            logger.debug(f"[API] ✓ Saved checkpoint resolution for {checkpoint_id}")
        except Exception as checkpoint_error:
            logger.warning(f"[API] Failed to save checkpoint resolution: {checkpoint_error}")
            # Don't fail the workflow if checkpoint save fails

        # Resume with Command - use async API
        result = await compiled_workflow.ainvoke(
            Command(resume=resolution),
            config
        )

        # Check if workflow completed or hit another checkpoint
        # We need to check the state for interrupts, not the result truthiness
        # (ainvoke always returns the state dict, so `if result:` is always True)
        state_after_resume = await compiled_workflow.aget_state(config)
        has_pending_checkpoint = (
            state_after_resume and
            hasattr(state_after_resume, 'interrupts') and
            state_after_resume.interrupts
        )

        if has_pending_checkpoint:
            # Hit another checkpoint - mark as awaiting (atomic update)
            await status_manager.mark_awaiting_checkpoint(workflow_id, result, validate=False)
        else:
            # Workflow completed - mark as done (atomic update with cleanup)
            await status_manager.mark_completed(workflow_id, validate=False)

    except Exception as e:
        logger.error(f"Resume failed for {workflow_id}: {e}", exc_info=True)
        await status_manager.mark_failed(workflow_id, e, validate=False)

@router.get("/{workflow_id}/history")
async def get_workflow_history(workflow_id: str):
    """Get full checkpoint history for workflow with enriched plan/review data"""

    if workflow_id not in active_workflows:
        raise HTTPException(status_code=404, detail="Workflow not found")

    compiled_workflow = active_workflows[workflow_id]["compiled"]
    config = {"configurable": {"thread_id": workflow_id}}

    # Get checkpoint history from LangGraph
    history = []
    try:
        # get_state_history returns states in reverse chronological order (newest first)
        # We'll reverse it to show oldest→newest for timeline display
        states_list = []
        async for state in compiled_workflow.aget_state_history(config):
            states_list.append(state)

        # Reverse to get chronological order
        states_list.reverse()

        for idx, state in enumerate(states_list):
            # Extract useful data from state
            state_values = state.values if state else {}

            # Determine step type based on state content
            step_type = "unknown"
            step_name = f"Step {idx + 1}"

            if "current_plan" in state_values:
                step_type = "plan"
                step_name = f"Plan (Iteration {state_values.get('iteration_count', 0)})"
            elif "reviews" in state_values and state_values["reviews"]:
                step_type = "review"
                step_name = f"Review {len(state_values['reviews'])} agents"

            # Extract relevant data for timeline display
            history_item = {
                "checkpoint_id": str(state.config.get("configurable", {}).get("checkpoint_id", "unknown")),
                "step_number": idx + 1,
                "step_type": step_type,
                "step_name": step_name,
                "iteration_count": state_values.get("iteration_count", 0),
                "checkpoint_number": state_values.get("checkpoint_number", 0),
                "created_at": state.created_at.isoformat() if state.created_at else None,
                "next_step": list(state.next) if state.next else [],

                # Include plan/review data for inspection
                "current_plan": state_values.get("current_plan", ""),
                "reviews": state_values.get("reviews", []),
                "instructions": state_values.get("instructions", ""),
                "actions": state_values.get("actions", []),
            }

            history.append(history_item)
    except Exception as e:
        logger.error(f"Error getting history: {e}", exc_info=True)
        history = []

    return {"workflow_id": workflow_id, "history": history}
