"""Claude Code CLI agent implementation"""

import logging
from typing import List

from backend.agents.cli_agent import JSONCLIAgent
from backend.settings import settings

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
            timeout=timeout or settings.agent_timeout,
            use_stdin=True  # Claude CLI works better with stdin for stream-json
        )
        self.cli_path = settings.claude_cli_path

    def get_cli_command(self, message: str) -> List[str]:
        """
        Build the Claude Code CLI command.

        Using --output-format json (not stream-json) to get complete response as single JSON blob.
        stream-json has a bug where subprocess terminates before flushing final message to stdout.

        Args:
            message: The prompt/message to send to Claude (passed via stdin, not used here)

        Returns:
            Command list without the message (message goes to stdin)
        """
        return [
            self.cli_path,
            "--output-format",   # Specify output format
            "json",              # Single JSON blob (not streaming) to avoid truncation
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
        # SAFETY CHECK: Reject system initialization messages
        # These have type="system" and subtype="init" and should never be used as agent output
        if isinstance(data, dict):
            if data.get('type') == 'system':
                error_msg = (
                    f"[{self.name}] ERROR: Received system message instead of result message! "
                    f"subtype={data.get('subtype')}, This indicates the stream-json filtering failed."
                )
                logger.error(error_msg)
                logger.error(f"[{self.name}] System message data: {str(data)[:500]}")
                raise ValueError(error_msg)

        # Try common JSON response patterns
        if isinstance(data, dict):
            # Log the message type for debugging
            msg_type = data.get('type', 'unknown')
            logger.info(f"[{self.name}] Extracting content from message type='{msg_type}'")

            # Pattern 1: 'result' field (from --output-format json)
            if 'result' in data:
                result = data['result']
                logger.debug(f"[{self.name}] Found 'result' field, type={type(result).__name__}")
                # If result is a string, return it directly
                if isinstance(result, str):
                    logger.info(f"[{self.name}] Returning string result, length={len(result)}")
                    return result
                # If result is a dict with content, extract it
                if isinstance(result, dict) and 'content' in result:
                    extracted = self._extract_string_content(result['content'])
                    logger.info(f"[{self.name}] Extracted content from result dict, length={len(extracted)}")
                    return extracted

            # Pattern 2: type=assistant with nested message object (stream-json format)
            if data.get('type') == 'assistant' and 'message' in data:
                message = data['message']
                logger.debug(f"[{self.name}] Found assistant-type with nested message")
                if isinstance(message, dict) and 'content' in message:
                    extracted = self._extract_string_content(message['content'])
                    logger.info(f"[{self.name}] Extracted content from assistant message, length={len(extracted)}")
                    return extracted

            # Pattern 3: Direct 'content' field
            if 'content' in data:
                return self._extract_string_content(data['content'])

            # Pattern 4: 'message' field (string)
            if 'message' in data and isinstance(data['message'], str):
                return data['message']

            # Pattern 5: Nested content in 'response'
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
                    block_type = block.get('type', '')
                    # ONLY extract text from text-type blocks
                    if block_type == 'text' and 'text' in block:
                        text_parts.append(block['text'])
                    # Skip tool_use and tool_result blocks - they're not the actual response
                    elif block_type in ('tool_use', 'tool_result'):
                        continue
                    # Fallback: extract text field if present (no type or unknown type)
                    elif 'text' in block:
                        text_parts.append(block['text'])
                    # Handle other dict formats
                    elif 'content' in block:
                        text_parts.append(str(block['content']))
                elif isinstance(block, str):
                    text_parts.append(block)

            if text_parts:
                return '\n'.join(text_parts)
            else:
                # No text content found - might be a message with only tool calls
                block_types = [b.get('type', 'unknown') if isinstance(b, dict) else 'string' for b in content]
                logger.warning(f"[{self.name}] Content list has no text blocks (only {block_types}), might be intermediate tool message")
                # Return empty string for intermediate messages, not the raw structure
                return ""

        # If it's a dict, try to extract text
        if isinstance(content, dict):
            if 'text' in content:
                return content['text']
            if 'value' in content:
                return str(content['value'])

        # Fallback: convert to string
        logger.warning(f"[{self.name}] Converting non-string content to string: {type(content)}")
        return str(content)
