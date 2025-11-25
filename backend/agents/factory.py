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

    async def get_agent(
        self,
        role: str,
        name: str,
        workspace_path: Optional[str] = None,
        display_name: str = None
    ) -> AgentInterface:
        """Get or create an agent"""
        agent_key = f"{role}_{name}"

        if agent_key in self._agents:
            agent = self._agents[agent_key]
            # Always update display_name if provided (cached agents may not have it)
            if display_name:
                agent.display_name = display_name
            return agent

        # Determine timeout based on role
        timeout = self._get_timeout_for_role(role)

        # Create new agent
        if self._use_mocks:
            agent = MockAgent(name=name, agent_type="mock", role=role, workspace_path=workspace_path)
            agent.display_name = display_name or name
        else:
            # Create real CLI agents based on agent name
            agent = self._create_cli_agent(name, role, workspace_path, timeout, display_name)

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

    def _create_cli_agent(
        self,
        name: str,
        role: str,
        workspace_path: Optional[str],
        timeout: int,
        display_name: str = None
    ) -> AgentInterface:
        """
        Create a CLI agent based on the agent name.

        Args:
            name: Agent name (e.g., "claude_planner", "codex_reviewer")
            role: Agent role (e.g., "planning", "review", "summary")
            workspace_path: Path to the workspace
            timeout: Timeout in seconds for this agent
            display_name: Human-friendly name for UI display

        Returns:
            CLI agent instance
        """
        # Roles that should not execute code
        restricted_roles = ("planning", "review", "summary")

        # Determine agent type from name prefix
        if name.startswith("claude"):
            # Note: --permission-mode plan is NOT used because it causes Claude to
            # create plan files instead of responding with content. Our "planning agent"
            # outputs plans as text, it doesn't use Claude's internal planning feature.
            return ClaudeAgent(
                name=name,
                role=role,
                workspace_path=workspace_path,
                timeout=timeout,
                plan_mode=False,  # Don't use --permission-mode plan
                display_name=display_name
            )
        elif name.startswith("codex"):
            # Enable suggest mode for review role (no auto-edits)
            suggest_mode = (role in restricted_roles)
            if suggest_mode:
                logger.info(f"[Factory] Creating Codex agent '{name}' with suggest mode enabled")
            return CodexAgent(
                name=name,
                role=role,
                workspace_path=workspace_path,
                timeout=timeout,
                suggest_mode=suggest_mode,
                display_name=display_name
            )
        elif name.startswith("gemini"):
            # Disable yolo mode for review role (no auto-approve)
            yolo_mode = (role not in restricted_roles)
            if not yolo_mode:
                logger.info(f"[Factory] Creating Gemini agent '{name}' with yolo mode disabled")
            return GeminiAgent(
                name=name,
                role=role,
                workspace_path=workspace_path,
                timeout=timeout,
                yolo_mode=yolo_mode,
                display_name=display_name
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
        """Get all review agents with friendly display names"""
        # All reviewers now use file-based stdout transport (handles 10KB+ responses)
        # Format: (role, name, display_name)
        review_agent_configs = [
            ("review", "claude_reviewer", "Review Agent 1 (Claude)"),
            ("review", "codex_reviewer", "Review Agent 2 (Codex)"),
            ("review", "gemini_reviewer", "Review Agent 3 (Gemini)")
        ]

        agents = []
        for role, name, display_name in review_agent_configs:
            agent = await self.get_agent(role, name, workspace_path=workspace_path, display_name=display_name)
            agents.append(agent)

        return agents

    async def get_summary_agent(self, workspace_path: Optional[str] = None) -> AgentInterface:
        """Get the summary agent for consolidating review feedback"""
        # Use Claude for summary as it excels at synthesis tasks
        return await self.get_agent(
            "summary",
            "claude_summary",
            workspace_path=workspace_path,
            display_name="Review Summary (Claude)"
        )

    async def stop_all(self):
        """Stop all agents"""
        for agent in self._agents.values():
            await agent.stop()
        self._agents.clear()

# Global instance
agent_factory = AgentFactory()
