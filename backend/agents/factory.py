import logging
from typing import Optional, List

from backend.agents.base import AgentInterface
from backend.agents.mock_agent import MockAgent
from backend.agents.claude_agent import ClaudeAgent
from backend.agents.codex_agent import CodexAgent
from backend.agents.gemini_agent import GeminiAgent
from backend.settings import settings

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

        # Determine timeout based on role
        timeout = self._get_timeout_for_role(role)

        # Create new agent
        if self._use_mocks:
            agent = MockAgent(name=name, agent_type="mock", role=role, workspace_path=workspace_path)
        else:
            # Create real CLI agents based on agent name
            agent = self._create_cli_agent(name, role, workspace_path, timeout)

        await agent.start()
        self._agents[agent_key] = agent

        return agent

    def _get_timeout_for_role(self, role: str) -> int:
        """Get timeout based on agent role"""
        if role == "planning":
            return settings.planning_agent_timeout
        elif role == "review":
            return settings.review_agent_timeout
        elif role == "summary":
            return settings.summary_agent_timeout
        else:
            return settings.agent_timeout

    def _create_cli_agent(self, name: str, role: str, workspace_path: Optional[str], timeout: int) -> AgentInterface:
        """
        Create a CLI agent based on the agent name.

        Args:
            name: Agent name (e.g., "claude_planner", "codex_reviewer")
            role: Agent role (e.g., "planning", "review")
            workspace_path: Path to the workspace
            timeout: Timeout in seconds for this agent

        Returns:
            CLI agent instance
        """
        # Determine agent type from name prefix
        if name.startswith("claude"):
            # Enable plan mode for planning role to prevent accidental code execution
            plan_mode = (role == "planning")
            if plan_mode:
                logger.info(f"[Factory] Creating Claude agent '{name}' with plan mode enabled")
            return ClaudeAgent(
                name=name,
                role=role,
                workspace_path=workspace_path,
                timeout=timeout,
                plan_mode=plan_mode
            )
        elif name.startswith("codex"):
            return CodexAgent(
                name=name,
                role=role,
                workspace_path=workspace_path,
                timeout=timeout
            )
        elif name.startswith("gemini"):
            return GeminiAgent(
                name=name,
                role=role,
                workspace_path=workspace_path,
                timeout=timeout
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
        # All reviewers now use file-based stdout transport (handles 10KB+ responses)
        review_agent_configs = [
            ("review", "claude_reviewer"),  # Claude Code CLI
            ("review", "codex_reviewer"),   # Codex CLI
            ("review", "gemini_reviewer")   # Gemini CLI
        ]

        agents = []
        for role, name in review_agent_configs:
            agent = await self.get_agent(role, name, workspace_path=workspace_path)
            agents.append(agent)

        return agents

    async def get_summary_agent(self, workspace_path: Optional[str] = None) -> AgentInterface:
        """Get the summary agent for consolidating review feedback"""
        # Use Claude for summary as it excels at synthesis tasks
        return await self.get_agent("summary", "claude_summary", workspace_path=workspace_path)

    async def stop_all(self):
        """Stop all agents"""
        for agent in self._agents.values():
            await agent.stop()
        self._agents.clear()

# Global instance
agent_factory = AgentFactory()
