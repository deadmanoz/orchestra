# Orchestra Implementation Approval Hooks

This directory contains Claude Code hooks for human-in-the-loop implementation approval.

## Overview

When Orchestra moves from the planning/review phase to implementation, these hooks allow the user to approve or deny each file modification before it happens.

**Flow:**
1. User approves a plan in Orchestra UI
2. Implementation agent (Claude Code) starts working
3. When Claude Code tries to Write/Edit/Bash, the hook intercepts
4. Hook sends approval request to Orchestra API
5. Orchestra UI shows the change for user approval
6. User approves or denies
7. Hook receives decision and allows/blocks the operation

## Files

- `implementation_approval.sh` - Bash version of the hook
- `implementation_approval.py` - Python version (recommended)
- `test_spike.py` - Test script to validate the spike

## Installation

### 1. Configure Claude Code

Add to your Claude Code settings (`.claude/settings.json` in your project or global config):

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write|Edit|Bash|NotebookEdit",
        "command": "python3 /path/to/orchestra/hooks/implementation_approval.py"
      }
    ]
  }
}
```

### 2. Set Environment Variables

Before starting Claude Code for implementation:

```bash
export ORCHESTRA_API_URL="http://localhost:8000"
export ORCHESTRA_WORKFLOW_ID="wf-your-workflow-id"
```

### 3. Start Orchestra

```bash
cd /path/to/orchestra
python -m backend.main
```

## Testing

1. Start Orchestra API:
   ```bash
   cd /home/user/orchestra
   python -m backend.main
   ```

2. Run the test script:
   ```bash
   python hooks/test_spike.py
   ```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/approvals/request` | POST | Create approval request |
| `/api/approvals/{id}` | GET | Get approval status |
| `/api/approvals/{id}/resolve` | POST | Approve or deny |
| `/api/approvals/{id}/wait` | POST | Long-poll for resolution |
| `/api/approvals/workflow/{id}/pending` | GET | Get all pending approvals |

## Exit Codes

- `0` - Approved: Tool is allowed to execute
- `2` - Denied: Tool is blocked from executing
- `1` - Error: Hook failed (tool still executes)

## Security Notes

- The hook fails open (allows execution) if Orchestra API is unavailable
- Modify this behavior in the hook script if you need fail-close security
- Consider adding authentication to the approval API in production
