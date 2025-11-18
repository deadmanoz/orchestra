from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from backend.config import settings
from backend.db.connection import db
from backend.api import workflows, websocket
from backend.agents.factory import agent_factory

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle management"""
    # Startup
    print("🎼 Starting Orchestra...")
    await db.init_db()
    print("✅ Database initialized")

    yield

    # Shutdown
    print("🛑 Shutting down Orchestra...")
    await agent_factory.stop_all()
    print("✅ All agents stopped")

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
