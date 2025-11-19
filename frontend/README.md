# Orchestra Frontend

React + TypeScript frontend for the Orchestra multi-agent orchestration platform.

## Features

- **Workflow Creation**: Start new orchestration workflows with custom prompts and workspace paths
- **Real-time Updates**: WebSocket integration with automatic reconnection for live workflow status updates
- **Error Resilience**: React Error Boundary for graceful error handling and recovery
- **Checkpoint Editor**: Interactive editor for reviewing and editing agent outputs at human-in-the-loop checkpoints
- **Workflow Dashboard**: Real-time monitoring of agent executions, messages, and workflow progress
- **Type-safe API**: Full TypeScript support with TanStack Query for data fetching

## Tech Stack

- **React 18.3** - UI framework
- **TypeScript** - Type safety
- **Vite** - Fast build tool and dev server
- **TanStack Query** - Server state management and caching
- **Axios** - HTTP client
- **React Markdown** - Markdown rendering for agent outputs
- **Lucide React** - Icon library

## Getting Started

### Prerequisites

- Node.js 18+
- npm or yarn
- Backend server running on `http://localhost:3030`

### Installation

```bash
npm install
```

### Development

Start the development server with hot module replacement:

```bash
npm run dev
```

The frontend will be available at `http://localhost:5173`

### Build

Build for production:

```bash
npm run build
```

Preview production build:

```bash
npm run preview
```

### Linting

Check code quality:

```bash
npm run lint
```

## Project Structure

```
frontend/
├── src/
│   ├── api/
│   │   └── client.ts           # API client and WebSocket manager
│   ├── components/
│   │   ├── CheckpointEditor.tsx    # Interactive checkpoint review UI
│   │   ├── CreateWorkflowForm.tsx  # Workflow creation form
│   │   └── WorkflowDashboard.tsx   # Workflow monitoring dashboard
│   ├── hooks/
│   │   ├── useWorkflow.ts          # React Query hook for workflow data
│   │   ├── useCreateWorkflow.ts    # Mutation hook for creating workflows
│   │   ├── useResumeWorkflow.ts    # Mutation hook for checkpoint actions
│   │   └── useWebSocket.ts         # WebSocket connection hook
│   ├── types/
│   │   └── index.ts            # TypeScript type definitions
│   ├── App.tsx                 # Main application component
│   ├── main.tsx                # Application entry point
│   └── index.css               # Global styles
├── package.json
├── tsconfig.json              # TypeScript configuration
├── vite.config.ts             # Vite configuration with API proxy
└── README.md
```

## API Integration

The frontend connects to the backend API at `http://localhost:3030/api` via Vite's proxy configuration.

### Key Endpoints

- `POST /api/workflows` - Create new workflow
- `GET /api/workflows/{id}` - Get workflow state and pending checkpoint
- `POST /api/workflows/{id}/resume` - Resolve checkpoint and resume workflow
- `WS /ws/{id}` - WebSocket connection for real-time updates

## Component Overview

### CreateWorkflowForm

Form for starting new workflows with:
- Workflow name
- Type selection (plan_review, implementation, custom)
- Initial prompt textarea
- Workspace path input (optional) for codebase-specific workflows

### WorkflowDashboard

Displays:
- Workflow status and metadata
- Agent execution history with timing
- Recent messages from agents and user

### CheckpointEditor

Interactive checkpoint UI featuring:
- Agent outputs from the current iteration
- Editable content area with preview/edit modes
- Markdown rendering
- User notes textarea
- Primary and secondary action buttons
- Real-time feedback on submission

## WebSocket Updates

The frontend automatically connects to the workflow WebSocket for real-time updates with automatic reconnection on connection loss:

- `status_update` - Workflow status changes
- `checkpoint_ready` - New checkpoint available for review
- `error` - Error notifications

The WebSocket connection includes:
- Automatic reconnection with exponential backoff
- Error handling for connection failures
- Graceful cleanup on component unmount

## Type Safety

Full TypeScript support with interfaces for:
- `Workflow` - Workflow metadata and status
- `Checkpoint` - Checkpoint data structure
- `AgentOutput` - Agent execution results
- `WorkflowStateSnapshot` - Complete workflow state
- `CheckpointResolution` - User checkpoint actions

## Development Notes

- The dev server proxies `/api` and `/ws` requests to `http://localhost:3030`
- Hot module replacement (HMR) is enabled for fast development
- TanStack Query provides automatic caching and refetching
- Workflows in "running" state are polled every 2 seconds
