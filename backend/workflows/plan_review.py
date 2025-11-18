from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command, interrupt
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from datetime import datetime
import operator
import uuid
import asyncio

from backend.workflows.templates import PromptTemplates
from backend.agents.base import AgentInterface
from backend.config import settings

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

class PlanReviewWorkflow:
    """Implements the plan-review-iterate workflow with human checkpoints"""

    def __init__(self, agent_factory, workspace_path: str = None):
        self.agent_factory = agent_factory
        self.workspace_path = workspace_path
        self.templates = PromptTemplates()
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
        workflow.add_node("review_agents", self._review_agents_node)
        workflow.add_node("review_checkpoint", self._review_checkpoint_node)

        # Set entry point
        workflow.set_entry_point("planning_agent")

        # Define edges
        workflow.add_edge("planning_agent", "plan_checkpoint")
        workflow.add_edge("plan_checkpoint", "review_agents")
        workflow.add_edge("review_agents", "review_checkpoint")

        # Conditional edge from review checkpoint
        workflow.add_conditional_edges(
            "review_checkpoint",
            lambda state: state.get("next_step", "end"),
            {
                "planning_agent": "planning_agent",
                "end": END
            }
        )

        return workflow

    async def _planning_agent_node(self, state: PlanReviewState) -> dict:
        """Node for planning agent execution"""
        print(f"[PlanningAgent] Starting iteration {state.get('iteration_count', 0)}")

        # Get planning agent
        planning_agent = await self.agent_factory.get_agent("planning", "claude_planner", workspace_path=self.workspace_path)

        # Build prompt
        if state.get("review_feedback"):
            # Revision based on feedback
            prompt = self.templates.planning_revision(
                state.get("user_edits") or state["current_plan"],
                state["review_feedback"]
            )
        else:
            # Initial planning
            initial_message = state["messages"][-1].content
            prompt = self.templates.planning_initial(initial_message)

        # Execute agent
        plan = await planning_agent.send_message(prompt)

        return {
            "current_plan": plan,
            "status": "plan_created",
            "messages": [AIMessage(content=plan, name="planning_agent")],
            "checkpoint_number": state.get("checkpoint_number", 0) + 1
        }

    async def _plan_checkpoint_node(self, state: PlanReviewState) -> dict:
        """Human checkpoint before sending to reviewers"""
        print(f"[Checkpoint] Plan ready for review - awaiting human approval")

        checkpoint_data = {
            "checkpoint_id": str(uuid.uuid4()),
            "checkpoint_number": state["checkpoint_number"],
            "step_name": "plan_ready_for_review",
            "workflow_id": state["workflow_id"],
            "iteration": state.get("iteration_count", 0),
            "agent_outputs": [{
                "agent_name": "planning_agent",
                "agent_type": "planning",
                "output": state["current_plan"],
                "timestamp": datetime.now().isoformat()
            }],
            "instructions": (
                "The PLANNING AGENT has created a plan. "
                "Review and edit if needed before sending to REVIEW AGENTS."
            ),
            "actions": {
                "primary": "send_to_reviewers",
                "secondary": ["edit_and_continue", "cancel"]
            },
            "editable_content": state["current_plan"]
        }

        # This pauses workflow until human provides input
        human_input = interrupt(checkpoint_data)

        # Process human decision
        edited_plan = human_input.get("edited_content", state["current_plan"])

        return {
            "user_edits": edited_plan,
            "status": "ready_for_review",
            "messages": [HumanMessage(
                content=f"[User approved plan for review]",
                name="user"
            )]
        }

    async def _review_agents_node(self, state: PlanReviewState) -> dict:
        """Node for parallel review agent execution"""
        print(f"[ReviewAgents] Executing parallel reviews")

        # Get review agents
        review_agents = await self.agent_factory.get_review_agents(workspace_path=self.workspace_path)

        plan_to_review = state.get("user_edits") or state["current_plan"]

        # Execute all reviews in parallel
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
        """Execute single review agent"""
        prompt = self.templates.review_request(plan, agent.name)
        return await agent.send_message(prompt)

    async def _review_checkpoint_node(self, state: PlanReviewState) -> dict:
        """Human checkpoint after reviews - decide next action"""
        print(f"[Checkpoint] Reviews collected - awaiting human decision")

        checkpoint_data = {
            "checkpoint_id": str(uuid.uuid4()),
            "checkpoint_number": state["checkpoint_number"],
            "step_name": "reviews_ready_for_consolidation",
            "workflow_id": state["workflow_id"],
            "iteration": state.get("iteration_count", 0),
            "agent_outputs": [
                {
                    "agent_name": fb["agent_name"],
                    "agent_type": "review",
                    "output": fb["feedback"],
                    "timestamp": fb["timestamp"]
                }
                for fb in state["review_feedback"]
            ],
            "instructions": (
                "Multiple REVIEW AGENTS have provided feedback. "
                "You can:\n"
                "1. Approve the plan (end workflow)\n"
                "2. Consolidate feedback and send back to PLANNING AGENT\n"
                "3. Cancel the workflow"
            ),
            "actions": {
                "primary": "send_to_planner_for_revision",
                "secondary": ["approve_plan", "cancel"]
            },
            "editable_content": self._consolidate_reviews(state["review_feedback"]),
            "context": {
                "current_plan": state.get("user_edits") or state["current_plan"]
            }
        }

        # Pause for human decision
        human_input = interrupt(checkpoint_data)

        action = human_input.get("action", "approve_plan")

        if action == "approve_plan":
            return {
                "status": "approved",
                "next_step": "end",
                "messages": [HumanMessage(
                    content="[User approved final plan]",
                    name="user"
                )]
            }
        elif action == "send_to_planner_for_revision":
            consolidated_feedback = human_input.get("edited_content", "")
            return {
                "status": "revision_needed",
                "next_step": "planning_agent",
                "iteration_count": state.get("iteration_count", 0) + 1,
                "user_edits": consolidated_feedback,
                "messages": [HumanMessage(
                    content=f"[User requested revision]\n{consolidated_feedback}",
                    name="user"
                )]
            }
        else:
            return {
                "status": "cancelled",
                "next_step": "end",
                "messages": [HumanMessage(
                    content="[User cancelled workflow]",
                    name="user"
                )]
            }

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
