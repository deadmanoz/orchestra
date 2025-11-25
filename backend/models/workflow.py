from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime
from enum import Enum

class WorkflowStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    AWAITING_CHECKPOINT = "awaiting_checkpoint"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class WorkflowType(str, Enum):
    PLAN_REVIEW = "plan_review"
    IMPLEMENTATION = "implementation"
    CUSTOM = "custom"

class WorkflowCreate(BaseModel):
    name: str
    type: WorkflowType
    initial_prompt: str
    workspace_path: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None

class WorkflowResponse(BaseModel):
    id: str
    name: str
    type: str
    status: str
    workspace_path: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    metadata: Optional[dict[str, Any]] = None
    result: Optional[dict[str, Any]] = None

class MessageResponse(BaseModel):
    id: int
    workflow_id: str
    role: str
    content: str
    agent_name: Optional[str] = None
    created_at: datetime
    metadata: Optional[dict[str, Any]] = None

class AgentExecutionResponse(BaseModel):
    id: int
    workflow_id: str
    agent_name: str
    agent_type: str
    input_content: str
    output_content: Optional[str] = None
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    execution_time_ms: Optional[int] = None
    cost_usd: Optional[float] = None
    metadata: Optional[dict[str, Any]] = None

class WorkflowStateSnapshot(BaseModel):
    """Current state of workflow including pending checkpoint"""
    workflow: WorkflowResponse
    pending_checkpoint: Optional[dict] = None
    recent_messages: list[MessageResponse] = []
    agent_executions: list[AgentExecutionResponse] = []
    current_iteration: int = 0  # Current iteration count from workflow state
