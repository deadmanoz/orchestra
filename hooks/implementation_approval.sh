#!/bin/bash
# Orchestra Implementation Approval Hook
#
# This is a Claude Code PreToolUse hook that intercepts file modification
# tools (Write, Edit, Bash) and requests approval from the Orchestra UI.
#
# Installation:
# Add to your Claude Code settings.json:
# {
#   "hooks": {
#     "PreToolUse": [
#       {
#         "matcher": "Write|Edit|Bash",
#         "command": "/path/to/orchestra/hooks/implementation_approval.sh"
#       }
#     ]
#   }
# }
#
# Environment variables:
#   ORCHESTRA_API_URL - Orchestra API base URL (default: http://localhost:8000)
#   ORCHESTRA_WORKFLOW_ID - Current workflow ID (required)
#
# Exit codes:
#   0 - Approved (allow tool to execute)
#   2 - Denied (block tool execution)
#   1 - Error (hook failed, tool still executes)

set -e

# Configuration
ORCHESTRA_API_URL="${ORCHESTRA_API_URL:-http://localhost:8000}"
WORKFLOW_ID="${ORCHESTRA_WORKFLOW_ID:-}"
POLL_INTERVAL=2  # seconds

# Read hook input from stdin
# Claude Code passes: {"tool_name": "...", "tool_input": {...}}
HOOK_INPUT=$(cat)

# Extract tool name and input using jq
TOOL_NAME=$(echo "$HOOK_INPUT" | jq -r '.tool_name // "unknown"')
TOOL_INPUT=$(echo "$HOOK_INPUT" | jq -c '.tool_input // {}')

# Log to stderr (won't interfere with hook output)
log() {
    echo "[Orchestra Hook] $1" >&2
}

log "Intercepted tool: $TOOL_NAME"

# Skip if no workflow ID configured
if [ -z "$WORKFLOW_ID" ]; then
    log "No ORCHESTRA_WORKFLOW_ID set, allowing tool execution"
    exit 0
fi

# Skip certain tools that don't need approval
case "$TOOL_NAME" in
    "Read"|"Glob"|"Grep"|"WebFetch"|"WebSearch")
        log "Read-only tool, allowing"
        exit 0
        ;;
esac

# Request approval from Orchestra API
log "Requesting approval from Orchestra..."
RESPONSE=$(curl -s -X POST "${ORCHESTRA_API_URL}/api/approvals/request" \
    -H "Content-Type: application/json" \
    -d "{
        \"workflow_id\": \"$WORKFLOW_ID\",
        \"tool_name\": \"$TOOL_NAME\",
        \"tool_input\": $TOOL_INPUT
    }")

# Extract approval ID
APPROVAL_ID=$(echo "$RESPONSE" | jq -r '.approval_id // empty')

if [ -z "$APPROVAL_ID" ]; then
    log "Failed to create approval request: $RESPONSE"
    exit 1
fi

log "Approval request created: $APPROVAL_ID"
log "Waiting for user decision..."

# Poll for approval status
while true; do
    STATUS_RESPONSE=$(curl -s "${ORCHESTRA_API_URL}/api/approvals/${APPROVAL_ID}")
    STATUS=$(echo "$STATUS_RESPONSE" | jq -r '.status // "error"')

    case "$STATUS" in
        "approved")
            log "✓ Approved! Proceeding with $TOOL_NAME"
            exit 0
            ;;
        "denied")
            USER_MSG=$(echo "$STATUS_RESPONSE" | jq -r '.user_message // "User denied the operation"')
            log "✗ Denied: $USER_MSG"
            # Output denial message for Claude to see
            echo "Operation blocked by user: $USER_MSG"
            exit 2
            ;;
        "pending")
            sleep $POLL_INTERVAL
            ;;
        *)
            log "Unknown status: $STATUS"
            exit 1
            ;;
    esac
done
