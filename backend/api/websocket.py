from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter()

# Active WebSocket connections
active_connections: dict[str, list[WebSocket]] = {}

@router.websocket("/ws/{workflow_id}")
async def websocket_endpoint(websocket: WebSocket, workflow_id: str):
    """WebSocket for real-time workflow updates"""
    await websocket.accept()
    logger.info(f"[WebSocket] Client connected for workflow {workflow_id}")

    # Add to active connections
    if workflow_id not in active_connections:
        active_connections[workflow_id] = []
    active_connections[workflow_id].append(websocket)

    try:
        while True:
            # Keep connection alive and send updates
            from backend.api.workflows import active_workflows

            if workflow_id in active_workflows:
                status_update = {
                    "type": "status_update",
                    "workflow_id": workflow_id,
                    "status": active_workflows[workflow_id]["status"],
                    "timestamp": datetime.now().isoformat()
                }

                try:
                    await websocket.send_json(status_update)
                except Exception as e:
                    logger.warning(f"[WebSocket] Failed to send message: {e}")
                    break

            # Wait before next update
            await asyncio.sleep(2)

    except WebSocketDisconnect:
        logger.info(f"[WebSocket] Client disconnected for workflow {workflow_id}")
    except Exception as e:
        logger.error(f"[WebSocket] Error: {e}", exc_info=True)
    finally:
        # Clean up connection
        if websocket in active_connections.get(workflow_id, []):
            active_connections[workflow_id].remove(websocket)
        if workflow_id in active_connections and not active_connections[workflow_id]:
            del active_connections[workflow_id]
        logger.debug(f"[WebSocket] Connection cleaned up for workflow {workflow_id}")

async def broadcast_to_workflow(workflow_id: str, message: dict):
    """Broadcast message to all connections for a workflow"""
    if workflow_id in active_connections:
        dead_connections = []
        for connection in active_connections[workflow_id]:
            try:
                await connection.send_json(message)
            except:
                dead_connections.append(connection)

        # Clean up dead connections
        for conn in dead_connections:
            active_connections[workflow_id].remove(conn)
