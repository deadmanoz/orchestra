"""Gemini CLI agent implementation"""

import logging
from typing import List

from backend.agents.cli_agent import JSONCLIAgent
from backend.config import settings

logger = logging.getLogger(__name__)


class GeminiAgent(JSONCLIAgent):
    """
    Agent implementation for Gemini CLI.

    Uses Gemini CLI with --output-format json for structured output.
    Command format: gemini -p "<prompt>" --output-format json

    Provides additional review perspective with Google's Gemini model.
    """

    def __init__(
        self,
        name: str,
        role: str = "review",
        workspace_path: str = None,
        timeout: int = None
    ):
        super().__init__(
            name=name,
            agent_type="gemini",
            role=role,
            workspace_path=workspace_path,
            timeout=timeout or settings.agent_timeout,
            use_stdin=True  # Use stdin to avoid argument length limits and work with file-based stdout
        )
        self.cli_path = settings.gemini_cli_path

    def get_cli_command(self, message: str) -> List[str]:
        """
        Build the Gemini CLI command.

        Uses stdin for input to work with file-based stdout redirection.
        Gemini CLI reads from stdin when no positional prompt is provided.

        Args:
            message: The prompt/message to send to Gemini (passed via stdin, not used here)

        Returns:
            Command list with appropriate flags
        """
        return [
            self.cli_path,
            "--output-format", "json",  # JSON output for parsing
            "--yolo",                    # Auto-approve all actions (non-interactive)
            # No positional argument - message passed via stdin
        ]

    def extract_content_from_json(self, data: dict) -> str:
        """
        Extract content from Gemini's JSON response.

        Gemini CLI JSON structure may vary based on mode and version.
        Handle common patterns.

        Args:
            data: Parsed JSON response from Gemini

        Returns:
            The extracted message content
        """
        if isinstance(data, dict):
            # Pattern 1: Direct 'content' field
            if 'content' in data:
                return data['content']

            # Pattern 2: 'text' field (common in Gemini responses)
            if 'text' in data:
                return data['text']

            # Pattern 3: 'output' field
            if 'output' in data:
                return data['output']

            # Pattern 4: 'message' field
            if 'message' in data:
                return data['message']

            # Pattern 5: 'result' field
            if 'result' in data:
                result = data['result']
                if isinstance(result, str):
                    return result
                if isinstance(result, dict) and 'content' in result:
                    return result['content']

            # Pattern 6: Nested in 'response'
            if 'response' in data and isinstance(data['response'], dict):
                if 'content' in data['response']:
                    return data['response']['content']
                if 'text' in data['response']:
                    return data['response']['text']

            # Pattern 7: Candidates array (Gemini API response format)
            if 'candidates' in data and isinstance(data['candidates'], list) and len(data['candidates']) > 0:
                candidate = data['candidates'][0]
                if isinstance(candidate, dict):
                    if 'content' in candidate:
                        content = candidate['content']
                        if isinstance(content, dict) and 'parts' in content:
                            parts = content['parts']
                            if isinstance(parts, list) and len(parts) > 0:
                                if isinstance(parts[0], dict) and 'text' in parts[0]:
                                    return parts[0]['text']
                    if 'output' in candidate:
                        return candidate['output']

        # Fallback to parent class behavior
        logger.warning(f"[{self.name}] Unexpected JSON structure, using fallback")
        logger.debug(f"[{self.name}] JSON keys: {list(data.keys()) if isinstance(data, dict) else 'not a dict'}")
        return super().extract_content_from_json(data)
