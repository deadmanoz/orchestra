# CLI Agent Integration Guide

## Overview

Orchestra now supports real CLI agents via subprocess integration! This allows you to use actual AI coding agents instead of mock agents.

> **Implementation Status**:
> - ✅ **ClaudeAgent**: Fully implemented and production-ready
> - ⏳ **CodexAgent**: Architecture defined, not yet implemented
> - ⏳ **GeminiAgent**: Architecture defined, not yet implemented
>
> This guide describes both implemented and planned agent integrations.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│         Orchestra Workflow (LangGraph)              │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│           Agent Factory (Singleton)                 │
│  ┌──────────────────────────────────────────────┐  │
│  │  get_agent(role, name) → Agent instance      │  │
│  │  Supports: Mock | Claude | Codex | Gemini   │  │
│  └──────────────────────────────────────────────┘  │
└──────┬──────────────┬─────────────────────────────┘
       │              │
       ▼              ▼
┌─────────────┐ ┌──────────────┐
│ ClaudeAgent │ │  MockAgent   │
│ (CLI)       │ │  (Fallback)  │
└──────┬──────┘ └──────────────┘
       │
       ▼
┌─────────────────────────────────┐
│   Subprocess (asyncio)          │
│   • claude --json -p <prompt>   │
│   • Async stdout/stderr capture │
│   • JSON response parsing       │
│   • Timeout handling            │
└─────────────────────────────────┘
```

## Components

### 1. Base Classes

#### `CLIAgent` (`backend/agents/cli_agent.py`)
Abstract base class for all CLI-based agents.

**Key Features:**
- Async subprocess management via `asyncio.create_subprocess_exec`
- Configurable timeout (default: 5 minutes)
- Workspace path handling
- Error handling with custom `CLIAgentError` exception
- Process lifecycle management (start, send_message, stop)

**Abstract Methods:**
- `get_cli_command(message: str) -> List[str]` - Build CLI command
- `parse_response(stdout: str, stderr: str) -> str` - Parse output

#### `JSONCLIAgent` (`backend/agents/cli_agent.py`)
Extends `CLIAgent` with JSON parsing capabilities.

**Features:**
- Automatic JSON parsing from stdout
- Flexible content extraction (override `extract_content_from_json()`)
- Handles multiple JSON response patterns
- Detailed error logging for parse failures

### 2. Agent Implementations

#### `ClaudeAgent` (`backend/agents/claude_agent.py`)
Claude Code CLI integration.

**Command Format:**
```bash
claude --json -p "<prompt>"
```

**JSON Response Patterns Supported:**
1. Direct field: `{"content": "response"}`
2. Message field: `{"message": "response"}`
3. Nested: `{"response": {"content": "response"}}`
4. List: `{"messages": [{"content": "response"}]}`

**Configuration:**
- CLI Path: `CLAUDE_CLI_PATH` (default: `claude`)
- Timeout: `AGENT_TIMEOUT` (default: 300 seconds)

### 3. Agent Factory

#### `AgentFactory` (`backend/agents/factory.py`)
Singleton factory for creating and managing agents.

**Agent Selection Logic:**
```python
if use_mock_agents:
    return MockAgent(...)
else:
    # Route based on agent name prefix:
    if name.startswith("claude"):
        return ClaudeAgent(...)
    # ... future: codex, gemini
    else:
        return MockAgent(...)  # Graceful fallback
```

**Key Methods:**
- `get_agent(role, name, workspace_path)` - Get or create agent
- `get_review_agents(workspace_path)` - Get all 3 reviewers
- `stop_all()` - Cleanup all agents

## Configuration

### Environment Variables

Add to `.env` file:

```bash
# Agent Configuration
USE_MOCK_AGENTS=false  # Set to false to use real CLI agents
AGENT_TIMEOUT=300      # Timeout in seconds

# CLI Paths (customize if not in PATH)
CLAUDE_CLI_PATH=claude
CODEX_CLI_PATH=codex
GEMINI_CLI_PATH=gemini
```

### Settings (`backend/config.py`)

```python
class Settings(BaseSettings):
    # Agents
    use_mock_agents: bool = True
    agent_timeout: int = 300

    # CLI Agent Paths
    claude_cli_path: str = "claude"
    codex_cli_path: str = "codex"
    gemini_cli_path: str = "gemini"
```

## Usage

### 1. Install CLI Agents

First, install the CLI agents you want to use:

```bash
# Claude Code (requires Anthropic API key)
npm install -g @anthropic-ai/claude-code

# Codex (requires OpenAI API key)
npm install -g openai-codex

# Gemini CLI (requires Google API key)
npm install -g @google/gemini-cli
```

### 2. Configure Environment

Copy `.env.example` to `.env` and set:

```bash
USE_MOCK_AGENTS=false
CLAUDE_CLI_PATH=claude  # or full path like /usr/local/bin/claude
```

### 3. Test Individual Agent

```python
from backend.agents.claude_agent import ClaudeAgent
import asyncio

async def test():
    agent = ClaudeAgent(
        name="test_planner",
        role="planning",
        workspace_path="./workspace"
    )

    await agent.start()
    response = await agent.send_message("Create a hello world app")
    print(response)
    await agent.stop()

asyncio.run(test())
```

### 4. Use in Workflow

The workflow automatically uses the factory:

```python
# In plan_review.py (line 78)
planning_agent = await self.agent_factory.get_agent(
    "planning",
    "claude_planner",  # This will route to ClaudeAgent!
    workspace_path=self.workspace_path
)

