"""Integration tests for API endpoints"""
import pytest
from httpx import AsyncClient, ASGITransport
from datetime import datetime

from backend.main import app
from backend.models.workflow import WorkflowCreate, WorkflowType


@pytest.mark.asyncio
class TestHealthEndpoint:
    """Test health check endpoint"""

    async def test_health_check(self):
        """Test health endpoint returns OK"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "environment" in data


@pytest.mark.asyncio
class TestWorkflowAPI:
    """Test workflow API endpoints"""

    async def test_create_workflow(self):
        """Test creating a new workflow"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/workflows",
                json={
                    "name": "Test Workflow",
                    "type": "plan_review",
                    "initial_prompt": "Create a test plan"
                }
            )

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["name"] == "Test Workflow"
        assert data["status"] == "running"
        assert data["type"] == "plan_review"

    async def test_create_workflow_validation(self):
        """Test workflow creation validates input"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Missing required field
            response = await client.post(
                "/api/workflows",
                json={
                    "name": "Test",
                    "type": "plan_review"
                    # Missing initial_prompt
                }
            )

        assert response.status_code == 422  # Validation error

    async def test_create_workflow_invalid_type(self):
        """Test invalid workflow type is rejected"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/workflows",
                json={
                    "name": "Test",
                    "type": "invalid_type",
                    "initial_prompt": "Test"
                }
            )

        assert response.status_code == 422

    async def test_get_workflow(self):
        """Test retrieving workflow status"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # First create a workflow
            create_response = await client.post(
                "/api/workflows",
                json={
                    "name": "Get Test",
                    "type": "plan_review",
                    "initial_prompt": "Test plan"
                }
            )

            workflow_id = create_response.json()["id"]

            # Then get it
            get_response = await client.get(f"/api/workflows/{workflow_id}")

        assert get_response.status_code == 200
        data = get_response.json()
        assert data["workflow"]["id"] == workflow_id
        assert "pending_checkpoint" in data
        assert "recent_messages" in data

    async def test_get_nonexistent_workflow(self):
        """Test getting non-existent workflow returns 404"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/workflows/nonexistent-id")

        assert response.status_code == 404

    async def test_resume_workflow_not_found(self):
        """Test resuming non-existent workflow"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/workflows/nonexistent/resume",
                json={"action": "approve"}
            )

        assert response.status_code == 404


@pytest.mark.asyncio
@pytest.mark.integration
class TestWorkflowLifecycle:
    """Integration tests for complete workflow lifecycle"""

    async def test_workflow_creation_and_retrieval(self):
        """Test creating and retrieving workflow"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Create workflow
            create_response = await client.post(
                "/api/workflows",
                json={
                    "name": "Lifecycle Test",
                    "type": "plan_review",
                    "initial_prompt": "Build a microservice"
                }
            )

            assert create_response.status_code == 200
            workflow_id = create_response.json()["id"]

            # Wait briefly for workflow to start
            import asyncio
            await asyncio.sleep(0.5)

            # Retrieve workflow
            get_response = await client.get(f"/api/workflows/{workflow_id}")

            assert get_response.status_code == 200
            data = get_response.json()
            assert data["workflow"]["id"] == workflow_id
            assert data["workflow"]["name"] == "Lifecycle Test"


@pytest.mark.asyncio
class TestWebSocketEndpoint:
    """Test WebSocket connections"""

    async def test_websocket_connection(self):
        """Test WebSocket can be established"""
        # Note: Testing WebSocket requires a more complex setup
        # This is a placeholder for WebSocket tests
        # In a real scenario, you'd use pytest-asyncio and websockets library
        pass


@pytest.mark.asyncio
class TestCORS:
    """Test CORS configuration"""

    async def test_cors_headers(self):
        """Test CORS headers are set"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.options(
                "/api/workflows",
                headers={"Origin": "http://localhost:5173"}
            )

        # Should allow the origin
        assert response.status_code in [200, 204]
