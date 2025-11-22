"""Test fallback extraction from malformed JSON"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from backend.agents.cli_agent import JSONCLIAgent


def test_fallback_extraction():
    """Test the _fallback_extract_content method"""

    # Create a test agent instance
    class TestAgent(JSONCLIAgent):
        def get_cli_command(self, message: str):
            return ["echo", message]

        def extract_content_from_json(self, data: dict) -> str:
            return data.get("content", str(data))

    agent = TestAgent(name="test", agent_type="test", role="test")

    # Test cases
    test_cases = [
        # Case 1: Malformed JSON with result field
        (
            '{"type":"result","result":"This is the content',
            "This is the content"
        ),
        # Case 2: Malformed JSON with escaped newlines
        (
            '{"result":"Line 1\\nLine 2\\nLine 3',
            "Line 1\nLine 2\nLine 3"
        ),
        # Case 3: Malformed JSON with escaped quotes
        (
            '{"result":"He said \\"hello\\" to me',
            'He said "hello" to me'
        ),
        # Case 4: Very long result field that's truncated
        (
            '{"type":"result","subtype":"success","result":"' + "A" * 5000,
            "A" * 5000
        ),
        # Case 5: Content field instead of result
        (
            '{"content":"Some content here',
            "Some content here"
        ),
        # Case 6: Real-world-like example
        (
            '{"type":"result","duration_ms":1234,"result":"## Plan\\n\\n1. Step one\\n2. Step two',
            "## Plan\n\n1. Step one\n2. Step two"
        ),
    ]

    print("Testing fallback extraction...")
    print("=" * 60)

    for i, (input_str, expected) in enumerate(test_cases, 1):
        result = agent._fallback_extract_content(input_str)
        success = result == expected

        print(f"\nTest {i}: {'✅ PASS' if success else '❌ FAIL'}")
        if len(input_str) <= 100:
            print(f"Input:    {repr(input_str)}")
        else:
            print(f"Input:    {repr(input_str[:50])}... ({len(input_str)} chars)")
        print(f"Expected: {repr(expected[:50])}..." if len(expected) > 50 else f"Expected: {repr(expected)}")
        if result:
            print(f"Got:      {repr(result[:50])}..." if len(result) > 50 else f"Got:      {repr(result)}")
        else:
            print(f"Got:      None")

        if not success:
            print(f"\n❌ MISMATCH:")
            print(f"  Expected length: {len(expected)}")
            print(f"  Got length:      {len(result) if result else 0}")
            if result:
                print(f"  First diff at:   {next((i for i, (a, b) in enumerate(zip(expected, result)) if a != b), len(expected))}")

    print("\n" + "=" * 60)
    print("✅ Fallback extraction tests completed!")


if __name__ == "__main__":
    test_fallback_extraction()