plan = await planning_agent.send_message(prompt)
```

## Current Implementation Status

### ✅ Completed

- [x] Base `CLIAgent` class with subprocess management
- [x] `JSONCLIAgent` for JSON-based agents
- [x] `ClaudeAgent` implementation for Claude Code
- [x] Agent factory integration with routing logic
- [x] Configuration system (env vars + settings)
- [x] Error handling and timeout support
- [x] Logging infrastructure
- [x] Unit tests for agent creation and JSON parsing

### 🚧 Planned (Not Yet Implemented)

- [ ] `CodexAgent` with `--output-schema` for structured reviews
- [ ] `GeminiAgent` with `--output-format json`
- [ ] Review JSON schema for consistent output
- [ ] Multi-agent review with different CLI tools

### 📋 Planned

- [ ] Retry logic for transient failures
- [ ] Advanced error recovery
- [ ] Subprocess output logging to files
- [ ] Cost tracking per agent execution
- [ ] Performance metrics collection

## Agent Roles in Workflow

### Planning Agent (Claude Code - Implemented)
- **Name**: `claude_planner`
- **Role**: `planning`
- **Task**: Create development plans, revise based on feedback
- **Status**: ✅ Fully implemented and tested
- **Why Claude?**: Best for complex reasoning and planning tasks

### Review Agents (Future Enhancement)
- **Names**: `codex_reviewer`, `gemini_reviewer`, `claude_reviewer`
- **Role**: `review`
- **Task**: Parallel code review with different perspectives
- **Status**: ⏳ Planned but not yet implemented (currently uses MockAgent)
- **Why Multiple?**: Diverse viewpoints improve plan quality

## Troubleshooting

### Agent Not Found

**Error**: `CLIAgentError: Agent claude_planner failed with exit code 127: command not found`

**Solution**: CLI not in PATH. Set full path in `.env`:
```bash
CLAUDE_CLI_PATH=/usr/local/bin/claude
```

### Timeout Errors

**Error**: `CLIAgentError: Agent claude_planner timed out after 300 seconds`

**Solution**: Increase timeout in `.env`:
```bash
AGENT_TIMEOUT=600  # 10 minutes
```

### JSON Parse Errors

**Error**: `CLIAgentError: Agent returned invalid JSON`

**Solution**: Check stderr output in logs. The agent may not support `--json` flag or may be returning non-JSON output. Verify CLI version and flags.

### Permission Errors

**Error**: `Permission denied` when executing CLI

**Solution**: Make CLI executable:
```bash
chmod +x $(which claude)
```

## Development Notes

### Adding a New CLI Agent

1. Create agent class extending `JSONCLIAgent`:

```python
from backend.agents.cli_agent import JSONCLIAgent
from backend.config import settings

class MyAgent(JSONCLIAgent):
    def __init__(self, name: str, role: str, workspace_path: str = None):
        super().__init__(
            name=name,
            agent_type="myagent",
            role=role,
            workspace_path=workspace_path,
            timeout=settings.agent_timeout
        )
        self.cli_path = settings.myagent_cli_path

    def get_cli_command(self, message: str) -> List[str]:
        return [self.cli_path, "--json", message]

    def extract_content_from_json(self, data: dict) -> str:
        # Agent-specific JSON extraction
        return data.get("result", "")
```

2. Add to factory routing in `factory.py`:

```python
elif name.startswith("myagent"):
    return MyAgent(name=name, role=role, workspace_path=workspace_path)
```

3. Add config in `config.py`:

```python
myagent_cli_path: str = "myagent"
```

### Testing Checklist

- [ ] Agent can be instantiated
- [ ] Command construction is correct
- [ ] JSON parsing handles expected output format
- [ ] Timeout handling works
- [ ] Error messages are clear
- [ ] Workspace path is passed correctly
- [ ] Agent integrates with factory
- [ ] End-to-end workflow completes

## Performance Considerations

### Subprocess Overhead
- Spawning process: ~100-200ms
- No persistent connections (stateless design)
- Each `send_message()` creates new subprocess

### Parallelization
- Review agents run in parallel via `asyncio.gather()`
- 3 reviewers = 3 concurrent subprocesses
- Monitor system resources with many concurrent agents

### Resource Limits
- Each subprocess consumes memory (model-dependent)
- Claude Code: ~500MB-1GB per process
- Set `AGENT_TIMEOUT` to prevent runaway processes

## Security Considerations

### Workspace Isolation
- Agents run in configured workspace directory
- Use `cwd=self.workspace_path` in subprocess
- Consider using Docker containers for full isolation

### Input Sanitization
- Prompts are passed as command arguments
- No shell expansion (`asyncio.create_subprocess_exec` uses direct exec)
- Still validate/sanitize user input before passing to agents

### API Key Management
- CLI tools read API keys from their own config
- Don't pass API keys via command line (visible in process list)
- Use environment variables or CLI-specific config files

## References

- [Claude Code CLI Documentation](https://docs.anthropic.com/claude/docs/claude-code)
- [Codex CLI Documentation](https://developers.openai.com/codex/cli/)
- [Gemini CLI Documentation](https://developers.google.com/gemini-code-assist/docs/gemini-cli)
- [LangGraph Documentation](https://python.langchain.com/docs/langgraph)
- [AsyncIO Subprocess](https://docs.python.org/3/library/asyncio-subprocess.html)
