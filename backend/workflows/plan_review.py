from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from datetime import datetime
import operator
import asyncio
import logging

from backend.workflows.templates import PromptTemplates
from backend.agents.base import AgentInterface
from backend.config import settings
from backend.services.checkpoint_manager import CheckpointManager

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

        # Define edges
        workflow.add_edge("planning_agent", "plan_checkpoint")

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
        workflow.add_edge("review_agents", "review_checkpoint")

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
        iteration = state.get('iteration_count', 0)
        logger.info(f"[PlanningAgent] Starting iteration {iteration}")

        # Get planning agent
        planning_agent = await self.agent_factory.get_agent("planning", "claude_planner", workspace_path=self.workspace_path)

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

        # Execute agent
        logger.debug(f"[PlanningAgent] Prompt length: {len(prompt)} chars")
        plan = await planning_agent.send_message(prompt)

        return {
            "current_plan": plan,
            "status": "plan_created",
            "messages": [AIMessage(content=plan, name="planning_agent")],
            "checkpoint_number": state.get("checkpoint_number", 0) + 1
        }

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
                agent.send_message(reviewer_prompt)
                for agent in review_agents
            ]
        elif iteration > 0:
            # Revision with FULL conversation history for context
            # Review agents can reference their previous reviews
            logger.info(f"[ReviewAgents] Using conversation history template (iteration {iteration})")
            plan_to_review = state.get("user_edits") or state["current_plan"]
            review_tasks = [
                self._execute_review_agent_with_history(agent, plan_to_review, state["messages"])
                for agent in review_agents
            ]
        else:
            # Initial review - use default template
            logger.info(f"[ReviewAgents] Using default reviewer prompt template")
            plan_to_review = state.get("user_edits") or state["current_plan"]
            review_tasks = [
                self._execute_review_agent(agent, plan_to_review)
                for agent in review_agents
            ]

        reviews = await asyncio.gather(*review_tasks)

        # Collect feedback
        feedback = [
            {
                "agent_name": agent.name,
                "agent_type": agent.agent_type,
                "feedback": review,
                "timestamp": datetime.now().isoformat()
            }
            for agent, review in zip(review_agents, reviews)
        ]

        return {
            "review_feedback": feedback,
            "status": "reviews_collected",
            "messages": [
                AIMessage(content=review, name=f"review_agent_{i}")
                for i, review in enumerate(reviews)
            ],
            "checkpoint_number": state["checkpoint_number"] + 1
        }

    async def _execute_review_agent(self, agent: AgentInterface, plan: str) -> str:
        """Execute single review agent (initial review, no history)"""
        prompt = self.templates.review_request(plan, agent.name)
        return await agent.send_message(prompt)

    async def _execute_review_agent_with_history(
        self,
        agent: AgentInterface,
        plan: str,
        messages: list
    ) -> str:
        """Execute review agent with full conversation history"""
        prompt = self.templates.review_with_history(messages, plan, agent.name)
        logger.debug(f"[{agent.name}] Prompt with history length: {len(prompt)} chars")
        return await agent.send_message(prompt)

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
                "agent_name": fb["agent_name"],
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
            consolidated += f"## {fb['agent_name']}\n\n"
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
