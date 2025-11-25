from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from backend.settings import settings
from backend.config.logging_config import setup_logging
from backend.db.connection import db
from backend.api import workflows, websocket, plans, approvals
from backend.agents.factory import agent_factory

# Initialize logging
setup_logging(
    log_level=settings.log_level if hasattr(settings, 'log_level') else 'INFO',
    log_file='orchestra.log' if settings.environment == 'production' else None
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle management"""
    # Startup
    logger.info("🎼 Starting Orchestra...")
    await db.init_db()
    logger.info("✅ Database initialized")

    yield

    # Shutdown
    logger.info("🛑 Shutting down Orchestra...")
    await agent_factory.stop_all()
    logger.info("✅ All agents stopped")

app = FastAPI(
    title="Orchestra",
    description="Multi-Agent Orchestration Platform",
    version="0.1.0",
    lifespan=lifespan
)

# CORS
cors_origins = settings.cors_origins if isinstance(settings.cors_origins, list) else [settings.cors_origins]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(workflows.router)
app.include_router(websocket.router)
app.include_router(plans.router)
app.include_router(approvals.router)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "environment": settings.environment}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug
    )
