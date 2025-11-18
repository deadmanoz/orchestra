"""Unit tests for data models"""
import pytest
from datetime import datetime
from pydantic import ValidationError

from backend.models.workflow import (
    WorkflowCreate,
    WorkflowResponse,
    WorkflowStatus,
    WorkflowType,
    WorkflowStateSnapshot
)
from backend.models.checkpoint import (
    CheckpointResolution,
    CheckpointStatus
)
from backend.models.agent import AgentConfig, AgentStatus


class TestWorkflowModels:
    """Test workflow data models"""

    def test_workflow_create_valid(self):
        """Test creating a valid workflow"""
        workflow = WorkflowCreate(
            name="Test Workflow",
            type=WorkflowType.PLAN_REVIEW,
            initial_prompt="Create a plan"
        )
        assert workflow.name == "Test Workflow"
        assert workflow.type == WorkflowType.PLAN_REVIEW
        assert workflow.initial_prompt == "Create a plan"

    def test_workflow_create_with_metadata(self):
        """Test workflow creation with metadata"""
        workflow = WorkflowCreate(
            name="Test",
            type=WorkflowType.PLAN_REVIEW,
            initial_prompt="Test",
            metadata={"key": "value"}
        )
        assert workflow.metadata == {"key": "value"}

    def test_workflow_response_serialization(self):
        """Test workflow response model"""
        response = WorkflowResponse(
            id="wf-123",
            name="Test",
            type="plan_review",
            status="running",
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        assert response.id == "wf-123"
        assert response.status == "running"

    def test_workflow_status_enum(self):
        """Test workflow status enumeration"""
        assert WorkflowStatus.PENDING.value == "pending"
        assert WorkflowStatus.RUNNING.value == "running"
        assert WorkflowStatus.AWAITING_CHECKPOINT.value == "awaiting_checkpoint"
        assert WorkflowStatus.COMPLETED.value == "completed"
        assert WorkflowStatus.FAILED.value == "failed"

    def test_workflow_type_enum(self):
        """Test workflow type enumeration"""
        assert WorkflowType.PLAN_REVIEW.value == "plan_review"
        assert WorkflowType.IMPLEMENTATION.value == "implementation"
        assert WorkflowType.CUSTOM.value == "custom"


class TestCheckpointModels:
    """Test checkpoint data models"""

    def test_checkpoint_resolution_approve(self):
        """Test checkpoint approval"""
        resolution = CheckpointResolution(
            action="approve",
            edited_content="Approved plan"
        )
        assert resolution.action == "approve"
        assert resolution.edited_content == "Approved plan"

    def test_checkpoint_resolution_edit(self):
        """Test checkpoint edit action"""
        resolution = CheckpointResolution(
            action="edit",
            edited_content="Modified content",
            user_notes="Made some changes"
        )
        assert resolution.action == "edit"
        assert resolution.user_notes == "Made some changes"

    def test_checkpoint_resolution_reject(self):
        """Test checkpoint rejection"""
        resolution = CheckpointResolution(action="reject")
        assert resolution.action == "reject"
        assert resolution.edited_content is None

    def test_checkpoint_invalid_action(self):
        """Test invalid checkpoint action"""
        with pytest.raises(ValidationError):
            CheckpointResolution(action="invalid_action")


class TestAgentModels:
    """Test agent data models"""

    def test_agent_config_creation(self):
        """Test agent configuration"""
        config = AgentConfig(
            name="test_agent",
            agent_type="mock",
            role="planning"
        )
        assert config.name == "test_agent"
        assert config.role == "planning"

    def test_agent_status_tracking(self):
        """Test agent status model"""
        status = AgentStatus(
            name="test_agent",
            type="mock",
            status="running",
            port=3701
        )
        assert status.status == "running"
        assert status.port == 3701
