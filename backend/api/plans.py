"""
Plans API endpoints for saving agent outputs to files.
"""

from fastapi import APIRouter, HTTPException
from pathlib import Path
from datetime import datetime
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/plans", tags=["plans"])


class SavePlanRequest(BaseModel):
    workspace_path: str
    content: str
    subdirectory: str = "plans"  # Optional subdirectory under design-and-review


@router.post("/save")
async def save_plan(request: SavePlanRequest):
    """
    Save a plan file to the workspace.

    This endpoint is used to persist planning agent outputs to disk
    for version control and future reference.
    """
    try:
        workspace = Path(request.workspace_path)

        # Validate workspace exists
        if not workspace.exists() or not workspace.is_dir():
            raise HTTPException(
                status_code=400,
                detail=f"Workspace path does not exist or is not a directory: {request.workspace_path}"
            )

        # Create design-and-review subdirectory
        plan_dir = workspace / "design-and-review" / request.subdirectory
        plan_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        plan_file = plan_dir / f"plan-{timestamp}.md"

        # Save plan content
        plan_file.write_text(request.content, encoding='utf-8')

        logger.info(f"Saved plan to {plan_file}")

        return {
            "success": True,
            "path": str(plan_file),
            "filename": plan_file.name
        }

    except Exception as e:
        logger.error(f"Failed to save plan: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to save plan: {str(e)}")


def save_plan_to_file(workspace_path: str, content: str, subdirectory: str = "plans") -> str:
    """
    Helper function to save plan content to file.

    Args:
        workspace_path: Path to workspace directory
        content: Plan content to save
        subdirectory: Subdirectory under design-and-review (default: "plans")

    Returns:
        Path to saved file
    """
    workspace = Path(workspace_path)

    if not workspace.exists() or not workspace.is_dir():
        raise ValueError(f"Invalid workspace path: {workspace_path}")

    # Create design-and-review subdirectory
    plan_dir = workspace / "design-and-review" / subdirectory
    plan_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    plan_file = plan_dir / f"plan-{timestamp}.md"

    # Save plan content
    plan_file.write_text(content, encoding='utf-8')

    logger.info(f"Saved plan to {plan_file}")

    return str(plan_file)
