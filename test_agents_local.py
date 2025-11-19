"""Test script for CLI agents in local environment

This script tests individual CLI agents (Claude, Codex, Gemini) to verify
they work correctly with real CLI tools installed on your system.

Prerequisites:
- Install CLI tools: claude, codex, gemini (via npm)
- Configure API keys for each CLI
- Set USE_MOCK_AGENTS=false in .env

Usage:
    python test_agents_local.py

You can comment out individual tests if you don't have all CLIs installed.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from backend.agents.claude_agent import ClaudeAgent
from backend.agents.codex_agent import CodexAgent
from backend.agents.gemini_agent import GeminiAgent


async def test_claude_agent():
    """Test ClaudeAgent with real CLI"""
    print("\n" + "="*60)
    print("Testing ClaudeAgent")
    print("="*60)

    agent = ClaudeAgent(
        name="test_claude",
        role="planning",
        workspace_path="./workspace"
    )

    await agent.start()
    print(f"✓ Agent started: {agent.status}")

    try:
        # Simple test prompt
        prompt = "Write a Python function that calculates fibonacci numbers."
        print(f"\nSending prompt: {prompt}")

        response = await agent.send_message(prompt)
        print(f"\n✓ Received response ({len(response)} chars)")
        print("\nResponse preview:")
        print("-" * 60)
        print(response[:500] + "..." if len(response) > 500 else response)
        print("-" * 60)

        return True

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        await agent.stop()
        print(f"\n✓ Agent stopped: {agent.status}")


async def test_codex_agent():
    """Test CodexAgent with real CLI"""
    print("\n" + "="*60)
    print("Testing CodexAgent (with structured review schema)")
    print("="*60)

    agent = CodexAgent(
        name="test_codex",
        role="review",
        workspace_path="./workspace",
        use_review_schema=True
    )

    await agent.start()
    print(f"✓ Agent started: {agent.status}")
    print(f"✓ Using review schema: {agent.use_review_schema}")
    print(f"✓ Schema path: {agent.review_schema_path}")

    try:
        # Review prompt
        prompt = """Review this development plan:

## Plan: Add User Authentication

1. Set up JWT-based authentication
2. Create login/register endpoints
3. Add password hashing with bcrypt
4. Implement session management

Please provide a structured review."""

        print(f"\nSending review request...")

        response = await agent.send_message(prompt)
        print(f"\n✓ Received structured review ({len(response)} chars)")
        print("\nFormatted Review:")
        print("-" * 60)
        print(response[:1000] + "..." if len(response) > 1000 else response)
        print("-" * 60)

        return True

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        await agent.stop()
        print(f"\n✓ Agent stopped: {agent.status}")


async def test_gemini_agent():
    """Test GeminiAgent with real CLI"""
    print("\n" + "="*60)
    print("Testing GeminiAgent")
    print("="*60)

    agent = GeminiAgent(
        name="test_gemini",
        role="review",
        workspace_path="./workspace"
    )

    await agent.start()
    print(f"✓ Agent started: {agent.status}")

    try:
        # Review prompt
        prompt = "Review this architecture: Microservices with REST APIs, PostgreSQL database, Redis cache, and React frontend."

        print(f"\nSending prompt: {prompt}")

        response = await agent.send_message(prompt)
        print(f"\n✓ Received response ({len(response)} chars)")
        print("\nResponse preview:")
        print("-" * 60)
        print(response[:500] + "..." if len(response) > 500 else response)
        print("-" * 60)

        return True

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        await agent.stop()
        print(f"\n✓ Agent stopped: {agent.status}")


async def main():
    """Run all agent tests"""
    print("="*60)
    print("CLI Agent Local Testing")
    print("="*60)

    # Check environment
    print(f"\nEnvironment:")
    print(f"  USE_MOCK_AGENTS: {os.getenv('USE_MOCK_AGENTS', 'not set')}")
    print(f"  Workspace: ./workspace")

    # Warn if mock agents are enabled
    if os.getenv('USE_MOCK_AGENTS', 'true').lower() == 'true':
        print("\n⚠️  WARNING: USE_MOCK_AGENTS=true in .env")
        print("   Real CLI agents will NOT be used!")
        print("   Set USE_MOCK_AGENTS=false to test real agents.\n")

    results = {}

    # Test each agent
    print("\n" + "="*60)
    print("Running Tests...")
    print("="*60)

    # Test Claude (comment out if CLI not installed)
    try:
        results['claude'] = await test_claude_agent()
    except Exception as e:
        print(f"Claude test failed to run: {e}")
        results['claude'] = False

    # Test Codex (comment out if CLI not installed)
    try:
        results['codex'] = await test_codex_agent()
    except Exception as e:
        print(f"Codex test failed to run: {e}")
        results['codex'] = False

    # Test Gemini (comment out if CLI not installed)
    try:
        results['gemini'] = await test_gemini_agent()
    except Exception as e:
        print(f"Gemini test failed to run: {e}")
        results['gemini'] = False

    # Summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)

    for agent, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"  {agent.capitalize()}: {status}")

    all_passed = all(results.values())
    if all_passed:
        print("\n🎉 All tests passed!")
    else:
        print("\n⚠️  Some tests failed. Check errors above.")

    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
