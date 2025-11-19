"""Base class for CLI-based agents that run as subprocesses"""

import asyncio
import json
import logging
import re
from abc import abstractmethod
from typing import Optional, List
from pathlib import Path

from backend.agents.base import AgentInterface

logger = logging.getLogger(__name__)


class CLIAgentError(Exception):
    """Exception raised for CLI agent errors"""
    pass


class CLIAgent(AgentInterface):
    """Base class for all CLI-based agents using subprocess communication"""

    def __init__(
        self,
        name: str,
        agent_type: str,
        role: str = "general",
        workspace_path: Optional[str] = None,
        timeout: int = 300,
        use_stdin: bool = False
    ):
        super().__init__(name, agent_type)
        self.role = role
        self.workspace_path = workspace_path or "."
        self.timeout = timeout
        self.use_stdin = use_stdin  # Whether to pass message via stdin instead of CLI args
        self.process: Optional[asyncio.subprocess.Process] = None

    @abstractmethod
    def get_cli_command(self, message: str) -> List[str]:
        """
        Return the CLI command to execute for sending a message.

        Args:
            message: The message/prompt to send to the agent

        Returns:
            List of command arguments (e.g., ["claude", "--json", "-p", message])
        """
        pass

    @abstractmethod
    async def parse_response(self, stdout: str, stderr: str) -> str:
        """
        Parse the CLI output into a clean response.

        Args:
            stdout: Standard output from the CLI process
            stderr: Standard error from the CLI process

        Returns:
            Parsed response string
        """
        pass

    async def start(self) -> None:
        """Initialize the agent (CLI agents are stateless, so this just sets status)"""
        logger.info(f"Starting CLI agent: {self.name} (type: {self.agent_type}, role: {self.role})")
        self.status = "running"

    async def send_message(self, content: str, **kwargs) -> str:
        """
        Send a message to the CLI agent and get the response.

        Args:
            content: The message/prompt to send
            **kwargs: Additional arguments (unused for now)

        Returns:
            Agent's response as a string

        Raises:
            CLIAgentError: If the subprocess fails or times out
        """
        logger.info(f"[{self.name}] Sending message (length: {len(content)} chars)")

        # Get the CLI command
        command = self.get_cli_command(content)

        if self.use_stdin:
            logger.debug(f"[{self.name}] Command: {' '.join(command)} (will send {len(content)} chars via stdin)")
        else:
            logger.debug(f"[{self.name}] Command: {' '.join(command[:5])}... (message in args)")

        try:
            # Execute the CLI command
            # Pass message via stdin if use_stdin=True, for better handling of multi-line prompts
            stdin_pipe = asyncio.subprocess.PIPE if self.use_stdin else None

            # Start subprocess in new session to prevent interference when running
            # multiple instances in parallel (prevents terminal/signal conflicts)
            process = await asyncio.create_subprocess_exec(
                *command,
                stdin=stdin_pipe,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.workspace_path,
                start_new_session=True  # Detach from controlling terminal
            )

            self.process = process

            # Send the message via stdin if enabled, otherwise just wait
            try:
                if self.use_stdin:
                    stdin_bytes = content.encode('utf-8')
                    logger.info(f"[{self.name}] Sending {len(stdin_bytes)} bytes via stdin")
                    logger.debug(f"[{self.name}] Prompt preview (first 200 chars): {content[:200]!r}")

                    stdout, stderr = await asyncio.wait_for(
                        process.communicate(input=stdin_bytes),
                        timeout=self.timeout
                    )
                    logger.info(f"[{self.name}] Process completed, parsing output...")
                else:
                    stdout, stderr = await asyncio.wait_for(
                        process.communicate(),
                        timeout=self.timeout
                    )
            except asyncio.TimeoutError:
                # Kill the process if it times out
                process.kill()
                await process.wait()
                raise CLIAgentError(
                    f"Agent {self.name} timed out after {self.timeout} seconds"
                )

            # Check return code
            if process.returncode != 0:
                error_msg = stderr.decode('utf-8', errors='replace')
                logger.error(f"[{self.name}] Process failed with code {process.returncode}: {error_msg}")
                raise CLIAgentError(
                    f"Agent {self.name} failed with exit code {process.returncode}: {error_msg}"
                )

            # Parse the response
            stdout_str = stdout.decode('utf-8', errors='replace')
            stderr_str = stderr.decode('utf-8', errors='replace')

            # Log raw output lengths for diagnostics
            logger.info(f"[{self.name}] Raw output: stdout={len(stdout_str)} chars, stderr={len(stderr_str)} chars, returncode={process.returncode}")

            # Log stderr if present (might contain warnings/info)
            if stderr_str.strip():
                logger.warning(f"[{self.name}] stderr: {stderr_str[:500]}")  # Limit to 500 chars

            # Log first and last part of stdout for diagnostics
            if stdout_str:
                logger.debug(f"[{self.name}] stdout (first 300 chars): {stdout_str[:300]}")
                if len(stdout_str) > 600:
                    logger.debug(f"[{self.name}] stdout (last 300 chars): ...{stdout_str[-300:]}")
            else:
                logger.error(f"[{self.name}] CLI returned EMPTY stdout!")

            response = await self.parse_response(stdout_str, stderr_str)
            logger.info(f"[{self.name}] Response received (length: {len(response)} chars)")

            return response

        except CLIAgentError:
            # Re-raise our custom errors
            raise
        except Exception as e:
            logger.error(f"[{self.name}] Unexpected error: {e}", exc_info=True)
            raise CLIAgentError(f"Agent {self.name} encountered an error: {str(e)}")
        finally:
            self.process = None

    async def get_status(self) -> dict:
        """Get the current status of the agent"""
        return {
            "name": self.name,
            "type": self.agent_type,
            "status": self.status,
            "role": self.role,
            "workspace_path": self.workspace_path,
            "is_running": self.process is not None and self.process.returncode is None
        }

    async def stop(self) -> None:
        """Stop the agent (kill any running process)"""
        logger.info(f"Stopping CLI agent: {self.name}")

        if self.process and self.process.returncode is None:
            logger.warning(f"[{self.name}] Killing running process")
            self.process.kill()
            await self.process.wait()

        self.status = "stopped"
        self.process = None


