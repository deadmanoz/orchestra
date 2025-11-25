# Orchestra - Project Task Runner
# Run 'just --list' to see all available commands

# Default recipe (shows help)
default:
    @just --list

# Install all dependencies (backend + frontend)
install:
    @echo "📦 Installing backend dependencies..."
    pip install -r requirements.txt
    @echo "📦 Installing frontend dependencies..."
    cd frontend && npm install

# Setup project (install + create .env)
setup:
    @echo "🎭 Setting up Orchestra..."
    @just install
    @if [ ! -f .env ]; then \
        echo "📝 Creating .env from .env.example..."; \
        cp .env.example .env; \
        echo "⚠️  Please update .env with your API keys"; \
    else \
        echo "✅ .env already exists"; \
    fi

# Run backend development server
backend:
    @echo "🎼 Starting backend server..."
    python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 3030

# Run frontend development server
frontend:
    @echo "🎨 Starting frontend dev server..."
    cd frontend && npm run dev

# Run both backend and frontend (requires 'concurrently' or separate terminals)
dev:
    @echo "🚀 Starting full development environment..."
    @echo "⚠️  Run 'just backend' and 'just frontend' in separate terminals"

# Build frontend for production
build:
    @echo "🏗️  Building frontend..."
    cd frontend && npm run build

# Run all tests
test:
    @echo "🧪 Running all tests..."
    pytest

# Run tests with coverage
test-cov:
    @echo "🧪 Running tests with coverage..."
    pytest --cov=backend --cov-report=html --cov-report=term

# Run specific test file
test-file FILE:
    @echo "🧪 Running tests in {{FILE}}..."
    pytest {{FILE}}

# Lint frontend code
lint:
    @echo "🔍 Linting frontend code..."
    cd frontend && npm run lint

# Type check frontend
typecheck:
    @echo "📝 Type checking frontend..."
    cd frontend && npx tsc --noEmit

# Clean build artifacts
clean:
    @echo "🧹 Cleaning build artifacts..."
    rm -rf frontend/dist
    rm -rf frontend/node_modules/.vite
    rm -rf backend/__pycache__
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete
    @echo "✅ Clean complete"

# Clean everything (including dependencies)
clean-all: clean
    @echo "🧹 Cleaning all dependencies..."
    rm -rf frontend/node_modules
    rm -rf .pytest_cache
    rm -rf .coverage
    rm -rf htmlcov
    @echo "✅ Deep clean complete"

# Check backend health
health:
    @echo "🏥 Checking backend health..."
    curl -s http://localhost:3030/health | python -m json.tool || echo "❌ Backend not running"

# View backend logs (if running in background)
logs:
    @echo "📋 Showing orchestra.log..."
    tail -f orchestra.log

# Database operations
db-reset:
    @echo "🗄️  Resetting database..."
    @echo "⚠️  Not implemented - add your db reset command here"

# Format Python code (requires black)
format-py:
    @echo "✨ Formatting Python code..."
    black backend/ tests/

# Format TypeScript code (requires prettier)
format-ts:
    @echo "✨ Formatting TypeScript code..."
    cd frontend && npx prettier --write "src/**/*.{ts,tsx}"

# Run Python linting (requires ruff or pylint)
lint-py:
    @echo "🔍 Linting Python code..."
    @if command -v ruff >/dev/null 2>&1; then \
        ruff check backend/ tests/; \
    else \
        echo "⚠️  ruff not installed. Run: pip install ruff"; \
    fi

# Git status check
status:
    @echo "📊 Git status:"
    @git status --short
    @echo ""
    @echo "🌿 Current branch: $(git branch --show-current)"

# Quick commit with message
commit MESSAGE:
    git add .
    git commit -m "{{MESSAGE}}"

# Push current branch
push:
    @echo "⬆️  Pushing to remote..."
    git push -u origin $(git branch --show-current)

# Create and push commit in one go
save MESSAGE: (commit MESSAGE) push

# Show project info
info:
    @echo "🎭 Orchestra Project Info"
    @echo "========================="
    @echo "Backend: FastAPI + Python"
    @echo "Frontend: React + Vite + TypeScript"
    @echo "Testing: pytest"
    @echo ""
    @echo "📍 Endpoints:"
    @echo "  Backend:  http://localhost:3030"
    @echo "  Frontend: http://localhost:5173"
    @echo "  API Docs: http://localhost:3030/docs"
    @echo ""
    @echo "Run 'just --list' to see all commands"
