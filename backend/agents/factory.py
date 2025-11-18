from typing import Optional, List
from backend.agents.base import AgentInterface
from backend.agents.mock_agent import MockAgent
from backend.config import settings

class AgentFactory:
    """Factory for creating and managing agents"""

    def __init__(self):
        self._agents: dict[str, AgentInterface] = {}
        self._use_mocks = settings.use_mock_agents

    async def get_agent(self, role: str, name: str) -> AgentInterface:
        """Get or create an agent"""
        agent_key = f"{role}_{name}"

        if agent_key in self._agents:
            return self._agents[agent_key]

        # Create new agent
        if self._use_mocks:
            agent = MockAgent(name=name, agent_type="mock", role=role)
        else:
            # TODO: Create real CLI/API agents when ready
            agent = MockAgent(name=name, agent_type="mock", role=role)

        await agent.start()
        self._agents[agent_key] = agent

        return agent

    async def get_review_agents(self) -> List[AgentInterface]:
        """Get all review agents"""
        review_agent_configs = [
            ("review", "claude_reviewer"),
            ("review", "codex_reviewer"),
            ("review", "gemini_reviewer")
        ]

        agents = []
        for role, name in review_agent_configs:
            agent = await self.get_agent(role, name)
            agents.append(agent)

        return agents

    async def stop_all(self):
        """Stop all agents"""
        for agent in self._agents.values():
            await agent.stop()
        self._agents.clear()

# Global instance
agent_factory = AgentFactory()
