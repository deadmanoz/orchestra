"""Claude Code CLI agent implementation"""

import logging
from typing import List

from backend.agents.cli_agent import JSONCLIAgent
from backend.config import settings

logger = logging.getLogger(__name__)


class ClaudeAgent(JSONCLIAgent):
    """
    Agent implementation for Claude Code CLI.

    Uses the Claude Code CLI with --print and --output-format json for structured output.
    Command format: claude --print --output-format json "<prompt>"

    Supports JSON schema via --json-schema flag for structured validation.
    """

    def __init__(
        self,
        name: str,
        role: str = "general",
        workspace_path: str = None,
        timeout: int = None
    ):
        super().__init__(
            name=name,
            agent_type="claude",
            role=role,
            workspace_path=workspace_path,
            timeout=timeout or settings.agent_timeout
        )
        self.cli_path = settings.claude_cli_path

    def get_cli_command(self, message: str) -> List[str]:
        """
        Build the Claude Code CLI command.

        Uses --print with --verbose and --output-format stream-json
        to avoid the 10KB truncation bug in regular json mode.

        Note: Claude Code CLI has a known bug where --output-format json truncates
        at fixed positions (4000, 6000, 8000, 10000, 12000, 16000 chars).
        Using stream-json requires --verbose flag when used with --print.

        Args:
            message: The prompt/message to send to Claude

        Returns:
            Command list: [claude_path, --print, --verbose, --output-format, stream-json, message]
        """
        return [
            self.cli_path,
            "--print",           # Non-interactive mode, print response and exit
            "--verbose",         # Required for stream-json with --print
            "--output-format",   # Specify output format
            "stream-json",       # Stream JSON to avoid 10KB truncation bug
            message              # Positional prompt argument
        ]

    def extract_content_from_json(self, data: dict) -> str:
        """
        Extract content from Claude Code's JSON response.

        Claude Code JSON structure may vary, but typically includes
        a 'content' field or similar. Adjust this based on actual output.

        Args:
            data: Parsed JSON response from Claude Code

        Returns:
            The extracted message content
        """
        # Try common JSON response patterns
        if isinstance(data, dict):
            # Pattern 1: 'result' field (from --output-format json)
            if 'result' in data:
                result = data['result']
                # If result is a string, return it directly
                if isinstance(result, str):
                    return result
                # If result is a dict with content, extract it
                if isinstance(result, dict) and 'content' in result:
                    return self._extract_string_content(result['content'])

            # Pattern 2: Direct 'content' field
            if 'content' in data:
                return self._extract_string_content(data['content'])

            # Pattern 3: 'message' field
            if 'message' in data:
                return data['message']

            # Pattern 4: Nested content in 'response'
            if 'response' in data and isinstance(data['response'], dict):
                if 'content' in data['response']:
                    return self._extract_string_content(data['response']['content'])

            # Pattern 5: List of messages (take last one)
            if 'messages' in data and isinstance(data['messages'], list) and len(data['messages']) > 0:
                last_message = data['messages'][-1]
                if isinstance(last_message, dict) and 'content' in last_message:
                    return self._extract_string_content(last_message['content'])

        # If we can't find content, log the structure and return as-is
        logger.warning(f"[{self.name}] Unexpected JSON structure, returning formatted JSON")
        logger.debug(f"[{self.name}] JSON keys: {list(data.keys()) if isinstance(data, dict) else 'not a dict'}")
        logger.debug(f"[{self.name}] Data sample: {str(data)[:500]}")

        # Fallback to parent class behavior
        return super().extract_content_from_json(data)

    def _extract_string_content(self, content) -> str:
        """
        Extract string from content that might be str, list, or dict.

        Args:
            content: Content value that could be various types

        Returns:
            String representation of the content
        """
        # If already a string, return it
        if isinstance(content, str):
            return content

        # If it's a list of content blocks (Claude API format)
        if isinstance(content, list):
            text_parts = []
            for block in content:
                if isinstance(block, dict):
                    # Handle {"type": "text", "text": "content"} format
                    if 'text' in block:
                        text_parts.append(block['text'])
                    # Handle other dict formats
                    elif 'content' in block:
                        text_parts.append(str(block['content']))
                elif isinstance(block, str):
                    text_parts.append(block)
            if text_parts:
                return '\n'.join(text_parts)

        # If it's a dict, try to extract text
        if isinstance(content, dict):
            if 'text' in content:
                return content['text']
            if 'value' in content:
                return str(content['value'])

        # Fallback: convert to string
        logger.warning(f"[{self.name}] Converting non-string content to string: {type(content)}")
        return str(content)
