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
        timeout: int = 300
    ):
        super().__init__(name, agent_type)
        self.role = role
        self.workspace_path = workspace_path or "."
        self.timeout = timeout
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
        logger.debug(f"[{self.name}] Command: {' '.join(command[:3])}...")  # Log command (truncated)

        try:
            # Execute the CLI command
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.workspace_path
            )

            self.process = process

            # Wait for completion with timeout
            try:
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

            # Log stderr if present (might contain warnings/info)
            if stderr_str.strip():
                logger.debug(f"[{self.name}] stderr: {stderr_str}")

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

        Args:
            output: Raw stdout from CLI

        Returns:
            Cleaned JSON string
        """
        # Remove ANSI escape codes (color codes, cursor movement, etc.)
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        cleaned = ansi_escape.sub('', output)

        # Try to find JSON objects in the output
        # Look for content between { and } (handles nested braces)
        brace_count = 0
        json_start = -1
        json_candidates = []

        for i, char in enumerate(cleaned):
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

        # Extract JSON from potentially noisy output
        json_str = self._extract_json_from_output(stdout)

        try:
            data = json.loads(json_str)
            return self.extract_content_from_json(data)
        except json.JSONDecodeError as e:
            logger.error(f"[{self.name}] Failed to parse JSON: {e}")
            # Log extracted JSON (limit to 2000 chars to avoid log spam)
            if len(json_str) <= 2000:
                logger.error(f"[{self.name}] Extracted JSON string:\n{json_str}")
            else:
                logger.error(f"[{self.name}] Extracted JSON string (first 1000 chars):\n{json_str[:1000]}")
                logger.error(f"[{self.name}] ... (truncated, total length: {len(json_str)} chars)")
                logger.error(f"[{self.name}] Last 500 chars:\n{json_str[-500:]}")
            logger.debug(f"[{self.name}] Full raw stdout:\n{stdout}")
            raise CLIAgentError(f"Agent {self.name} returned invalid JSON: {str(e)}")

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
