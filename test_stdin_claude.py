"""
Quick test to verify Claude CLI works with stdin and stream-json format.

This tests the exact configuration Orchestra uses:
  echo "prompt" | claude --output-format stream-json

Prerequisites:
- Claude CLI installed
- API key configured

Usage:
    python test_stdin_claude.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from backend.agents.claude_agent import ClaudeAgent


async def test_claude_with_stdin():
    """Test Claude CLI agent with stdin-based communication"""

    print("=" * 80)
    print("Testing Claude CLI with stdin + stream-json")
    print("=" * 80)
    print()

    agent = ClaudeAgent(
        name="test_claude",
        role="planning",
        workspace_path="."
    )

    print(f"✓ Created agent: {agent.name}")
    print(f"  - CLI path: {agent.cli_path}")
    print(f"  - Use stdin: {agent.use_stdin}")
    print(f"  - Timeout: {agent.timeout}s")
    print()

    await agent.start()
    print(f"✓ Agent started: {agent.status}")
    print()

    # Simple test prompt
    test_prompt = "Write a one-sentence description of what Python list comprehensions are."

    print(f"Test prompt: {test_prompt}")
    print(f"Command: {' '.join(agent.get_cli_command(test_prompt))}")
    print(f"(Prompt will be sent via stdin)")
    print()
    print("Sending message...")
    print("-" * 80)

    try:
        response = await agent.send_message(test_prompt)

        print()
        print("-" * 80)
        print(f"✅ SUCCESS! Received response ({len(response)} chars)")
        print()
        print("Response:")
        print("-" * 80)
        print(response)
        print("-" * 80)

        return True

    except Exception as e:
        print()
        print("-" * 80)
        print(f"❌ FAILED: {e}")
        print("-" * 80)

        import traceback
        traceback.print_exc()

        return False

    finally:
        await agent.stop()
        print()
        print(f"✓ Agent stopped")


async def main():
    print()
    print("This test verifies that:")
    print("  1. Claude CLI accepts input via stdin")
    print("  2. --output-format stream-json works without --print")
    print("  3. We correctly extract type='result' messages")
    print("  4. No JSON parsing errors occur")
    print()
    input("Press Enter to continue...")
    print()

    success = await test_claude_with_stdin()

    print()
    print("=" * 80)
    if success:
        print("✅ Test PASSED - stdin approach works!")
        print()
        print("Next steps:")
        print("  1. Restart your backend server")
        print("  2. Try running a workflow")
        print("  3. Check logs for [claude_planner] messages")
    else:
        print("❌ Test FAILED - see error above")
        print()
        print("Common issues:")
        print("  - Claude CLI not installed: brew install anthropics/claude/claude")
        print("  - API key not configured: claude login")
        print("  - Check stderr output in logs")

    print("=" * 80)
    print()

    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
