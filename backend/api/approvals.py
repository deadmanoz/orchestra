"""
Implementation Approval API

Spike: Proof-of-concept for Claude Code hook-based implementation approval.

This API allows Claude Code hooks to:
1. Request approval for file modifications (Write, Edit, Bash)
2. Poll for user decisions
3. Receive approve/deny responses

Flow:
1. Claude Code hook intercepts Write/Edit/Bash tool call
2. Hook POSTs to /api/approvals/request with tool details
3. Frontend displays approval request to user
4. User approves/denies via /api/approvals/{id}/resolve
5. Hook polls /api/approvals/{id} until resolved
6. Hook returns exit code 0 (allow) or 2 (deny)
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime
import uuid
import asyncio
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/approvals", tags=["approvals"])

# In-memory store for pending approvals (replace with Redis in production)
pending_approvals: dict[str, dict] = {}


class ApprovalRequest(BaseModel):
    """Request from Claude Code hook for tool approval"""
    workflow_id: str
    tool_name: str  # e.g., "Write", "Edit", "Bash"
    tool_input: dict  # The tool's input parameters
    file_path: Optional[str] = None  # Extracted for convenience
    content_preview: Optional[str] = None  # First N chars of content


class ApprovalResponse(BaseModel):
    """Response to hook with approval ID"""
    approval_id: str
    status: Literal["pending", "approved", "denied"]
    message: str


class ApprovalStatus(BaseModel):
    """Status of an approval request"""
    approval_id: str
    workflow_id: str
    tool_name: str
    tool_input: dict
    file_path: Optional[str]
    content_preview: Optional[str]
    status: Literal["pending", "approved", "denied"]
    user_message: Optional[str] = None  # Message from user on deny
    created_at: str
    resolved_at: Optional[str] = None


class ApprovalResolution(BaseModel):
    """User's decision on an approval request"""
    decision: Literal["approve", "deny"]
    message: Optional[str] = None  # Optional message (e.g., reason for deny)


@router.post("/request", response_model=ApprovalResponse)
async def request_approval(request: ApprovalRequest):
    """
    Request approval for a tool call.

    Called by Claude Code hook when intercepting Write/Edit/Bash.
    Returns immediately with approval_id for polling.
    """
    approval_id = f"apr-{uuid.uuid4().hex[:12]}"

    # Extract file_path from tool_input if not provided
    file_path = request.file_path
    if not file_path:
        file_path = request.tool_input.get("file_path") or request.tool_input.get("path")

    # Create content preview
    content_preview = request.content_preview
    if not content_preview:
        content = request.tool_input.get("content") or request.tool_input.get("command", "")
        if content:
            content_preview = content[:500] + ("..." if len(content) > 500 else "")

    # Store approval request
    pending_approvals[approval_id] = {
        "approval_id": approval_id,
        "workflow_id": request.workflow_id,
        "tool_name": request.tool_name,
        "tool_input": request.tool_input,
        "file_path": file_path,
        "content_preview": content_preview,
        "status": "pending",
        "user_message": None,
        "created_at": datetime.now().isoformat(),
        "resolved_at": None
    }

    logger.info(f"[Approval] Created approval request {approval_id} for {request.tool_name} on {file_path}")

    return ApprovalResponse(
        approval_id=approval_id,
        status="pending",
        message=f"Approval request created. Poll /api/approvals/{approval_id} for status."
    )


@router.get("/{approval_id}", response_model=ApprovalStatus)
async def get_approval_status(approval_id: str):
    """
    Get status of an approval request.

    Hook polls this endpoint until status is "approved" or "denied".
    """
    if approval_id not in pending_approvals:
        raise HTTPException(status_code=404, detail="Approval request not found")

    return ApprovalStatus(**pending_approvals[approval_id])


@router.post("/{approval_id}/resolve", response_model=ApprovalStatus)
async def resolve_approval(approval_id: str, resolution: ApprovalResolution):
    """
    Resolve an approval request (approve or deny).

    Called by frontend when user makes a decision.
    """
    if approval_id not in pending_approvals:
        raise HTTPException(status_code=404, detail="Approval request not found")

    approval = pending_approvals[approval_id]

    if approval["status"] != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Approval already resolved with status: {approval['status']}"
        )

    # Update approval status
    approval["status"] = "approved" if resolution.decision == "approve" else "denied"
    approval["user_message"] = resolution.message
    approval["resolved_at"] = datetime.now().isoformat()

    logger.info(f"[Approval] Resolved {approval_id}: {approval['status']}")

    return ApprovalStatus(**approval)


@router.get("/workflow/{workflow_id}/pending")
async def get_pending_approvals(workflow_id: str):
    """
    Get all pending approvals for a workflow.

    Used by frontend to display approval requests.
    """
    pending = [
        ApprovalStatus(**approval)
        for approval in pending_approvals.values()
        if approval["workflow_id"] == workflow_id and approval["status"] == "pending"
    ]

    return {"workflow_id": workflow_id, "pending_approvals": pending}


@router.post("/{approval_id}/wait", response_model=ApprovalStatus)
async def wait_for_approval(approval_id: str, timeout_seconds: int = 300):
    """
    Long-poll endpoint that waits for approval resolution.

    Alternative to polling - hook can call this and it will block until
    the approval is resolved or timeout is reached.

    Args:
        approval_id: The approval request ID
        timeout_seconds: Max time to wait (default 5 minutes)

    Returns:
        ApprovalStatus when resolved or timeout
    """
    if approval_id not in pending_approvals:
        raise HTTPException(status_code=404, detail="Approval request not found")

    # Poll every second until resolved or timeout
    elapsed = 0
    poll_interval = 1  # seconds

    while elapsed < timeout_seconds:
        approval = pending_approvals[approval_id]

        if approval["status"] != "pending":
            return ApprovalStatus(**approval)

        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

    # Timeout - return current status (still pending)
    return ApprovalStatus(**pending_approvals[approval_id])
