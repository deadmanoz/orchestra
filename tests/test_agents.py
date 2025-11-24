"""Unit tests for agent system"""
import pytest
import asyncio

from backend.agents.base import AgentInterface
from backend.agents.mock_agent import MockAgent
from backend.agents.factory import AgentFactory
from backend.settings import settings


class TestMockAgent:
    """Test mock agent implementation"""

    @pytest.mark.asyncio
    async def test_mock_agent_initialization(self):
        """Test mock agent can be created"""
        agent = MockAgent(name="test_agent", agent_type="mock", role="planning")
        assert agent.name == "test_agent"
        assert agent.agent_type == "mock"
        assert agent.role == "planning"
        assert agent.status == "initialized"

    @pytest.mark.asyncio
    async def test_mock_agent_startup(self):
        """Test mock agent startup"""
        agent = MockAgent(name="test", agent_type="mock", role="planning")
        await agent.start()
        assert agent.status == "running"

    @pytest.mark.asyncio
    async def test_mock_agent_planning_response(self):
        """Test planning agent generates plan"""
        agent = MockAgent(name="planner", agent_type="mock", role="planning")
        await agent.start()

        response = await agent.send_message("Create a plan for a web app")

        assert isinstance(response, str)
        assert len(response) > 0
        assert "plan" in response.lower() or "phase" in response.lower()

    @pytest.mark.asyncio
    async def test_mock_agent_review_response(self):
        """Test review agent generates feedback"""
        agent = MockAgent(name="reviewer", agent_type="mock", role="review")
        await agent.start()

        response = await agent.send_message("Review this plan: Build a web app")

        assert isinstance(response, str)
        assert len(response) > 0
        assert "review" in response.lower() or "feedback" in response.lower()

    @pytest.mark.asyncio
    async def test_mock_agent_get_status(self):
        """Test getting agent status"""
        agent = MockAgent(name="test", agent_type="mock", role="planning")
        await agent.start()

        status = await agent.get_status()

        assert status["name"] == "test"
        assert status["type"] == "mock"
        assert status["status"] == "running"
        assert status["role"] == "planning"

    @pytest.mark.asyncio
    async def test_mock_agent_stop(self):
        """Test stopping agent"""
        agent = MockAgent(name="test", agent_type="mock", role="planning")
        await agent.start()
        await agent.stop()

        assert agent.status == "stopped"


class TestAgentFactory:
    """Test agent factory"""

    @pytest.mark.asyncio
    async def test_factory_create_agent(self):
        """Test factory creates agents"""
        factory = AgentFactory()

        agent = await factory.get_agent("planning", "test_planner")

        assert agent is not None
        assert agent.name == "test_planner"
        assert agent.status == "running"

    @pytest.mark.asyncio
    async def test_factory_reuses_agents(self):
        """Test factory reuses existing agents"""
        factory = AgentFactory()

        agent1 = await factory.get_agent("planning", "test_planner")
        agent2 = await factory.get_agent("planning", "test_planner")

        assert agent1 is agent2  # Same instance

    @pytest.mark.asyncio
    async def test_factory_creates_multiple_agents(self):
        """Test factory can create multiple different agents"""
        factory = AgentFactory()

        planner = await factory.get_agent("planning", "planner")
        reviewer = await factory.get_agent("review", "reviewer")

        assert planner is not reviewer
        assert planner.name == "planner"
        assert reviewer.name == "reviewer"

    @pytest.mark.asyncio
    async def test_factory_get_review_agents(self):
        """Test factory returns multiple review agents"""
        factory = AgentFactory()

        review_agents = await factory.get_review_agents()

        assert len(review_agents) == 3  # claude, codex, gemini reviewers
        assert all(agent.status == "running" for agent in review_agents)

    @pytest.mark.asyncio
    async def test_factory_stop_all(self):
        """Test factory can stop all agents"""
        factory = AgentFactory()

        # Create some agents
        await factory.get_agent("planning", "planner")
        await factory.get_agent("review", "reviewer")

        # Stop all
        await factory.stop_all()

        # Factory should be empty
        assert len(factory._agents) == 0


class TestAgentInterface:
    """Test agent interface compliance"""

    def test_mock_agent_implements_interface(self):
        """Test MockAgent implements AgentInterface"""
        assert issubclass(MockAgent, AgentInterface)

    @pytest.mark.asyncio
    async def test_interface_methods_exist(self):
        """Test all interface methods are implemented"""
        agent = MockAgent("test", "mock", "planning")

        # Check all required methods exist
        assert hasattr(agent, "start")
        assert hasattr(agent, "send_message")
        assert hasattr(agent, "get_status")
        assert hasattr(agent, "stop")

        # Check they're callable
        assert callable(agent.start)
        assert callable(agent.send_message)
        assert callable(agent.get_status)
        assert callable(agent.stop)
