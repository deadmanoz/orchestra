from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime
from enum import Enum

class CheckpointStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EDITED = "edited"

class CheckpointResponse(BaseModel):
    id: str
    workflow_id: str
    checkpoint_number: int
    step_name: str
    agent_outputs: list[dict]
    user_edited_content: Optional[str] = None
    user_notes: Optional[str] = None
    status: str
    created_at: datetime
    resolved_at: Optional[datetime] = None

class CheckpointResolution(BaseModel):
    action: Literal["approve", "edit", "reject"]
    edited_content: Optional[str] = None
    user_notes: Optional[str] = None
