import logging
from typing import Optional, List

from backend.agents.base import AgentInterface
from backend.agents.mock_agent import MockAgent
from backend.agents.claude_agent import ClaudeAgent
from backend.agents.codex_agent import CodexAgent
from backend.agents.gemini_agent import GeminiAgent
from backend.config import settings

logger = logging.getLogger(__name__)

class AgentFactory:
    """Factory for creating and managing agents"""

    def __init__(self):
        self._agents: dict[str, AgentInterface] = {}
        self._use_mocks = settings.use_mock_agents

    async def get_agent(self, role: str, name: str, workspace_path: Optional[str] = None) -> AgentInterface:
        """Get or create an agent"""
        agent_key = f"{role}_{name}"

        if agent_key in self._agents:
            return self._agents[agent_key]

        # Create new agent
        if self._use_mocks:
            agent = MockAgent(name=name, agent_type="mock", role=role, workspace_path=workspace_path)
        else:
            # Create real CLI agents based on agent name
            agent = self._create_cli_agent(name, role, workspace_path)

        await agent.start()
        self._agents[agent_key] = agent

        return agent

    def _create_cli_agent(self, name: str, role: str, workspace_path: Optional[str]) -> AgentInterface:
        """
        Create a CLI agent based on the agent name.

        Args:
            name: Agent name (e.g., "claude_planner", "codex_reviewer")
            role: Agent role (e.g., "planning", "review")
            workspace_path: Path to the workspace

        Returns:
            CLI agent instance
        """
        # Determine agent type from name prefix
        if name.startswith("claude"):
            return ClaudeAgent(
                name=name,
                role=role,
                workspace_path=workspace_path
            )
        elif name.startswith("codex"):
            return CodexAgent(
                name=name,
                role=role,
                workspace_path=workspace_path
            )
        elif name.startswith("gemini"):
            return GeminiAgent(
                name=name,
                role=role,
                workspace_path=workspace_path
            )
        else:
            # Fallback to mock for unknown agent types
            logger.warning(f"Unknown agent type for '{name}', falling back to MockAgent")
            return MockAgent(
                name=name,
                agent_type="unknown",
                role=role,
                workspace_path=workspace_path
            )

    async def get_review_agents(self, workspace_path: Optional[str] = None) -> List[AgentInterface]:
        """Get all review agents"""
        # Test Gemini with file-based stdout transport
        review_agent_configs = [
            # ("review", "claude_reviewer"),  # Disabled - not tested with file transport yet
            # ("review", "codex_reviewer"),  # Disabled - already works, testing Gemini now
            ("review", "gemini_reviewer")   # ACTIVE: Testing with file-based stdout
        ]

        agents = []
        for role, name in review_agent_configs:
            agent = await self.get_agent(role, name, workspace_path=workspace_path)
            agents.append(agent)

        return agents

    async def stop_all(self):
        """Stop all agents"""
        for agent in self._agents.values():
            await agent.stop()
        self._agents.clear()

# Global instance
agent_factory = AgentFactory()
