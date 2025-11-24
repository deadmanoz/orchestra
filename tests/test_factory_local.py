"""Test agent factory routing

This script tests that the AgentFactory correctly routes to the right
agent types based on agent names.

Prerequisites:
- Set USE_MOCK_AGENTS=false in .env to test real agent routing
- No CLI tools required (just tests routing logic)

Usage:
    python test_factory_local.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from backend.agents.factory import AgentFactory
from backend.settings import settings


async def test_factory_routing():
    """Test that factory creates correct agent types"""
    print("="*60)
    print("Testing Agent Factory Routing")
    print("="*60)

    print(f"\nConfiguration:")
    print(f"  USE_MOCK_AGENTS: {settings.use_mock_agents}")
    print(f"  CLAUDE_CLI_PATH: {settings.claude_cli_path}")
    print(f"  CODEX_CLI_PATH: {settings.codex_cli_path}")
    print(f"  GEMINI_CLI_PATH: {settings.gemini_cli_path}")

    if settings.use_mock_agents:
        print("\n⚠️  WARNING: USE_MOCK_AGENTS=true")
        print("   Factory will create MockAgent instances.")
        print("   Set USE_MOCK_AGENTS=false to test CLI agent routing.\n")

    factory = AgentFactory()

    # Test planning agent (Claude)
    print("\n1. Creating planning agent (claude_planner)...")
    planner = await factory.get_agent("planning", "claude_planner", "./workspace")
    print(f"   ✓ Name: {planner.name}")
    print(f"   ✓ Type: {planner.agent_type}")
    print(f"   ✓ Class: {planner.__class__.__name__}")
    print(f"   ✓ Role: {planner.role}")

    if not settings.use_mock_agents:
        assert planner.agent_type == "claude", f"Expected 'claude', got '{planner.agent_type}'"
        assert planner.__class__.__name__ == "ClaudeAgent", f"Expected ClaudeAgent, got {planner.__class__.__name__}"
        print(f"   ✓ CLI Path: {planner.cli_path}")

    # Test review agents
    print("\n2. Creating review agents...")
    reviewers = await factory.get_review_agents("./workspace")
    print(f"   ✓ Got {len(reviewers)} reviewers")

    for reviewer in reviewers:
        print(f"\n   Agent: {reviewer.name}")
        print(f"     - Type: {reviewer.agent_type}")
        print(f"     - Class: {reviewer.__class__.__name__}")
        print(f"     - Role: {reviewer.role}")
        if not settings.use_mock_agents:
            print(f"     - CLI Path: {getattr(reviewer, 'cli_path', 'N/A')}")

    if not settings.use_mock_agents:
        expected_types = ["claude", "codex", "gemini"]
        actual_types = [r.agent_type for r in reviewers]
        assert actual_types == expected_types, f"Expected {expected_types}, got {actual_types}"

        expected_classes = ["ClaudeAgent", "CodexAgent", "GeminiAgent"]
        actual_classes = [r.__class__.__name__ for r in reviewers]
        assert actual_classes == expected_classes, f"Expected {expected_classes}, got {actual_classes}"

    # Test unknown agent type (should fallback to mock)
    print("\n3. Testing unknown agent type (should fallback to mock)...")
    unknown = await factory.get_agent("test", "unknown_agent", "./workspace")
    print(f"   ✓ Name: {unknown.name}")
    print(f"   ✓ Type: {unknown.agent_type}")
    print(f"   ✓ Class: {unknown.__class__.__name__}")
    assert unknown.__class__.__name__ == "MockAgent", "Should fallback to MockAgent for unknown types"

    print("\n" + "="*60)
    print("✅ Factory routing test passed!")
    print("="*60)

    # Cleanup
    await factory.stop_all()
    print("\n✓ All agents stopped")


async def test_agent_caching():
    """Test that factory caches agents"""
    print("\n" + "="*60)
    print("Testing Agent Caching")
    print("="*60)

    factory = AgentFactory()

    # Get same agent twice
    print("\n1. Creating agent first time...")
    agent1 = await factory.get_agent("planning", "claude_planner", "./workspace")
    print(f"   ✓ Agent created: {agent1.name} (id: {id(agent1)})")

    print("\n2. Getting same agent again (should return cached)...")
    agent2 = await factory.get_agent("planning", "claude_planner", "./workspace")
    print(f"   ✓ Agent returned: {agent2.name} (id: {id(agent2)})")

    assert agent1 is agent2, "Should return same instance (cached)"
    print("\n   ✓ Caching works - same instance returned")

    # Cleanup
    await factory.stop_all()
    print("\n✓ Agents stopped")


async def main():
    """Run all factory tests"""
    try:
        await test_factory_routing()
        await test_agent_caching()

        print("\n" + "="*60)
        print("🎉 All factory tests passed!")
        print("="*60)

        return True

    except AssertionError as e:
        print(f"\n❌ Assertion failed: {e}")
        return False
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
