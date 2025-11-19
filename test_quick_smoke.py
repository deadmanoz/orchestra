"""Quick smoke test for CLI agent setup

This is the fastest way to verify your CLI agents are configured correctly.
No actual CLI execution - just validates configuration and imports.

Usage:
    python test_quick_smoke.py
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

import asyncio
from backend.agents.factory import agent_factory
from backend.config import settings


async def smoke_test():
    """Quick smoke test - verify configuration and agent creation"""
    print("="*60)
    print("Quick Smoke Test - CLI Agent Configuration")
    print("="*60)

    # Check configuration
    print("\nConfiguration:")
    print(f"  USE_MOCK_AGENTS: {settings.use_mock_agents}")
    print(f"  AGENT_TIMEOUT: {settings.agent_timeout}s")
    print(f"  CLAUDE_CLI_PATH: {settings.claude_cli_path}")
    print(f"  CODEX_CLI_PATH: {settings.codex_cli_path}")
    print(f"  GEMINI_CLI_PATH: {settings.gemini_cli_path}")

    # Check if CLIs are in PATH (if not using mocks)
    if not settings.use_mock_agents:
        import shutil
        print("\nCLI Availability:")
        for cli_name, cli_path in [
            ("Claude", settings.claude_cli_path),
            ("Codex", settings.codex_cli_path),
            ("Gemini", settings.gemini_cli_path)
        ]:
            full_path = shutil.which(cli_path)
            if full_path:
                print(f"  ✓ {cli_name}: {full_path}")
            else:
                print(f"  ✗ {cli_name}: Not found in PATH")

    # Test agent creation
    print("\nCreating test agent...")
    agent = await agent_factory.get_agent('planning', 'claude_planner', './workspace')
    print(f"  ✓ Agent created: {agent.name}")
    print(f"  ✓ Type: {agent.agent_type}")
    print(f"  ✓ Class: {agent.__class__.__name__}")
    print(f"  ✓ Role: {agent.role}")
    if hasattr(agent, 'cli_path'):
        print(f"  ✓ CLI path: {agent.cli_path}")
    print(f"  ✓ Status: {agent.status}")

    # Test review agents
    print("\nCreating review agents...")
    reviewers = await agent_factory.get_review_agents('./workspace')
    print(f"  ✓ Created {len(reviewers)} reviewers")
    for reviewer in reviewers:
        print(f"    - {reviewer.name}: {reviewer.__class__.__name__}")

    # Cleanup
    await agent_factory.stop_all()
    print("\n✓ All agents stopped")

    print("\n" + "="*60)
    print("✅ Smoke test passed!")
    print("="*60)

    if settings.use_mock_agents:
        print("\nℹ️  You're using mock agents.")
        print("   Set USE_MOCK_AGENTS=false in .env to use real CLI agents.")
    else:
        print("\nℹ️  Real CLI agents configured.")
        print("   Run test_agents_local.py to test actual CLI execution.")


if __name__ == "__main__":
    try:
        asyncio.run(smoke_test())
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Smoke test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
