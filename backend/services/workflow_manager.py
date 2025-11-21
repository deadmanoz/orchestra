"""
Workflow Status Management Service

Centralizes all workflow status transitions, ensuring atomic updates,
validation, and proper audit trails.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum

from backend.models.workflow import WorkflowStatus
from backend.db.connection import db
from backend.api.websocket import broadcast_to_workflow

logger = logging.getLogger(__name__)


class StatusTransition(Enum):
    """Valid workflow status transitions"""
    # From PENDING
    PENDING_TO_RUNNING = ("pending", "running")

    # From RUNNING
    RUNNING_TO_AWAITING = ("running", "awaiting_checkpoint")
    RUNNING_TO_COMPLETED = ("running", "completed")
    RUNNING_TO_FAILED = ("running", "failed")
    RUNNING_TO_CANCELLED = ("running", "cancelled")

    # From AWAITING_CHECKPOINT
    AWAITING_TO_RUNNING = ("awaiting_checkpoint", "running")
    AWAITING_TO_COMPLETED = ("awaiting_checkpoint", "completed")
    AWAITING_TO_FAILED = ("awaiting_checkpoint", "failed")
    AWAITING_TO_CANCELLED = ("awaiting_checkpoint", "cancelled")


class WorkflowStatusManager:
    """
    Manages workflow status transitions with validation and atomic updates.

    Ensures:
    - Valid state transitions (enforces state machine)
    - Atomic updates (memory + database)
    - WebSocket notifications
    - Proper logging and audit trail
    - Memory cleanup on terminal states
    """

    def __init__(self, active_workflows: Dict[str, Any]):
        """
        Initialize the status manager.

        Args:
            active_workflows: Reference to in-memory workflows dict
        """
        self.active_workflows = active_workflows
        self._valid_transitions = self._build_transition_map()

    def _build_transition_map(self) -> Dict[str, set]:
        """Build valid state transition map from enum"""
        transitions = {}
        for transition in StatusTransition:
            from_state, to_state = transition.value
            if from_state not in transitions:
                transitions[from_state] = set()
            transitions[from_state].add(to_state)
        return transitions

    def validate_transition(self, workflow_id: str, to_status: str) -> bool:
        """
        Validate if status transition is allowed.

        Args:
            workflow_id: The workflow ID
            to_status: Target status

        Returns:
            True if transition is valid, False otherwise
        """
        if workflow_id not in self.active_workflows:
            logger.warning(f"Workflow {workflow_id} not in active workflows")
            return False

        current_status = self.active_workflows[workflow_id].get("status")

        # Allow any transition if current state unknown (defensive)
        if not current_status:
            logger.warning(f"Workflow {workflow_id} has no current status, allowing transition to {to_status}")
            return True

        # Check if transition is valid
        valid_next_states = self._valid_transitions.get(current_status, set())
        is_valid = to_status in valid_next_states

        if not is_valid:
            logger.error(
                f"Invalid status transition for workflow {workflow_id}: "
                f"{current_status} -> {to_status}"
            )

        return is_valid

    async def mark_awaiting_checkpoint(
        self,
        workflow_id: str,
        result: dict,
        validate: bool = True
    ) -> None:
        """
        Mark workflow as awaiting checkpoint with atomic updates.

        Args:
            workflow_id: The workflow ID
            result: LangGraph result containing checkpoint data
            validate: Whether to validate state transition (default: True)

        Raises:
            ValueError: If transition is invalid and validate=True
        """
        target_status = WorkflowStatus.AWAITING_CHECKPOINT.value

        # Validate transition
        if validate and not self.validate_transition(workflow_id, target_status):
            current = self.active_workflows[workflow_id].get("status", "unknown")
            raise ValueError(
                f"Invalid transition: {current} -> {target_status} for workflow {workflow_id}"
            )

        logger.info(f"Marking workflow {workflow_id} as awaiting checkpoint")

        # Update memory state
        self.active_workflows[workflow_id]["status"] = target_status
        self.active_workflows[workflow_id]["last_result"] = result

        # Update database atomically
        async with db.get_connection() as conn:
            await conn.execute(
                "UPDATE workflows SET status = ?, updated_at = ? WHERE id = ?",
                (target_status, datetime.now().isoformat(), workflow_id)
            )
            await conn.commit()

        logger.debug(f"Database updated for workflow {workflow_id}")

        # Notify frontend via WebSocket
        await broadcast_to_workflow(workflow_id, {
            "type": "checkpoint_ready",
            "workflow_id": workflow_id,
            "timestamp": datetime.now().isoformat()
        })

        logger.info(f"Workflow {workflow_id} marked as awaiting checkpoint successfully")

    async def mark_completed(self, workflow_id: str, validate: bool = True) -> None:
        """
        Mark workflow as completed with atomic updates and cleanup.

        Args:
            workflow_id: The workflow ID
            validate: Whether to validate state transition (default: True)

        Raises:
            ValueError: If transition is invalid and validate=True
        """
        target_status = WorkflowStatus.COMPLETED.value

        # Validate transition
        if validate and not self.validate_transition(workflow_id, target_status):
            current = self.active_workflows[workflow_id].get("status", "unknown")
            raise ValueError(
                f"Invalid transition: {current} -> {target_status} for workflow {workflow_id}"
            )

        logger.info(f"Marking workflow {workflow_id} as completed")

        # Update memory state
        self.active_workflows[workflow_id]["status"] = target_status

        # Update database atomically
        async with db.get_connection() as conn:
            await conn.execute(
                "UPDATE workflows SET status = ?, completed_at = ?, updated_at = ? WHERE id = ?",
                (target_status, datetime.now().isoformat(),
                 datetime.now().isoformat(), workflow_id)
            )
            await conn.commit()

        logger.debug(f"Database updated for workflow {workflow_id}")

        # Notify frontend
        await broadcast_to_workflow(workflow_id, {
            "type": "workflow_completed",
            "workflow_id": workflow_id,
            "timestamp": datetime.now().isoformat()
        })

        # Clean up active workflows (terminal state)
        if workflow_id in self.active_workflows:
            del self.active_workflows[workflow_id]
            logger.debug(f"Cleaned up workflow {workflow_id} from active workflows")

        logger.info(f"Workflow {workflow_id} marked as completed successfully")

    async def mark_failed(
        self,
        workflow_id: str,
        error: Exception,
        validate: bool = True
    ) -> None:
        """
        Mark workflow as failed with atomic updates and cleanup.

        Args:
            workflow_id: The workflow ID
            error: The exception that caused the failure
            validate: Whether to validate state transition (default: True)

        Raises:
            ValueError: If transition is invalid and validate=True
        """
        target_status = WorkflowStatus.FAILED.value
        error_message = str(error)

        # Validate transition
        if validate and not self.validate_transition(workflow_id, target_status):
            current = self.active_workflows.get(workflow_id, {}).get("status", "unknown")
            logger.warning(
                f"Invalid transition: {current} -> {target_status} for workflow {workflow_id}, "
                f"but allowing due to error condition"
            )
            # Don't raise error - we want to record failures even if transition is invalid

        logger.error(f"Marking workflow {workflow_id} as failed: {error_message}")

        # Update memory state
        if workflow_id in self.active_workflows:
            self.active_workflows[workflow_id]["status"] = target_status
            self.active_workflows[workflow_id]["error"] = error_message

        # Update database atomically
        async with db.get_connection() as conn:
            await conn.execute(
                "UPDATE workflows SET status = ?, updated_at = ? WHERE id = ?",
                (target_status, datetime.now().isoformat(), workflow_id)
            )
            await conn.commit()

        logger.debug(f"Database updated for workflow {workflow_id}")

        # Notify frontend
        await broadcast_to_workflow(workflow_id, {
            "type": "workflow_failed",
            "workflow_id": workflow_id,
            "error": error_message,
            "timestamp": datetime.now().isoformat()
        })

        # Clean up active workflows (terminal state)
        if workflow_id in self.active_workflows:
            del self.active_workflows[workflow_id]
            logger.debug(f"Cleaned up workflow {workflow_id} from active workflows")

        logger.warning(f"Workflow {workflow_id} marked as failed")

    async def mark_running(self, workflow_id: str, validate: bool = True) -> None:
        """
        Mark workflow as running.

        Args:
            workflow_id: The workflow ID
            validate: Whether to validate state transition (default: True)

        Raises:
            ValueError: If transition is invalid and validate=True
        """
        target_status = WorkflowStatus.RUNNING.value

        # Validate transition
        if validate and not self.validate_transition(workflow_id, target_status):
            current = self.active_workflows[workflow_id].get("status", "unknown")
            raise ValueError(
                f"Invalid transition: {current} -> {target_status} for workflow {workflow_id}"
            )

        logger.info(f"Marking workflow {workflow_id} as running")

        # Update memory state
        self.active_workflows[workflow_id]["status"] = target_status

        # Update database atomically
        async with db.get_connection() as conn:
            await conn.execute(
                "UPDATE workflows SET status = ?, updated_at = ? WHERE id = ?",
                (target_status, datetime.now().isoformat(), workflow_id)
            )
            await conn.commit()

        logger.info(f"Workflow {workflow_id} marked as running")

    def get_status(self, workflow_id: str) -> Optional[str]:
        """
        Get current workflow status.

        Args:
            workflow_id: The workflow ID

        Returns:
            Current status or None if workflow not found
        """
        if workflow_id not in self.active_workflows:
            return None
        return self.active_workflows[workflow_id].get("status")
