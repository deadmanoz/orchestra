from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Optional
import uuid
import asyncio
from datetime import datetime
import json
import aiosqlite
import os
from pathlib import Path

from backend.models.workflow import (
    WorkflowCreate, WorkflowResponse, WorkflowStateSnapshot, WorkflowStatus
)
from backend.workflows.plan_review import PlanReviewWorkflow
from backend.agents.factory import agent_factory
from backend.db.connection import db
from langchain_core.messages import HumanMessage
from langgraph.types import Command

router = APIRouter(prefix="/api/workflows", tags=["workflows"])

# In-memory store for active workflows (replace with Redis in production)
active_workflows = {}

def validate_workspace_path(workspace_path: Optional[str]) -> Optional[str]:
    """Validate and resolve workspace path"""
    if not workspace_path:
        return None

    # Resolve to absolute path
    resolved_path = Path(workspace_path).resolve()

    # Check if path exists and is a directory
    if not resolved_path.exists():
        raise HTTPException(status_code=400, detail=f"Workspace path does not exist: {workspace_path}")

    if not resolved_path.is_dir():
        raise HTTPException(status_code=400, detail=f"Workspace path is not a directory: {workspace_path}")

    # Convert to string
    return str(resolved_path)

@router.post("", response_model=WorkflowResponse)
async def create_workflow(
    workflow_create: WorkflowCreate,
    background_tasks: BackgroundTasks
):
    """Create and start a new workflow"""
    workflow_id = f"wf-{uuid.uuid4().hex[:12]}"

    # Validate workspace path
    workspace_path = validate_workspace_path(workflow_create.workspace_path)

    # Save to database
    async with db.get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO workflows (id, name, type, status, workspace_path, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                workflow_id,
                workflow_create.name,
                workflow_create.type.value,
                WorkflowStatus.RUNNING.value,
                workspace_path,
                datetime.now().isoformat(),
                datetime.now().isoformat()
            )
        )
        await conn.commit()

    # Create workflow instance
    if workflow_create.type.value == "plan_review":
        workflow = PlanReviewWorkflow(agent_factory, workspace_path=workspace_path)
        await workflow.setup()  # Initialize async checkpointer
        compiled_workflow = workflow.compile()
    else:
        raise HTTPException(status_code=400, detail="Unsupported workflow type")

    # Store in active workflows
    active_workflows[workflow_id] = {
        "compiled": compiled_workflow,
        "instance": workflow,
        "status": WorkflowStatus.RUNNING.value
    }

    # Start workflow execution in background
    background_tasks.add_task(
        execute_workflow,
        workflow_id,
        compiled_workflow,
        workflow_create.initial_prompt
    )

    return WorkflowResponse(
        id=workflow_id,
        name=workflow_create.name,
        type=workflow_create.type.value,
        status=WorkflowStatus.RUNNING.value,
        workspace_path=workspace_path,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )

async def execute_workflow(
    workflow_id: str,
    compiled_workflow,
    initial_prompt: str
):
    """Execute workflow until first checkpoint"""
    try:
        config = {"configurable": {"thread_id": workflow_id}}

        initial_state = {
            "workflow_id": workflow_id,
            "messages": [HumanMessage(content=initial_prompt)],
            "iteration_count": 0,
            "checkpoint_number": 0,
            "status": "starting"
        }

        # This will run until first interrupt() - use async API
        result = await compiled_workflow.ainvoke(
            initial_state,
            config
        )

        # Update workflow status
        active_workflows[workflow_id]["status"] = WorkflowStatus.AWAITING_CHECKPOINT.value
        active_workflows[workflow_id]["last_result"] = result

        # Update database
        async with db.get_connection() as conn:
            await conn.execute(
                "UPDATE workflows SET status = ?, updated_at = ? WHERE id = ?",
                (WorkflowStatus.AWAITING_CHECKPOINT.value, datetime.now().isoformat(), workflow_id)
            )
            await conn.commit()

    except Exception as e:
        print(f"Workflow {workflow_id} failed: {e}")
        import traceback
        traceback.print_exc()
        active_workflows[workflow_id]["status"] = WorkflowStatus.FAILED.value
        active_workflows[workflow_id]["error"] = str(e)

