from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime

class AgentConfig(BaseModel):
    name: str
    agent_type: str
    role: str  # "planning", "review", "implementation"
    config: Optional[dict[str, Any]] = None

class AgentStatus(BaseModel):
    name: str
    type: str
    status: str
    port: Optional[int] = None
    pid: Optional[int] = None
    started_at: Optional[datetime] = None
