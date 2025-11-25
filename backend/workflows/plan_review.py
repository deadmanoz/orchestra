from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from datetime import datetime
import operator
import asyncio
import logging
import time

from backend.workflows.templates import PromptTemplates
from backend.agents.base import AgentInterface
from backend.settings import settings
from backend.services.checkpoint_manager import CheckpointManager
from backend.db.connection import db

logger = logging.getLogger(__name__)

# Define workflow state
class PlanReviewState(TypedDict):
    """State shared across all nodes in the workflow"""
    messages: Annotated[Sequence[BaseMessage], operator.add]
    workflow_id: str
    current_plan: str
    review_feedback: list[dict]
    iteration_count: int
    checkpoint_number: int
    status: str
    user_edits: str
    next_step: str
    reviewer_prompt: str  # Custom reviewer prompt (if user wants to edit full prompt)
    planner_prompt: str  # Custom planner revision prompt (if user wants to edit full prompt)
    retry_agent: bool  # Flag to indicate retry after timeout
    timeout_extension: int  # Seconds to extend timeout for retry
    skip_timed_out_agent: str  # Agent name to skip if user chose to skip

class PlanReviewWorkflow:
    """Implements the plan-review-iterate workflow with human checkpoints"""

    def __init__(self, agent_factory, workspace_path: str = None):
        self.agent_factory = agent_factory
        self.workspace_path = workspace_path
        self.templates = PromptTemplates()
        self.checkpoint_manager = CheckpointManager()
        self.graph = self._build_graph()
        # Use AsyncSqliteSaver for async workflow execution
        # Initialize the async context manager
        self._checkpointer_cm = AsyncSqliteSaver.from_conn_string(settings.langgraph_checkpoint_db)
        # We'll enter the context manager in an async setup method
        self.checkpointer = None
        self._setup_complete = False

    async def _create_agent_execution(
        self,
        workflow_id: str,
        agent_name: str,
        agent_type: str,
        input_content: str
    ) -> int:
        """
        Create an agent execution record in the database.

        Returns:
            The execution ID
        """
        async with db.get_connection() as conn:
            cursor = await conn.execute(
                """
                INSERT INTO agent_executions (
                    workflow_id, agent_name, agent_type, input_content,
                    status, started_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    workflow_id,
                    agent_name,
                    agent_type,
                    input_content,
                    "running",
                    datetime.now().isoformat()
                )
            )
            await conn.commit()
            return cursor.lastrowid

    async def _complete_agent_execution(
        self,
        execution_id: int,
        output_content: str,
        execution_time_ms: int,
        status: str = "completed"
    ) -> None:
        """
        Update an agent execution record when complete.

        Args:
            execution_id: The execution ID
            output_content: The agent's output
            execution_time_ms: Execution time in milliseconds
            status: Final status (completed or failed)
        """
        async with db.get_connection() as conn:
            await conn.execute(
                """
                UPDATE agent_executions
                SET output_content = ?,
                    status = ?,
                    completed_at = ?,
                    execution_time_ms = ?
                WHERE id = ?
                """,
                (
                    output_content,
                    status,
                    datetime.now().isoformat(),
                    execution_time_ms,
                    execution_id
                )
            )
            await conn.commit()

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow"""
        workflow = StateGraph(PlanReviewState)

        # Add nodes
        workflow.add_node("planning_agent", self._planning_agent_node)
        workflow.add_node("plan_checkpoint", self._plan_checkpoint_node)
        workflow.add_node("edit_reviewer_prompt_checkpoint", self._edit_reviewer_prompt_checkpoint_node)
        workflow.add_node("review_agents", self._review_agents_node)
        workflow.add_node("review_checkpoint", self._review_checkpoint_node)
        workflow.add_node("edit_planner_prompt_checkpoint", self._edit_planner_prompt_checkpoint_node)

        # Set entry point
        workflow.set_entry_point("planning_agent")

        # Define edges with conditional routing for timeout retries
        # Planning agent can route to plan_checkpoint OR retry itself on timeout OR end if cancelled
        workflow.add_conditional_edges(
            "planning_agent",
            lambda state: (
                "planning_agent" if state.get("retry_agent")
                else state.get("next_step", "plan_checkpoint") if state.get("next_step") == "end"
                else "plan_checkpoint"
            ),
            {
                "planning_agent": "planning_agent",  # Retry after timeout
                "plan_checkpoint": "plan_checkpoint",  # Normal flow
                "end": END  # Cancel
            }
        )

        # Conditional edge from plan checkpoint based on action
        workflow.add_conditional_edges(
            "plan_checkpoint",
            lambda state: state.get("next_step", "review_agents"),
            {
                "edit_reviewer_prompt": "edit_reviewer_prompt_checkpoint",
                "review_agents": "review_agents",
                "end": END
            }
        )

        workflow.add_edge("edit_reviewer_prompt_checkpoint", "review_agents")

        # Review agents can route to review_checkpoint OR retry itself on timeout OR end if cancelled
        workflow.add_conditional_edges(
            "review_agents",
            lambda state: (
                "review_agents" if state.get("retry_agent")
                else state.get("next_step", "review_checkpoint") if state.get("next_step") in ["review_checkpoint", "end"]
                else "review_checkpoint"
            ),
            {
                "review_agents": "review_agents",  # Retry after timeout
                "review_checkpoint": "review_checkpoint",  # Normal flow or skip
                "end": END  # Cancel
            }
        )

        # Conditional edge from review checkpoint
        workflow.add_conditional_edges(
            "review_checkpoint",
            lambda state: state.get("next_step", "end"),
            {
                "edit_planner_prompt": "edit_planner_prompt_checkpoint",
                "planning_agent": "planning_agent",
                "end": END
            }
        )

        workflow.add_edge("edit_planner_prompt_checkpoint", "planning_agent")

        return workflow

    async def _planning_agent_node(self, state: PlanReviewState) -> dict:
        """Node for planning agent execution"""
        from backend.agents.cli_agent import CLIAgentError

        iteration = state.get('iteration_count', 0)
        workflow_id = state.get('workflow_id')
        logger.info(f"[PlanningAgent] Starting iteration {iteration}")

        # Get planning agent
        planning_agent = await self.agent_factory.get_agent("planning", "claude_planner", workspace_path=self.workspace_path)

        # Check if we're retrying after timeout with extension
        if state.get("retry_agent") and state.get("timeout_extension"):
            timeout_extension = state.get("timeout_extension", 0)
            logger.info(f"[PlanningAgent] Retrying with +{timeout_extension}s timeout extension")
            # Temporarily extend timeout
            original_timeout = planning_agent.timeout
            planning_agent.timeout = original_timeout + timeout_extension

        # Build prompt - check if user provided custom planner prompt
        if state.get("planner_prompt"):
            # Use custom planner prompt edited by user
            logger.info(f"[PlanningAgent] Using custom planner prompt edited by user")
            prompt = state["planner_prompt"]
        elif iteration > 0:
            # Revision with FULL conversation history for context
            # This allows the agent to remember previous attempts and user preferences
            logger.info(f"[PlanningAgent] Using conversation history template (iteration {iteration})")
            prompt = self.templates.planning_with_history(
                messages=state["messages"],
                review_feedback=state.get("review_feedback")
            )
        else:
            # Initial planning - use default template
            logger.info(f"[PlanningAgent] Using default initial planning template")
            initial_message = state["messages"][-1].content
            prompt = self.templates.planning_initial(initial_message)

        # Create execution record
        execution_id = await self._create_agent_execution(
            workflow_id=workflow_id,
            agent_name=planning_agent.name,
            agent_type="planning",
            input_content=prompt  # Store full prompt
        )

        # Execute agent with timing
        logger.debug(f"[PlanningAgent] Prompt length: {len(prompt)} chars")
        start_time = time.time()
        try:
            plan = await planning_agent.send_message(prompt)
            execution_time_ms = int((time.time() - start_time) * 1000)

            # Update execution record
            await self._complete_agent_execution(
                execution_id=execution_id,
                output_content=plan,
                execution_time_ms=execution_time_ms,
                status="completed"
            )

            # Clear retry flags if successful
            return {
                "current_plan": plan,
                "status": "plan_created",
                "messages": [AIMessage(content=plan, name="planning_agent")],
                "checkpoint_number": state.get("checkpoint_number", 0) + 1,
                "retry_agent": None,  # Clear retry flag
                "timeout_extension": None  # Clear extension
            }
        except CLIAgentError as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            await self._complete_agent_execution(
                execution_id=execution_id,
                output_content=str(e),
                execution_time_ms=execution_time_ms,
                status="failed"
            )

            # Check if it's a timeout error
            if "timed out" in str(e).lower():
                logger.warning(f"[PlanningAgent] Timeout detected, creating checkpoint for user decision")
                # Create timeout checkpoint instead of failing
                return await self.checkpoint_manager.create_timeout_checkpoint(
                    state=state,
                    agent_name=planning_agent.name,
                    agent_type="planning",
                    timeout_seconds=planning_agent.timeout,
                    error_message=str(e),
                    prompt=prompt
                )
            else:
                # Non-timeout error, re-raise
                raise
        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            await self._complete_agent_execution(
                execution_id=execution_id,
                output_content=str(e),
                execution_time_ms=execution_time_ms,
                status="failed"
            )
            raise

    async def _plan_checkpoint_node(self, state: PlanReviewState) -> dict:
        """Human checkpoint before sending to reviewers"""
        logger.info(f"[Checkpoint] Plan ready for review - awaiting human approval")

        # Use CheckpointManager to handle checkpoint lifecycle
        return await self.checkpoint_manager.create_plan_review_checkpoint(
            state=state,
            plan=state["current_plan"]
        )

    async def _edit_reviewer_prompt_checkpoint_node(self, state: PlanReviewState) -> dict:
        """Human checkpoint for editing the complete reviewer prompt"""
        logger.info(f"[Checkpoint] Edit reviewer prompt - awaiting human edits")

        # Generate the default reviewer prompt
        plan_to_review = state.get("user_edits") or state["current_plan"]
        default_reviewer_prompt = self.templates.review_request(plan_to_review, "REVIEW_AGENT")

        # Use CheckpointManager to handle checkpoint lifecycle
        return await self.checkpoint_manager.create_prompt_edit_checkpoint(
            state=state,
            prompt=default_reviewer_prompt,
            step_name="edit_reviewer_prompt",
            primary_action="send_to_reviewers",
            instructions=(
                "Edit the complete prompt that will be sent to all REVIEW AGENTS.\n\n"
                "You can inject user feedback, directives, or additional context here.\n"
                "The edited prompt will be sent to all reviewers (Claude, Codex, Gemini).\n\n"
                "Tip: Add user feedback like this:\n"
                "**** USER FEEDBACK START ****\n"
                "[Your feedback/directives here]\n"
                "**** USER FEEDBACK END ****"
            )
        )

    async def _review_agents_node(self, state: PlanReviewState) -> dict:
        """Node for parallel review agent execution"""
        iteration = state.get('iteration_count', 0)
        workflow_id = state.get('workflow_id')
        logger.info(f"[ReviewAgents] Executing parallel reviews (iteration {iteration})")

        # Get review agents
        review_agents = await self.agent_factory.get_review_agents(workspace_path=self.workspace_path)

        # Check if user provided a custom reviewer prompt
        if state.get("reviewer_prompt"):
            # Use the custom prompt edited by the user
            logger.info(f"[ReviewAgents] Using custom reviewer prompt edited by user")
            reviewer_prompt = state["reviewer_prompt"]
            # Execute all reviews in parallel with the same custom prompt
            review_tasks = [
                self._execute_review_agent_tracked(agent, reviewer_prompt, workflow_id, idx + 1)
                for idx, agent in enumerate(review_agents)
            ]
        elif iteration > 0:
            # Revision with FULL conversation history for context
            # Review agents can reference their previous reviews
            logger.info(f"[ReviewAgents] Using conversation history template (iteration {iteration})")
            plan_to_review = state.get("user_edits") or state["current_plan"]
            review_tasks = [
                self._execute_review_agent_with_history_tracked(agent, plan_to_review, state["messages"], workflow_id, idx + 1)
                for idx, agent in enumerate(review_agents)
            ]
        else:
            # Initial review - use default template
            logger.info(f"[ReviewAgents] Using default reviewer prompt template")
            plan_to_review = state.get("user_edits") or state["current_plan"]
            review_tasks = [
                self._execute_review_agent_tracked(
                    agent,
                    self.templates.review_request(plan_to_review, idx + 1),
                    workflow_id,
                    idx + 1
                )
                for idx, agent in enumerate(review_agents)
            ]

        review_results = await asyncio.gather(*review_tasks)

        # Check for timeouts
        timed_out_agents = [r for r in review_results if r.get("timeout")]
        successful_reviews = [r for r in review_results if r.get("success")]

        # If any agent timed out, create checkpoint for first timeout
        if timed_out_agents:
            first_timeout = timed_out_agents[0]
            logger.warning(
                f"[ReviewAgents] {first_timeout['agent_name']} timed out, "
                f"creating checkpoint ({len(successful_reviews)}/{len(review_results)} agents completed)"
            )

            # Build feedback from successful reviews to preserve in state
            successful_feedback = [
                {
                    "agent_name": review_agents[i].name,
                    "agent_type": review_agents[i].agent_type,
                    "agent_identifier": f"REVIEW AGENT {i + 1}",
                    "feedback": result["result"],
                    "timestamp": datetime.now().isoformat()
                }
                for i, result in enumerate(review_results)
                if result.get("success")
            ]

            # Store successful reviews so far in state for potential skip action
            checkpoint_result = await self.checkpoint_manager.create_timeout_checkpoint(
                state=state,
                agent_name=first_timeout["agent_name"],
                agent_type="review",
                timeout_seconds=first_timeout["timeout_seconds"],
                error_message=first_timeout["error"],
                prompt=first_timeout["prompt"]
            )

            # If user chose to skip, include the successful reviews we collected
            if checkpoint_result.get("skip_timed_out_agent"):
                checkpoint_result["review_feedback"] = successful_feedback
                if successful_feedback:
                    checkpoint_result["messages"] = checkpoint_result.get("messages", []) + [
                        AIMessage(content=fb["feedback"], name=f"review_agent_{i}")
                        for i, fb in enumerate(successful_feedback)
                    ]

            return checkpoint_result

        # All successful - collect feedback with generic agent names for prompts
        feedback = [
            {
                "agent_name": review_agents[i].name,  # Real name for DB/UI
                "agent_type": review_agents[i].agent_type,  # Real type for DB/UI
                "agent_identifier": f"REVIEW AGENT {i + 1}",  # Generic name for prompts
                "feedback": result["result"],
                "timestamp": datetime.now().isoformat()
            }
            for i, result in enumerate(review_results)
            if result.get("success")
        ]

        return {
            "review_feedback": feedback,
            "status": "reviews_collected",
            "messages": [
                AIMessage(content=result["result"], name=f"review_agent_{i}")
                for i, result in enumerate(review_results)
                if result.get("success")
            ],
            "checkpoint_number": state["checkpoint_number"] + 1
        }

    async def _execute_review_agent(self, agent: AgentInterface, plan: str, agent_index: int = 1) -> str:
        """Execute single review agent (initial review, no history)"""
        prompt = self.templates.review_request(plan, agent_index)
        return await agent.send_message(prompt)

    async def _execute_review_agent_with_history(
        self,
        agent: AgentInterface,
        plan: str,
        messages: list,
        agent_index: int = 1
    ) -> str:
        """Execute review agent with full conversation history"""
        prompt = self.templates.review_with_history(messages, plan, agent_index)
        logger.debug(f"[{agent.name}] Prompt with history length: {len(prompt)} chars")
        return await agent.send_message(prompt)

    async def _execute_review_agent_tracked(
        self,
        agent: AgentInterface,
        prompt: str,
        workflow_id: str,
        agent_index: int
    ) -> dict:
        """
        Execute review agent with database tracking.

        Returns:
            Dict with 'success', 'result', 'agent_name', 'timeout' keys
        """
        from backend.agents.cli_agent import CLIAgentError

        # Create execution record
        execution_id = await self._create_agent_execution(
            workflow_id=workflow_id,
            agent_name=agent.name,
            agent_type="review",
            input_content=prompt  # Store full prompt
        )

        # Execute with timing
        start_time = time.time()
        try:
            result = await agent.send_message(prompt)
            execution_time_ms = int((time.time() - start_time) * 1000)

            # Update execution record
            await self._complete_agent_execution(
                execution_id=execution_id,
                output_content=result,
                execution_time_ms=execution_time_ms,
                status="completed"
            )
            return {
                "success": True,
                "result": result,
                "agent_name": agent.name,
                "agent_index": agent_index,
                "timeout": False
            }
        except CLIAgentError as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            await self._complete_agent_execution(
                execution_id=execution_id,
                output_content=str(e),
                execution_time_ms=execution_time_ms,
                status="failed"
            )

            # Check if it's a timeout
            if "timed out" in str(e).lower():
                logger.warning(f"[{agent.name}] Timeout detected, will ask user how to proceed")
                return {
                    "success": False,
                    "result": None,
                    "agent_name": agent.name,
                    "agent_index": agent_index,
                    "timeout": True,
                    "error": str(e),
                    "timeout_seconds": agent.timeout,
                    "prompt": prompt
                }
            else:
                # Non-timeout error, re-raise
                raise
        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            await self._complete_agent_execution(
                execution_id=execution_id,
                output_content=str(e),
                execution_time_ms=execution_time_ms,
                status="failed"
            )
            raise

    async def _execute_review_agent_with_history_tracked(
        self,
        agent: AgentInterface,
        plan: str,
        messages: list,
        workflow_id: str,
        agent_index: int
    ) -> dict:
        """
        Execute review agent with history and database tracking.

        Returns:
            Dict with 'success', 'result', 'agent_name', 'timeout' keys
        """
        from backend.agents.cli_agent import CLIAgentError

        prompt = self.templates.review_with_history(messages, plan, agent_index)
        logger.debug(f"[{agent.name}] Prompt with history length: {len(prompt)} chars")

        # Create execution record
        execution_id = await self._create_agent_execution(
            workflow_id=workflow_id,
            agent_name=agent.name,
            agent_type="review",
            input_content=prompt  # Store full prompt
        )

        # Execute with timing
        start_time = time.time()
        try:
            result = await agent.send_message(prompt)
            execution_time_ms = int((time.time() - start_time) * 1000)

            # Update execution record
            await self._complete_agent_execution(
                execution_id=execution_id,
                output_content=result,
                execution_time_ms=execution_time_ms,
                status="completed"
            )
            return {
                "success": True,
                "result": result,
                "agent_name": agent.name,
                "agent_index": agent_index,
                "timeout": False
            }
        except CLIAgentError as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            await self._complete_agent_execution(
                execution_id=execution_id,
                output_content=str(e),
                execution_time_ms=execution_time_ms,
                status="failed"
            )

            # Check if it's a timeout
            if "timed out" in str(e).lower():
                logger.warning(f"[{agent.name}] Timeout detected, will ask user how to proceed")
                return {
                    "success": False,
                    "result": None,
                    "agent_name": agent.name,
                    "agent_index": agent_index,
                    "timeout": True,
                    "error": str(e),
                    "timeout_seconds": agent.timeout,
                    "prompt": prompt
                }
            else:
                # Non-timeout error, re-raise
                raise
        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            await self._complete_agent_execution(
                execution_id=execution_id,
                output_content=str(e),
                execution_time_ms=execution_time_ms,
                status="failed"
            )
            raise

    async def _review_checkpoint_node(self, state: PlanReviewState) -> dict:
        """Human checkpoint after reviews - decide next action"""
        logger.info(f"[Checkpoint] Reviews collected - awaiting human decision")

        consolidated_feedback = self._consolidate_reviews(state["review_feedback"])
        return await self.checkpoint_manager.create_review_consolidation_checkpoint(
            state=state,
            consolidated_feedback=consolidated_feedback
        )

    async def _edit_planner_prompt_checkpoint_node(self, state: PlanReviewState) -> dict:
        """Human checkpoint for editing the complete planner revision prompt"""
        logger.info(f"[Checkpoint] Edit planner prompt - awaiting human edits")

        # Generate the default planner revision prompt
        current_plan = state.get("user_edits") or state["current_plan"]
        review_feedback = [
            {
                "agent_identifier": fb.get("agent_identifier", "REVIEW AGENT"),
                "feedback": fb["feedback"]
            }
            for fb in state["review_feedback"]
        ]
        default_planner_prompt = self.templates.planning_revision(current_plan, review_feedback)

        # Use CheckpointManager to handle checkpoint lifecycle
        return await self.checkpoint_manager.create_prompt_edit_checkpoint(
            state=state,
            prompt=default_planner_prompt,
            step_name="edit_planner_prompt",
            primary_action="send_to_planner_for_revision",
            instructions=(
                "Edit the complete prompt that will be sent to the PLANNING AGENT for revision.\n\n"
                "You can inject user feedback, directives, or additional context here.\n"
                "The edited prompt will be sent to the planner to revise the plan.\n\n"
                "Tip: Add user feedback/directives like this:\n"
                "**** USER FEEDBACK START ****\n"
                "[Your feedback/directives here]\n"
                "**** USER FEEDBACK END ****"
            )
        )

    def _consolidate_reviews(self, feedback: list[dict]) -> str:
        """Consolidate multiple review feedbacks into editable format"""
        consolidated = "=== CONSOLIDATED REVIEW FEEDBACK ===\n\n"

        for fb in feedback:
            # Use generic agent_identifier for prompts, not agent_name
            agent_id = fb.get('agent_identifier', fb.get('agent_name', 'REVIEW AGENT'))
            consolidated += f"## {agent_id}\n\n"
            consolidated += fb['feedback']
            consolidated += "\n\n" + "="*60 + "\n\n"

        consolidated += "\n=== USER CONSOLIDATION ===\n"
        consolidated += "[Edit this section to provide consolidated feedback to the PLANNING AGENT]\n\n"

        return consolidated

    async def setup(self):
        """Async setup to initialize the checkpointer context manager"""
        if not self._setup_complete:
            self.checkpointer = await self._checkpointer_cm.__aenter__()
            self._setup_complete = True

    def compile(self):
        """Compile the workflow with SQLite checkpointer"""
        # Note: setup() must be called before compile() to initialize checkpointer
        if self.checkpointer is None:
            raise RuntimeError("Workflow not set up. Call await workflow.setup() before compile()")
        return self.graph.compile(checkpointer=self.checkpointer)