class JSONCLIAgent(CLIAgent):
    """
    Base class for CLI agents that return JSON output.
    Provides common JSON parsing logic.
    """

    def _extract_json_from_output(self, output: str) -> str:
        """
        Extract JSON from CLI output that may contain extra text.

        Handles cases where:
        - Output contains ANSI escape codes
        - JSON is surrounded by progress indicators or warnings
        - Multiple JSON objects are present (takes the last one)
        - Braces inside JSON string values (doesn't count them)
        - Stream JSON (NDJSON) format with multiple objects per line

        Args:
            output: Raw stdout from CLI

        Returns:
            Cleaned JSON string
        """
        # Remove ANSI escape codes (color codes, cursor movement, etc.)
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        cleaned = ansi_escape.sub('', output)

        # Handle stream-json format (newline-delimited JSON)
        # If output contains multiple lines with JSON objects, try to combine them
        lines = cleaned.strip().split('\n')

        logger.debug(f"[_extract_json_from_output] Total lines in output: {len(lines)}")

        if len(lines) > 1:
            # Try to find complete JSON objects in each line
            # For stream-json with --verbose, look specifically for type: "result"
            result_json = None
            valid_json_lines = []

            for idx, line in enumerate(lines):
                line = line.strip()
                if line.startswith('{') and line.endswith('}'):
                    try:
                        obj = json.loads(line)
                        valid_json_lines.append(line)

                        obj_type = obj.get('type', 'no-type')
                        logger.debug(f"[_extract_json_from_output] Line {idx}: type={obj_type}, length={len(line)}")

                        # Look for the result message (not system/thinking messages)
                        if isinstance(obj, dict) and obj.get('type') == 'result':
                            result_json = line
                            logger.info(f"[_extract_json_from_output] ✓ Found result-type message on line {idx}")
                    except Exception as e:
                        logger.debug(f"[_extract_json_from_output] Line {idx} failed to parse: {e}")
                        continue

            # Prefer the result message if found, otherwise take the last valid JSON
            if result_json:
                logger.info(f"[_extract_json_from_output] Using result-type message")
                cleaned = result_json
            elif valid_json_lines:
                logger.error(f"[_extract_json_from_output] CRITICAL: No result-type message found in stream-json output!")
                logger.error(f"[_extract_json_from_output] Found {len(valid_json_lines)} JSON objects but none had type='result'")
                logger.error(f"[_extract_json_from_output] This likely means Claude CLI failed or was interrupted before completing")

                # Log types of all messages found
                for idx, line in enumerate(valid_json_lines):
                    try:
                        obj = json.loads(line)
                        msg_type = obj.get('type', 'unknown')
                        msg_subtype = obj.get('subtype', '')
                        logger.error(f"[_extract_json_from_output] Message {idx}: type={msg_type}, subtype={msg_subtype}")
                    except:
                        pass

                logger.warning(f"[_extract_json_from_output] Falling back to last JSON object (may be incorrect!)")
                logger.warning(f"[_extract_json_from_output] Last object preview: {valid_json_lines[-1][:200]}...")
                cleaned = valid_json_lines[-1]
            else:
                logger.error(f"[_extract_json_from_output] No valid JSON lines found!")
        else:
            logger.debug(f"[_extract_json_from_output] Single line output, skipping multi-line handling")

        # Try to find JSON objects in the output
        # This is a state machine that tracks:
        # - Whether we're inside a string literal
        # - The brace depth (only counting structural braces, not those in strings)
        brace_count = 0
        json_start = -1
        json_candidates = []
        in_string = False
        escape_next = False

        for i, char in enumerate(cleaned):
            # Handle escape sequences in strings
            if escape_next:
                escape_next = False
                continue

            if char == '\\' and in_string:
                escape_next = True
                continue

            # Handle string boundaries (only if not escaped)
            if char == '"':
                in_string = not in_string
                continue

            # Only count braces when NOT inside a string
            if not in_string:
                if char == '{':
                    if brace_count == 0:
                        json_start = i
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0 and json_start != -1:
                        json_candidates.append(cleaned[json_start:i+1])
                        json_start = -1

        # If we found JSON candidates, return the last one (most likely the actual response)
        if json_candidates:
            return json_candidates[-1]

        # Fallback: return cleaned output
        return cleaned.strip()

    async def parse_response(self, stdout: str, stderr: str) -> str:
        """
        Parse JSON response from CLI.

        Expects JSON output with a specific structure that subclasses can define.
        Default implementation looks for a 'content' field.
        """
        if not stdout.strip():
            raise CLIAgentError(f"Agent {self.name} returned empty output")

        # Log raw output length for diagnostics
        logger.debug(f"[{self.name}] Raw stdout length: {len(stdout)} chars")

        # Extract JSON from potentially noisy output
        json_str = self._extract_json_from_output(stdout)

        logger.debug(f"[{self.name}] Extracted JSON length: {len(json_str)} chars")

        try:
            data = json.loads(json_str)
            return self.extract_content_from_json(data)
        except json.JSONDecodeError as e:
            logger.error(f"[{self.name}] Failed to parse JSON: {e}")
            logger.error(f"[{self.name}] Raw stdout length: {len(stdout)} chars, Extracted JSON length: {len(json_str)} chars")

            # Log extracted JSON (limit to 2000 chars to avoid log spam)
            if len(json_str) <= 2000:
                logger.error(f"[{self.name}] Extracted JSON string:\n{json_str}")
            else:
                logger.error(f"[{self.name}] Extracted JSON string (first 1000 chars):\n{json_str[:1000]}")
                logger.error(f"[{self.name}] ... (truncated, total length: {len(json_str)} chars)")
                logger.error(f"[{self.name}] Last 500 chars:\n{json_str[-500:]}")

                # Try to show where the JSON becomes invalid
                # Attempt to parse progressively smaller chunks to find the break point
                for test_len in [5000, 2000, 1000, 500]:
                    if test_len < len(json_str):
                        test_str = json_str[:test_len] + '"}}'  # Try to close it artificially
                        try:
                            json.loads(test_str)
                            logger.error(f"[{self.name}] JSON is valid up to ~{test_len} chars (with artificial closing)")
                            break
                        except:
                            continue

            # Attempt fallback: try to extract result/content field using regex
            logger.warning(f"[{self.name}] Attempting fallback extraction using regex...")
            result = self._fallback_extract_content(json_str)
            if result:
                logger.warning(f"[{self.name}] Fallback extraction succeeded! Extracted {len(result)} chars")
                return result

            logger.debug(f"[{self.name}] Full raw stdout:\n{stdout}")
            raise CLIAgentError(f"Agent {self.name} returned invalid JSON: {str(e)}")

    def _fallback_extract_content(self, malformed_json: str) -> Optional[str]:
        """
        Attempt to extract content from malformed JSON using regex.

        This is a fallback when json.loads() fails. It tries to extract
        the value of common field names like 'result', 'content', 'message'.

        Args:
            malformed_json: The malformed JSON string

        Returns:
            Extracted content if found, None otherwise
        """
        # Try to extract common field names in order of priority
        # Pattern matches: "field": "value (where value can have escaped quotes and continues to end of string if unclosed)
        field_names = ['result', 'content', 'message']

        for field_name in field_names:
            # Match the field name and opening quote, then capture everything until:
            # - An unescaped quote followed by comma/brace/end, OR
            # - End of string (for truncated JSON)
            pattern = rf'"{field_name}"\s*:\s*"((?:[^"\\]|\\.)*?)(?:(?<!\\)"[\s,\}}]|$)'

            match = re.search(pattern, malformed_json, re.DOTALL)
            if match:
                content = match.group(1)
                # Unescape common JSON escape sequences
                content = content.replace('\\n', '\n')
                content = content.replace('\\t', '\t')
                content = content.replace('\\r', '\r')
                content = content.replace('\\"', '"')
                content = content.replace('\\\\', '\\')
                return content

        return None

    def extract_content_from_json(self, data: dict) -> str:
        """
        Extract the content from the JSON response.
        Override this in subclasses for agent-specific JSON structures.

        Args:
            data: Parsed JSON data

        Returns:
            Extracted content string
        """
        # Default: look for 'content' field
        if isinstance(data, dict) and 'content' in data:
            return data['content']

        # If data is already a string, return it
        if isinstance(data, str):
            return data

        # Otherwise, return the JSON as a formatted string
        return json.dumps(data, indent=2)
