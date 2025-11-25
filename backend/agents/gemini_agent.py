"""Gemini CLI agent implementation"""

import logging
from typing import List

from backend.agents.cli_agent import JSONCLIAgent
from backend.settings import settings

logger = logging.getLogger(__name__)


class GeminiAgent(JSONCLIAgent):
    """
    Agent implementation for Gemini CLI.

    Uses Gemini CLI with --output-format json for structured output.
    Command format: gemini -p "<prompt>" --output-format json

    Provides additional review perspective with Google's Gemini model.
    Supports yolo mode control via --yolo flag for auto-approval.
    """

    def __init__(
        self,
        name: str,
        role: str = "review",
        workspace_path: str = None,
        timeout: int = None,
        yolo_mode: bool = True,
        display_name: str = None
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
        self.yolo_mode = yolo_mode
        self.display_name = display_name or name

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
        cmd = [
            self.cli_path,
            "--output-format", "json",  # JSON output for parsing
            # No positional argument - message passed via stdin
        ]

        # Only add --yolo for non-review roles (implementation agents)
        # Review agents should not auto-approve actions
        if self.yolo_mode:
            cmd.append("--yolo")  # Auto-approve all actions (non-interactive)
            logger.debug(f"[{self.name}] Yolo mode enabled - agent will auto-approve actions")

        return cmd

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
            # Pattern 1: Direct 'response' field (Gemini CLI with --yolo + --output-format json)
            # This is the most common pattern with Gemini CLI
            if 'response' in data:
                response = data['response']
                if isinstance(response, str):
                    return response
                # If response is dict, try to extract text from it
                if isinstance(response, dict):
                    if 'text' in response:
                        return response['text']
                    if 'content' in response:
                        return response['content']

            # Pattern 2: Direct 'content' field
            if 'content' in data:
                return data['content']

            # Pattern 3: 'text' field (common in Gemini responses)
            if 'text' in data:
                return data['text']

            # Pattern 4: 'output' field
            if 'output' in data:
                return data['output']

            # Pattern 5: 'message' field
            if 'message' in data:
                return data['message']

            # Pattern 6: 'result' field
            if 'result' in data:
                result = data['result']
                if isinstance(result, str):
                    return result
                if isinstance(result, dict) and 'content' in result:
                    return result['content']

            # Pattern 7: Nested in 'response'
            if 'response' in data and isinstance(data['response'], dict):
                if 'content' in data['response']:
                    return data['response']['content']
                if 'text' in data['response']:
                    return data['response']['text']

            # Pattern 8: Candidates array (Gemini API response format)
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
