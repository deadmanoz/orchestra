# 🎼 Orchestra

Multi-Agent Orchestration Platform with Human-in-the-Loop Checkpoints

## Overview

Orchestra enables workflows where multiple AI agents (like Claude Code, OpenAI Codex, Gemini) collaborate on tasks with mandatory human review at every handoff point. Built with LangGraph for workflow orchestration, FastAPI for the backend, and React for the frontend.

## Architecture

- **Backend**: Python FastAPI + LangGraph
- **Frontend**: React + TypeScript + TanStack Query
- **Database**: SQLite (with LangGraph checkpointing)
- **Agents**: Mock agents for development, pluggable CLI/API agents

## Quick Start

### Backend Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Run backend
python -m backend.main
```

Backend will be available at: http://localhost:8000
API docs at: http://localhost:8000/docs

### Frontend Setup (Coming Soon)

```bash
cd frontend
npm install
npm run dev
```

## Features

### Current (MVP)
- ✅ Plan-Review workflow with human checkpoints
- ✅ Mock agents for development
- ✅ LangGraph-based orchestration
- ✅ SQLite persistence with automatic checkpointing
- ✅ REST API for workflow management

### Coming Soon
- 🔄 React frontend with checkpoint editor
- 🔄 WebSocket real-time updates
- 🔄 CLI agent integration (Claude Code, Codex, etc.)
- 🔄 Workflow visualization
- 🔄 Export to markdown/PDF

## Workflow Example

### Plan-Review Cycle

1. **Planning Agent** creates initial plan
2. **Human Checkpoint**: User reviews and edits plan
3. **Review Agents** (3 agents in parallel) provide feedback
4. **Human Checkpoint**: User consolidates feedback
5. Loop back to step 1 or approve final plan

## Development

### Testing the Backend

```bash
# Test health endpoint
curl http://localhost:8000/health

# Create a workflow
curl -X POST http://localhost:8000/api/workflows \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Plan Review",
    "type": "plan_review",
    "initial_prompt": "Create a plan for building a todo app"
  }'
```

### Project Structure

```
orchestra/
├── backend/              # Python FastAPI backend
│   ├── api/             # REST API endpoints
│   ├── workflows/       # LangGraph workflows
│   ├── agents/          # Agent interfaces
│   ├── models/          # Pydantic models
│   ├── db/              # Database schema & connection
│   └── utils/           # Utilities
├── frontend/            # React frontend (coming soon)
├── data/                # SQLite database
└── tests/               # Tests
```

## Configuration

Environment variables (`.env`):

```env
ENVIRONMENT=development
DEBUG=True
USE_MOCK_AGENTS=True
API_HOST=0.0.0.0
API_PORT=8000
CORS_ORIGINS=http://localhost:5173
```

## License

MIT
