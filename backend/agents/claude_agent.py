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
                return data['result']

            # Pattern 2: Direct 'content' field
            if 'content' in data:
                return data['content']

            # Pattern 3: 'message' field
            if 'message' in data:
                return data['message']

            # Pattern 4: Nested content in 'response'
            if 'response' in data and isinstance(data['response'], dict):
                if 'content' in data['response']:
                    return data['response']['content']

            # Pattern 5: List of messages (take last one)
            if 'messages' in data and isinstance(data['messages'], list) and len(data['messages']) > 0:
                last_message = data['messages'][-1]
                if isinstance(last_message, dict) and 'content' in last_message:
                    return last_message['content']

        # If we can't find content, log the structure and return as-is
        logger.warning(f"[{self.name}] Unexpected JSON structure, returning formatted JSON")
        logger.debug(f"[{self.name}] JSON keys: {list(data.keys()) if isinstance(data, dict) else 'not a dict'}")

        # Fallback to parent class behavior
        return super().extract_content_from_json(data)
