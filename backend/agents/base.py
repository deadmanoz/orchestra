from abc import ABC, abstractmethod
from typing import Optional, Any

class AgentInterface(ABC):
    """Base interface for all agents"""

    def __init__(self, name: str, agent_type: str, display_name: str = None):
        self.name = name
        self.agent_type = agent_type
        self.display_name = display_name or name
        self.status = "initialized"

    @abstractmethod
    async def start(self) -> None:
        """Start the agent (if needed)"""
        pass

    @abstractmethod
    async def send_message(self, content: str, **kwargs) -> str:
        """Send message to agent and get response"""
        pass

    @abstractmethod
    async def get_status(self) -> dict:
        """Get agent status"""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop the agent"""
        pass