@router.get("/{workflow_id}", response_model=WorkflowStateSnapshot)
async def get_workflow(workflow_id: str):
    """Get current workflow state including pending checkpoint"""

    # Get workflow from database
    async with db.get_connection() as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT * FROM workflows WHERE id = ?",
            (workflow_id,)
        )
        workflow_row = await cursor.fetchone()

        if not workflow_row:
            raise HTTPException(status_code=404, detail="Workflow not found")

    # Get LangGraph checkpoint data
    pending_checkpoint = None
    if workflow_id in active_workflows:
        last_result = active_workflows[workflow_id].get("last_result")
        if last_result:
            # LangGraph interrupt returns data in specific format
            pending_checkpoint = last_result

    workflow_dict = dict(workflow_row)
    # Convert string timestamps to datetime
    workflow_dict['created_at'] = datetime.fromisoformat(workflow_dict['created_at'])
    workflow_dict['updated_at'] = datetime.fromisoformat(workflow_dict['updated_at'])

    return WorkflowStateSnapshot(
        workflow=WorkflowResponse(**workflow_dict),
        pending_checkpoint=pending_checkpoint,
        recent_messages=[]
    )

@router.post("/{workflow_id}/resume")
async def resume_workflow(
    workflow_id: str,
    resolution: dict,
    background_tasks: BackgroundTasks
):
    """Resume workflow after checkpoint resolution"""

    if workflow_id not in active_workflows:
        raise HTTPException(status_code=404, detail="Workflow not found")

    compiled_workflow = active_workflows[workflow_id]["compiled"]
    config = {"configurable": {"thread_id": workflow_id}}

    # Resume with user input
    background_tasks.add_task(
        resume_workflow_execution,
        workflow_id,
        compiled_workflow,
        config,
        resolution
    )

    return {"status": "resuming", "workflow_id": workflow_id}

async def resume_workflow_execution(
    workflow_id: str,
    compiled_workflow,
    config: dict,
    resolution: dict
):
    """Resume workflow execution after human input"""
    try:
        # Resume with Command - use async API
        result = await compiled_workflow.ainvoke(
            Command(resume=resolution),
            config
        )

        # Check if workflow completed or hit another checkpoint
        if result:
            active_workflows[workflow_id]["status"] = WorkflowStatus.AWAITING_CHECKPOINT.value
            active_workflows[workflow_id]["last_result"] = result
        else:
            # Workflow completed
            active_workflows[workflow_id]["status"] = WorkflowStatus.COMPLETED.value

            async with db.get_connection() as conn:
                await conn.execute(
                    "UPDATE workflows SET status = ?, completed_at = ?, updated_at = ? WHERE id = ?",
                    (WorkflowStatus.COMPLETED.value, datetime.now().isoformat(),
                     datetime.now().isoformat(), workflow_id)
                )
                await conn.commit()

    except Exception as e:
        print(f"Resume failed for {workflow_id}: {e}")
        import traceback
        traceback.print_exc()
        active_workflows[workflow_id]["status"] = WorkflowStatus.FAILED.value
        active_workflows[workflow_id]["error"] = str(e)

@router.get("/{workflow_id}/history")
async def get_workflow_history(workflow_id: str):
    """Get full checkpoint history for workflow"""

    if workflow_id not in active_workflows:
        raise HTTPException(status_code=404, detail="Workflow not found")

    compiled_workflow = active_workflows[workflow_id]["compiled"]
    config = {"configurable": {"thread_id": workflow_id}}

    # Get checkpoint history from LangGraph
    history = []
    try:
        for state in compiled_workflow.get_state_history(config):
            history.append({
                "checkpoint_id": str(state.config.get("checkpoint_id", "unknown")),
                "state": state.values,
                "next_step": list(state.next) if state.next else [],
                "created_at": state.created_at.isoformat() if state.created_at else None
            })
    except Exception as e:
        print(f"Error getting history: {e}")
        history = []

    return {"workflow_id": workflow_id, "history": history}
