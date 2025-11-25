#!/usr/bin/env python3
"""
Orchestra Implementation Approval Hook (Python version)

This is a Claude Code PreToolUse hook that intercepts file modification
tools (Write, Edit, Bash) and requests approval from the Orchestra UI.

Installation:
Add to your Claude Code settings.json:
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write|Edit|Bash",
        "command": "python3 /path/to/orchestra/hooks/implementation_approval.py"
      }
    ]
  }
}

Environment variables:
  ORCHESTRA_API_URL - Orchestra API base URL (default: http://localhost:8000)
  ORCHESTRA_WORKFLOW_ID - Current workflow ID (required)

Exit codes:
  0 - Approved (allow tool to execute)
  2 - Denied (block tool execution)
  1 - Error (hook failed, tool still executes)
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error

# Configuration
ORCHESTRA_API_URL = os.environ.get("ORCHESTRA_API_URL", "http://localhost:8000")
WORKFLOW_ID = os.environ.get("ORCHESTRA_WORKFLOW_ID", "")
POLL_INTERVAL = 2  # seconds

# Read-only tools that don't need approval
READ_ONLY_TOOLS = {"Read", "Glob", "Grep", "WebFetch", "WebSearch", "Task", "TodoRead"}


def log(msg: str):
    """Log to stderr (won't interfere with hook output)"""
    print(f"[Orchestra Hook] {msg}", file=sys.stderr)


def post_json(url: str, data: dict) -> dict:
    """POST JSON to URL and return parsed response"""
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_json(url: str) -> dict:
    """GET JSON from URL and return parsed response"""
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    # Read hook input from stdin
    # Claude Code passes: {"tool_name": "...", "tool_input": {...}}
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        log(f"Failed to parse hook input: {e}")
        sys.exit(1)

    tool_name = hook_input.get("tool_name", "unknown")
    tool_input = hook_input.get("tool_input", {})

    log(f"Intercepted tool: {tool_name}")

    # Skip if no workflow ID configured
    if not WORKFLOW_ID:
        log("No ORCHESTRA_WORKFLOW_ID set, allowing tool execution")
        sys.exit(0)

    # Skip read-only tools
    if tool_name in READ_ONLY_TOOLS:
        log("Read-only tool, allowing")
        sys.exit(0)

    # Request approval from Orchestra API
    log("Requesting approval from Orchestra...")
    try:
        response = post_json(
            f"{ORCHESTRA_API_URL}/api/approvals/request",
            {
                "workflow_id": WORKFLOW_ID,
                "tool_name": tool_name,
                "tool_input": tool_input
            }
        )
    except urllib.error.URLError as e:
        log(f"Failed to connect to Orchestra API: {e}")
        log("Allowing tool execution (API unavailable)")
        sys.exit(0)  # Fail open - allow if API unavailable

    approval_id = response.get("approval_id")
    if not approval_id:
        log(f"Failed to create approval request: {response}")
        sys.exit(1)

    log(f"Approval request created: {approval_id}")
    log("Waiting for user decision...")

    # Poll for approval status
    while True:
        try:
            status_response = get_json(f"{ORCHESTRA_API_URL}/api/approvals/{approval_id}")
            status = status_response.get("status", "error")

            if status == "approved":
                log(f"✓ Approved! Proceeding with {tool_name}")
                sys.exit(0)

            elif status == "denied":
                user_msg = status_response.get("user_message", "User denied the operation")
                log(f"✗ Denied: {user_msg}")
                # Output denial message for Claude to see
                print(f"Operation blocked by user: {user_msg}")
                sys.exit(2)

            elif status == "pending":
                time.sleep(POLL_INTERVAL)

            else:
                log(f"Unknown status: {status}")
                sys.exit(1)

        except urllib.error.URLError as e:
            log(f"Error polling approval status: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
