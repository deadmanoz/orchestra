# Local Testing Guide for CLI Agents

This guide will help you test the CLI agent integration (ClaudeAgent, CodexAgent, GeminiAgent) in your local development environment.

## Prerequisites

### 1. Install CLI Tools

You'll need to install the CLI tools for the agents you want to test.

#### Claude Code CLI
```bash
# Install via npm (requires Node.js)
npm install -g @anthropic-ai/claude-code

# Verify installation
claude --version

# Configure with your API key (one-time setup)
# Follow the prompts to enter your Anthropic API key
claude
```

#### Codex CLI
```bash
# Install via npm
npm install -g openai-codex

# Verify installation
codex --version

# Configure with your OpenAI API key
# Set environment variable or follow CLI setup prompts
export OPENAI_API_KEY=your_openai_api_key_here
```

#### Gemini CLI
```bash
# Install via npm
npm install -g @google/gemini-cli

# Verify installation
gemini --version

# Configure with your Google API key
export GOOGLE_API_KEY=your_google_api_key_here
```

### 2. Verify CLI Tools Work

Before testing with Orchestra, verify each CLI works independently:

```bash
# Test Claude Code
claude -p "Write a hello world function in Python" --json

# Test Codex
codex -p "Review this code: print('hello')" --json --quiet

# Test Gemini
gemini -p "Explain async/await in Python" --output-format json
```

If these commands work, the CLIs are ready for integration!

## Configuration

### 1. Set Up Environment Variables

Create or edit `.env` file in the Orchestra root directory:

```bash
# Copy example to .env if you haven't already
cp .env.example .env
```

Edit `.env`:

```bash
# IMPORTANT: Set to false to use real CLI agents
USE_MOCK_AGENTS=false

# Timeout for agent execution (in seconds)
AGENT_TIMEOUT=300

# CLI paths (customize if not in PATH)
CLAUDE_CLI_PATH=claude
CODEX_CLI_PATH=codex
GEMINI_CLI_PATH=gemini

# API Keys (optional - CLIs use their own config)
# Only needed if you want to pass keys explicitly
# ANTHROPIC_API_KEY=your_key_here
# OPENAI_API_KEY=your_key_here
# GOOGLE_API_KEY=your_key_here
```

### 2. Verify Configuration

Test that Orchestra can find and use the CLIs:

```bash
python -c "from backend.config import settings; print(f'Mock agents: {settings.use_mock_agents}'); print(f'Claude CLI: {settings.claude_cli_path}')"
```

Expected output:
```
Mock agents: False
Claude CLI: claude
```

## Testing Strategies

### Strategy 1: Unit Testing Individual Agents

Test each agent type in isolation.

#### Create Test Script: `test_agents_local.py`

```python
"""Test script for CLI agents in local environment"""

import asyncio
import os
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
    exit(0 if success else 1)
```

#### Run the Test

```bash
# Make sure .env has USE_MOCK_AGENTS=false
python test_agents_local.py
```

### Strategy 2: Testing with Agent Factory

Test that the factory correctly routes to CLI agents:

#### Create Test Script: `test_factory_local.py`

```python
"""Test agent factory routing"""

import asyncio
from backend.agents.factory import AgentFactory


async def test_factory_routing():
    """Test that factory creates correct agent types"""
    print("Testing Agent Factory Routing\n")

    factory = AgentFactory()

    # Test planning agent (Claude)
    print("1. Creating planning agent (claude_planner)...")
    planner = await factory.get_agent("planning", "claude_planner", "./workspace")
    print(f"   ✓ Type: {planner.agent_type}")
    print(f"   ✓ Class: {planner.__class__.__name__}")
    assert planner.agent_type == "claude", "Should create ClaudeAgent"

    # Test review agents
    print("\n2. Creating review agents...")
    reviewers = await factory.get_review_agents("./workspace")
    print(f"   ✓ Got {len(reviewers)} reviewers")

    for reviewer in reviewers:
        print(f"   - {reviewer.name}: {reviewer.__class__.__name__} (type: {reviewer.agent_type})")

    expected_types = ["claude", "codex", "gemini"]
    actual_types = [r.agent_type for r in reviewers]
    assert actual_types == expected_types, f"Expected {expected_types}, got {actual_types}"

    print("\n✅ Factory routing test passed!")

    # Cleanup
    await factory.stop_all()


if __name__ == "__main__":
    asyncio.run(test_factory_routing())
```

#### Run the Test

```bash
python test_factory_local.py
```

### Strategy 3: End-to-End Workflow Testing

Test the full PlanReviewWorkflow with real agents.

#### Start the Backend Server

```bash
# Terminal 1: Start backend
cd backend
uvicorn main:app --reload --port 3030
```

#### Start the Frontend

```bash
# Terminal 2: Start frontend
cd frontend
npm install  # if not done already
npm run dev
```

#### Create a Workflow

1. Open browser to `http://localhost:5173`
2. Fill out the "Create Workflow" form:
   - **Task Description**: "Build a REST API for a todo application"
   - **Workspace Path**: `./workspace/test-project`
3. Click "Start Workflow"

#### Monitor Execution

