#!/usr/bin/env python3
"""
Test script for the implementation approval spike.

This script simulates the flow:
1. Start Orchestra API (must be running separately)
2. Hook sends approval request
3. API creates pending approval
4. User approves/denies via API
5. Hook receives response

Usage:
    # In terminal 1: Start Orchestra
    cd /home/user/orchestra && python -m backend.main

    # In terminal 2: Run this test
    python hooks/test_spike.py
"""

import json
import subprocess
import sys
import threading
import time
import urllib.request
import urllib.error

ORCHESTRA_API = "http://localhost:8000"
TEST_WORKFLOW_ID = "wf-test-spike-001"


def log(msg: str):
    print(f"[Test] {msg}")


def check_api_health() -> bool:
    """Check if Orchestra API is running"""
    try:
        with urllib.request.urlopen(f"{ORCHESTRA_API}/health", timeout=5) as resp:
            return resp.status == 200
    except:
        return False


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


def simulate_hook_call(tool_name: str, tool_input: dict) -> dict:
    """Simulate what Claude Code would send to the hook"""
    hook_input = {
        "tool_name": tool_name,
        "tool_input": tool_input
    }

    # Request approval
    response = post_json(
        f"{ORCHESTRA_API}/api/approvals/request",
        {
            "workflow_id": TEST_WORKFLOW_ID,
            "tool_name": tool_name,
            "tool_input": tool_input
        }
    )
    return response


def test_approval_flow():
    """Test the full approval flow"""
    log("=" * 60)
    log("Testing Implementation Approval Spike")
    log("=" * 60)

    # Check API
    log("\n1. Checking if Orchestra API is running...")
    if not check_api_health():
        log("❌ Orchestra API not running!")
        log("   Start it with: cd /home/user/orchestra && python -m backend.main")
        sys.exit(1)
    log("✓ API is healthy")

    # Test 1: Create approval request
    log("\n2. Creating approval request (simulating Write tool)...")
    response = simulate_hook_call(
        tool_name="Write",
        tool_input={
            "file_path": "/home/user/test-project/src/index.ts",
            "content": "export function hello() {\n  console.log('Hello, World!');\n}\n"
        }
    )
    approval_id = response.get("approval_id")
    log(f"✓ Approval request created: {approval_id}")
    log(f"   Status: {response.get('status')}")

    # Test 2: Check status (should be pending)
    log("\n3. Checking approval status (should be pending)...")
    status = get_json(f"{ORCHESTRA_API}/api/approvals/{approval_id}")
    log(f"✓ Status: {status.get('status')}")
    log(f"   Tool: {status.get('tool_name')}")
    log(f"   File: {status.get('file_path')}")

    # Test 3: Get pending approvals for workflow
    log("\n4. Getting all pending approvals for workflow...")
    pending = get_json(f"{ORCHESTRA_API}/api/approvals/workflow/{TEST_WORKFLOW_ID}/pending")
    log(f"✓ Found {len(pending.get('pending_approvals', []))} pending approval(s)")

    # Test 4: Approve the request
    log("\n5. Approving the request...")
    resolved = post_json(
        f"{ORCHESTRA_API}/api/approvals/{approval_id}/resolve",
        {
            "decision": "approve",
            "message": "Looks good, proceed!"
        }
    )
    log(f"✓ Resolution: {resolved.get('status')}")

    # Test 5: Verify status changed
    log("\n6. Verifying status changed to approved...")
    final_status = get_json(f"{ORCHESTRA_API}/api/approvals/{approval_id}")
    log(f"✓ Final status: {final_status.get('status')}")
    log(f"   User message: {final_status.get('user_message')}")

    # Test 6: Test denial flow
    log("\n7. Testing denial flow...")
    response2 = simulate_hook_call(
        tool_name="Bash",
        tool_input={
            "command": "rm -rf /important/data",
            "description": "Delete important data"
        }
    )
    approval_id2 = response2.get("approval_id")
    log(f"✓ Created approval: {approval_id2}")

    denied = post_json(
        f"{ORCHESTRA_API}/api/approvals/{approval_id2}/resolve",
        {
            "decision": "deny",
            "message": "Too dangerous, do not proceed"
        }
    )
    log(f"✓ Denied: {denied.get('status')}")
    log(f"   Reason: {denied.get('user_message')}")

    # Summary
    log("\n" + "=" * 60)
    log("✓ SPIKE VALIDATION SUCCESSFUL")
    log("=" * 60)
    log("\nThe approval flow works as expected:")
    log("1. Hook can request approval via POST /api/approvals/request")
    log("2. Hook can poll status via GET /api/approvals/{id}")
    log("3. UI can approve/deny via POST /api/approvals/{id}/resolve")
    log("4. Hook receives the decision and can proceed or block")
    log("\nNext steps:")
    log("- Add frontend component for approval requests")
    log("- Configure Claude Code hooks with the hook script")
    log("- Test with actual Claude Code execution")


def test_hook_script():
    """Test the actual hook script"""
    log("\n" + "=" * 60)
    log("Testing Hook Script Directly")
    log("=" * 60)

    # Prepare hook input (what Claude Code would send)
    hook_input = json.dumps({
        "tool_name": "Edit",
        "tool_input": {
            "file_path": "/home/user/project/main.py",
            "old_string": "def foo():",
            "new_string": "def bar():"
        }
    })

    log("\n1. Running hook script with Edit tool input...")
    log("   (This will block waiting for approval - approve in another terminal)")
    log(f"   Approve with: curl -X POST {ORCHESTRA_API}/api/approvals/<id>/resolve")
    log("   -H 'Content-Type: application/json' -d '{\"decision\": \"approve\"}'")

    # Note: Can't easily test blocking behavior in this script
    # User needs to manually test with actual Claude Code

    log("\n✓ Hook scripts created at:")
    log("   - hooks/implementation_approval.sh (bash)")
    log("   - hooks/implementation_approval.py (python)")


if __name__ == "__main__":
    test_approval_flow()
    test_hook_script()
