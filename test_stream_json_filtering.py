"""Test stream-json filtering for type='result' messages"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from backend.agents.cli_agent import JSONCLIAgent
import json


def test_stream_json_filtering():
    """Test that we correctly filter for type='result' messages in stream-json format"""

    # Create a test agent instance
    class TestAgent(JSONCLIAgent):
        def get_cli_command(self, message: str):
            return ["echo", message]

        def extract_content_from_json(self, data: dict) -> str:
            return data.get("result", str(data))

    agent = TestAgent(name="test", agent_type="test", role="test")

    # Simulate stream-json output from Claude CLI with --verbose --output-format stream-json
    # This is NDJSON format - one JSON object per line
    stream_json_output = """{"type":"system","subtype":"init","session_id":"abc123","model":"claude-sonnet-4"}
{"type":"thinking","content":"Analyzing the requirements..."}
{"type":"result","result":"This is the actual plan content that should be extracted"}"""

    print("Testing stream-json filtering...")
    print("=" * 80)
    print("\nInput (3 lines of NDJSON):")
    for i, line in enumerate(stream_json_output.split('\n'), 1):
        obj = json.loads(line)
        print(f"  Line {i}: type={obj.get('type')}, subtype={obj.get('subtype', 'N/A')}")

    # Extract JSON - should find and return the type="result" message
    result = agent._extract_json_from_output(stream_json_output)

    print(f"\nExtracted JSON:")
    print(f"  {result}")

    # Verify it's the result message
    result_obj = json.loads(result)

    print(f"\nParsed object:")
    print(f"  type = {result_obj.get('type')}")
    print(f"  result = {result_obj.get('result', 'N/A')}")

    # Assertions
    assert result_obj.get('type') == 'result', f"Expected type='result', got type='{result_obj.get('type')}'"
    assert result_obj.get('result') == "This is the actual plan content that should be extracted", \
        "Expected the result content to match"

    print("\n" + "=" * 80)
    print("✅ Stream-JSON filtering test PASSED!")
    print("   - Correctly filtered for type='result' message")
    print("   - Ignored system and thinking messages")
    print("   - Extracted the actual plan content")


def test_stream_json_no_result():
    """Test behavior when no type='result' message is present (error case)"""

    class TestAgent(JSONCLIAgent):
        def get_cli_command(self, message: str):
            return ["echo", message]

        def extract_content_from_json(self, data: dict) -> str:
            return data.get("result", str(data))

    agent = TestAgent(name="test", agent_type="test", role="test")

    # Simulate incomplete stream-json output (CLI failed before outputting result)
    incomplete_output = """{"type":"system","subtype":"init","session_id":"abc123","model":"claude-sonnet-4"}
{"type":"thinking","content":"Analyzing..."}"""

    print("\n\nTesting stream-json with NO result message...")
    print("=" * 80)
    print("\nInput (2 lines, no type='result'):")
    for i, line in enumerate(incomplete_output.split('\n'), 1):
        obj = json.loads(line)
        print(f"  Line {i}: type={obj.get('type')}")

    # Extract JSON - should fall back to last valid JSON (with warning)
    result = agent._extract_json_from_output(incomplete_output)

    print(f"\nExtracted JSON (fallback):")
    print(f"  {result}")

    # Verify it fell back to the last message (thinking message)
    result_obj = json.loads(result)

    print(f"\nParsed object:")
    print(f"  type = {result_obj.get('type')}")

    assert result_obj.get('type') == 'thinking', \
        f"Expected fallback to last message (type='thinking'), got type='{result_obj.get('type')}'"

    print("\n" + "=" * 80)
    print("⚠️  Fallback behavior verified!")
    print("   - No type='result' message found")
    print("   - Correctly fell back to last valid JSON")
    print("   - This simulates a CLI failure scenario")


if __name__ == "__main__":
    test_stream_json_filtering()
    test_stream_json_no_result()
    print("\n" + "=" * 80)
    print("✅ All stream-JSON tests completed!")
