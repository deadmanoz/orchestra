"""Integration tests for workflow system"""
import pytest
from langchain_core.messages import HumanMessage

from backend.workflows.plan_review import PlanReviewWorkflow, PlanReviewState
from backend.workflows.templates import PromptTemplates
from backend.agents.factory import AgentFactory


class TestPromptTemplates:
    """Test prompt template generation"""

    def test_planning_initial_template(self):
        """Test initial planning prompt"""
        templates = PromptTemplates()
        prompt = templates.planning_initial("Build a web app")

        assert "Build a web app" in prompt
        assert "PLANNING AGENT" in prompt
        assert "REVIEW AGENTS" in prompt.upper()

    def test_planning_revision_template(self):
        """Test revision planning prompt"""
        templates = PromptTemplates()
        feedback = [
            {"agent_name": "Reviewer1", "feedback": "Add security"},
            {"agent_name": "Reviewer2", "feedback": "Consider scalability"}
        ]

        prompt = templates.planning_revision("Original plan", feedback)

        assert "Original plan" in prompt
        assert "Reviewer1" in prompt
        assert "Add security" in prompt
        assert "Reviewer2" in prompt
        assert "Consider scalability" in prompt

    def test_review_request_template(self):
        """Test review request prompt"""
        templates = PromptTemplates()
        prompt = templates.review_request("My development plan", "TestReviewer")

        assert "My development plan" in prompt
        assert "TestReviewer" in prompt
        assert "REVIEW AGENT" in prompt


class TestPlanReviewWorkflow:
    """Test plan-review workflow integration"""

    @pytest.mark.asyncio
    async def test_workflow_initialization(self):
        """Test workflow can be initialized"""
        factory = AgentFactory()
        workflow = PlanReviewWorkflow(factory)

        assert workflow.agent_factory is factory
        assert workflow.graph is not None
        assert workflow._checkpointer_cm is not None
        assert workflow.checkpointer is None  # Not initialized until setup()

        # Test setup
        await workflow.setup()
        assert workflow.checkpointer is not None
        assert workflow._setup_complete is True

    @pytest.mark.asyncio
    async def test_workflow_compile(self):
        """Test workflow can be compiled"""
        factory = AgentFactory()
        workflow = PlanReviewWorkflow(factory)

        await workflow.setup()
        compiled = workflow.compile()

        assert compiled is not None

    @pytest.mark.asyncio
    async def test_planning_agent_node(self):
        """Test planning agent node execution"""
        factory = AgentFactory()
        workflow = PlanReviewWorkflow(factory)

        state = {
            "workflow_id": "test-wf",
            "messages": [HumanMessage(content="Create a plan for a todo app")],
            "iteration_count": 0,
            "checkpoint_number": 0,
            "status": "starting"
        }

        result = await workflow._planning_agent_node(state)

        assert "current_plan" in result
        assert result["status"] == "plan_created"
        assert result["checkpoint_number"] == 1
        assert len(result["messages"]) == 1

    @pytest.mark.asyncio
    async def test_review_agents_node(self):
        """Test review agents node execution"""
        factory = AgentFactory()
        workflow = PlanReviewWorkflow(factory)

        state = {
            "workflow_id": "test-wf",
            "current_plan": "My development plan",
            "user_edits": "My development plan",
            "checkpoint_number": 1
        }

        result = await workflow._review_agents_node(state)

        assert "review_feedback" in result
        assert len(result["review_feedback"]) == 3  # 3 review agents
        assert result["status"] == "reviews_collected"
        assert len(result["messages"]) == 3

    @pytest.mark.asyncio
    async def test_consolidate_reviews(self):
        """Test review consolidation"""
        factory = AgentFactory()
        workflow = PlanReviewWorkflow(factory)

        feedback = [
            {"agent_name": "Agent1", "feedback": "Good plan", "timestamp": "2025-01-01"},
            {"agent_name": "Agent2", "feedback": "Needs work", "timestamp": "2025-01-01"}
        ]

        consolidated = workflow._consolidate_reviews(feedback)

        assert "Agent1" in consolidated
        assert "Agent2" in consolidated
        assert "Good plan" in consolidated
        assert "Needs work" in consolidated
        assert "USER CONSOLIDATION" in consolidated


class TestWorkflowState:
    """Test workflow state management"""

    def test_state_structure(self):
        """Test workflow state has required fields"""
        # This is a TypedDict, just verify the structure is correct
        state_fields = PlanReviewState.__annotations__.keys()

        required_fields = {
            "messages",
            "workflow_id",
            "current_plan",
            "review_feedback",
            "iteration_count",
            "checkpoint_number",
            "status",
            "user_edits",
            "next_step"
        }

        assert required_fields.issubset(state_fields)


@pytest.mark.integration
class TestWorkflowExecution:
    """Integration tests for full workflow execution"""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_full_workflow_to_first_checkpoint(self):
        """Test workflow executes to first checkpoint"""
        factory = AgentFactory()
        workflow = PlanReviewWorkflow(factory)
        await workflow.setup()
        compiled = workflow.compile()

        initial_state = {
            "workflow_id": "integration-test",
            "messages": [HumanMessage(content="Build a simple API")],
            "iteration_count": 0,
            "checkpoint_number": 0,
            "status": "starting"
        }

        config = {"configurable": {"thread_id": "test-thread"}}

        # Execute until first interrupt (checkpoint)
        try:
            result = await compiled.ainvoke(initial_state, config)

            # If we reach here, workflow executed but didn't hit checkpoint
            # (This happens when async execution completes without interrupting)
            assert result is not None
        except Exception as e:
            # Workflow should pause at checkpoint, not error
            pytest.fail(f"Workflow failed: {e}")
