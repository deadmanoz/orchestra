"""Test JSON extraction from noisy CLI output"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from backend.agents.cli_agent import JSONCLIAgent


def test_json_extraction():
    """Test the _extract_json_from_output method"""

    # Create a test agent instance
    class TestAgent(JSONCLIAgent):
        def get_cli_command(self, message: str):
            return ["echo", message]

        def extract_content_from_json(self, data: dict) -> str:
            return data.get("content", str(data))

    agent = TestAgent(name="test", agent_type="test", role="test")

    # Test cases
    test_cases = [
        # Case 1: Clean JSON
        (
            '{"content": "Hello world"}',
            '{"content": "Hello world"}'
        ),
        # Case 2: JSON with ANSI codes
        (
            '\x1B[32m{"content": "Hello world"}\x1B[0m',
            '{"content": "Hello world"}'
        ),
        # Case 3: JSON with extra output before
        (
            'Loading...\n{"content": "Hello world"}',
            '{"content": "Hello world"}'
        ),
        # Case 4: JSON with extra output after
        (
            '{"content": "Hello world"}\nDone!',
            '{"content": "Hello world"}'
        ),
        # Case 5: Multiple JSON objects (should take last one)
        (
            '{"status": "loading"}\n{"content": "Hello world"}',
            '{"content": "Hello world"}'
        ),
        # Case 6: Nested JSON
        (
            '{"response": {"content": "Hello world", "metadata": {}}}',
            '{"response": {"content": "Hello world", "metadata": {}}}'
        ),
    ]

    print("Testing JSON extraction...")
    print("=" * 60)

    for i, (input_str, expected) in enumerate(test_cases, 1):
        result = agent._extract_json_from_output(input_str)
        success = result == expected

        print(f"\nTest {i}: {'✅ PASS' if success else '❌ FAIL'}")
        print(f"Input:    {repr(input_str[:50])}...")
        print(f"Expected: {repr(expected[:50])}...")
        print(f"Got:      {repr(result[:50])}...")

        if not success:
            print(f"\nFull expected: {expected}")
            print(f"Full got:      {result}")

    print("\n" + "=" * 60)
    print("✅ JSON extraction tests completed!")


if __name__ == "__main__":
    test_json_extraction()