Watch the workflow execute with real CLI agents:
- **Planning phase**: Claude Code generates the plan
- **Review phase**: Codex, Gemini, and Claude all review in parallel
- **Checkpoints**: Review and approve at each checkpoint

Check backend logs to see subprocess execution:
```
[claude_planner] Sending message (length: 150 chars)
[claude_planner] Command: claude --json -p ...
[claude_planner] Response received (length: 2500 chars)
```

### Strategy 4: Quick Smoke Test

Minimal test to verify everything is wired up:

```bash
python -c "
import asyncio
from backend.agents.factory import agent_factory

async def smoke_test():
    agent = await agent_factory.get_agent('planning', 'claude_planner', './workspace')
    print(f'Agent: {agent.name} ({agent.agent_type})')
    print(f'CLI: {agent.cli_path}')
    await agent_factory.stop_all()

asyncio.run(smoke_test())
"
```

Expected output:
```
Agent: claude_planner (claude)
CLI: claude
```

## Troubleshooting

### Issue: "Command not found" Error

**Problem**: CLI agent executable not found

**Solution**:
```bash
# Check if CLI is in PATH
which claude  # Should show path like /usr/local/bin/claude

# If not found, install it
npm install -g @anthropic-ai/claude-code

# Or set full path in .env
CLAUDE_CLI_PATH=/full/path/to/claude
```

### Issue: "API Key not configured"

**Problem**: CLI doesn't have API key

**Solution**:
```bash
# Run CLI setup (interactive)
claude  # Follow prompts to enter API key

# Or set environment variable
export ANTHROPIC_API_KEY=your_key_here

# Verify
claude -p "test" --json
```

### Issue: Timeout Errors

**Problem**: Agent takes longer than 5 minutes (default timeout)

**Solution**:
```bash
# Increase timeout in .env
AGENT_TIMEOUT=600  # 10 minutes
```

### Issue: JSON Parse Errors

**Problem**: CLI returns non-JSON output

**Solution**:
1. Test CLI directly: `claude -p "test" --json`
2. Check CLI version: `claude --version`
3. Verify `--json` flag is supported
4. Check agent logs for actual output received

### Issue: Mock Agents Still Being Used

**Problem**: Tests use MockAgent instead of CLI agents

**Solution**:
```bash
# Make sure .env has:
USE_MOCK_AGENTS=false

# Restart backend if it's running
# Backend loads .env at startup
```

### Issue: Workspace Path Not Found

**Problem**: Agent can't access workspace directory

**Solution**:
```bash
# Create workspace directory
mkdir -p ./workspace

# Check permissions
ls -la ./workspace

# Use absolute path if needed
WORKSPACE_PATH=/full/path/to/workspace
```

## Expected Results

### Successful ClaudeAgent Test

```
Testing ClaudeAgent
============================================================
✓ Agent started: running

Sending prompt: Write a Python function that calculates fibonacci numbers.

✓ Received response (543 chars)

Response preview:
------------------------------------------------------------
def fibonacci(n):
    """Calculate the nth Fibonacci number."""
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)
------------------------------------------------------------

✓ Agent stopped: stopped
```

### Successful CodexAgent Test

```
Testing CodexAgent (with structured review schema)
============================================================
✓ Agent started: running
✓ Using review schema: True

Sending review request...

✓ Received structured review (2841 chars)

Formatted Review:
------------------------------------------------------------
# Code Review by test_codex

## Overall Assessment

**Verdict:** Approve With Changes (Confidence: 85.0%)

The plan provides a solid foundation for user authentication...

## Metrics
- **Code Quality:** 7/10
- **Security:** 6/10
...
------------------------------------------------------------
```

### Successful Factory Test

```
Testing Agent Factory Routing

1. Creating planning agent (claude_planner)...
   ✓ Type: claude
   ✓ Class: ClaudeAgent

2. Creating review agents...
   ✓ Got 3 reviewers
   - claude_reviewer: ClaudeAgent (type: claude)
   - codex_reviewer: CodexAgent (type: codex)
   - gemini_reviewer: GeminiAgent (type: gemini)

✅ Factory routing test passed!
```

## Next Steps

Once local testing is successful:

1. **Integrate with CI/CD** - Add agent tests to your CI pipeline
2. **Monitor Performance** - Track agent response times and costs
3. **Tune Prompts** - Optimize prompts for better agent outputs
4. **Scale Up** - Test with larger, real-world projects
5. **Production Deploy** - Deploy with real agents enabled

## Tips for Effective Testing

1. **Start Small**: Test with simple prompts first
2. **Check Logs**: Monitor backend logs for subprocess output
3. **One at a Time**: Test agents individually before testing all together
4. **Version Check**: Ensure CLI tools are up-to-date
5. **Cost Awareness**: CLI agents make real API calls - monitor usage
6. **Timeout Tuning**: Adjust timeouts based on your task complexity
7. **Error Handling**: Test failure scenarios (invalid API keys, network issues)

## Getting Help

If you encounter issues:

1. Check the main [CLI Agent Integration Guide](CLI_AGENT_INTEGRATION.md)
2. Review agent logs in backend output
3. Test CLI tools independently
4. Verify environment variables are set correctly
5. Check that USE_MOCK_AGENTS=false in .env

Happy testing! 🚀
