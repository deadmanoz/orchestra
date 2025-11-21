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
        workflow_data = active_workflows[workflow_id]
        compiled_workflow = workflow_data["compiled"]
        config = {"configurable": {"thread_id": workflow_id}}

        # Get current state from LangGraph checkpoint
        try:
            # Use async method since we're using AsyncSqliteSaver
            state = await compiled_workflow.aget_state(config)
            print(f"[API] State for {workflow_id}: has interrupts={bool(state.interrupts if state else False)}")

            # LangGraph stores interrupt data in state.interrupts (tuple of Interrupt objects)
            # NOT in state.values['__interrupt__']
            if state and hasattr(state, 'interrupts') and state.interrupts:
                # interrupts is a tuple, take the first one
                interrupt_obj = state.interrupts[0]
                print(f"[API] Found interrupt object: {type(interrupt_obj)}")

                # Extract the value from the Interrupt object
                if hasattr(interrupt_obj, 'value'):
                    pending_checkpoint = interrupt_obj.value
                    print(f"[API] ✓ Extracted checkpoint data, keys: {pending_checkpoint.keys() if isinstance(pending_checkpoint, dict) else 'not a dict'}")
                else:
                    print(f"[API] Interrupt object has no 'value' attribute")
            else:
                print(f"[API] No interrupts in state (state={state is not None}, has_attr={hasattr(state, 'interrupts') if state else False}, interrupts={state.interrupts if state and hasattr(state, 'interrupts') else None})")
        except Exception as e:
            print(f"[API] Error getting checkpoint state: {e}")
            import traceback
            traceback.print_exc()

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
    """Get full checkpoint history for workflow with enriched plan/review data"""

    if workflow_id not in active_workflows:
        raise HTTPException(status_code=404, detail="Workflow not found")

    compiled_workflow = active_workflows[workflow_id]["compiled"]
    config = {"configurable": {"thread_id": workflow_id}}

    # Get checkpoint history from LangGraph
    history = []
    try:
        # get_state_history returns states in reverse chronological order (newest first)
        # We'll reverse it to show oldest→newest for timeline display
        states_list = []
        async for state in compiled_workflow.aget_state_history(config):
            states_list.append(state)

        # Reverse to get chronological order
        states_list.reverse()

        for idx, state in enumerate(states_list):
            # Extract useful data from state
            state_values = state.values if state else {}

            # Determine step type based on state content
            step_type = "unknown"
            step_name = f"Step {idx + 1}"

            if "current_plan" in state_values:
                step_type = "plan"
                step_name = f"Plan (Iteration {state_values.get('iteration_count', 0)})"
            elif "reviews" in state_values and state_values["reviews"]:
                step_type = "review"
                step_name = f"Review {len(state_values['reviews'])} agents"

            # Extract relevant data for timeline display
            history_item = {
                "checkpoint_id": str(state.config.get("configurable", {}).get("checkpoint_id", "unknown")),
                "step_number": idx + 1,
                "step_type": step_type,
                "step_name": step_name,
                "iteration_count": state_values.get("iteration_count", 0),
                "checkpoint_number": state_values.get("checkpoint_number", 0),
                "created_at": state.created_at.isoformat() if state.created_at else None,
                "next_step": list(state.next) if state.next else [],

                # Include plan/review data for inspection
                "current_plan": state_values.get("current_plan", ""),
                "reviews": state_values.get("reviews", []),
                "instructions": state_values.get("instructions", ""),
                "actions": state_values.get("actions", []),
            }

            history.append(history_item)
    except Exception as e:
        print(f"Error getting history: {e}")
        import traceback
        traceback.print_exc()
        history = []

    return {"workflow_id": workflow_id, "history": history}
