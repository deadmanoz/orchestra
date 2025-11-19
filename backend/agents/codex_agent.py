"""Codex CLI agent implementation"""

import json
import logging
from typing import List
from pathlib import Path

from backend.agents.cli_agent import JSONCLIAgent
from backend.config import settings

logger = logging.getLogger(__name__)


class CodexAgent(JSONCLIAgent):
    """
    Agent implementation for Codex CLI.

    Uses Codex CLI with --json and --output-schema flags for structured output.
    Command format: codex --json --quiet --output-schema <schema> -p "<prompt>"

    Particularly powerful for code reviews due to structured schema support.
    """

    def __init__(
        self,
        name: str,
        role: str = "review",
        workspace_path: str = None,
        timeout: int = None,
        use_review_schema: bool = True
    ):
        super().__init__(
            name=name,
            agent_type="codex",
            role=role,
            workspace_path=workspace_path,
            timeout=timeout or settings.agent_timeout
        )
        self.cli_path = settings.codex_cli_path
        self.use_review_schema = use_review_schema

        # Path to review schema for structured output
        self.review_schema_path = Path(__file__).parent.parent / "schemas" / "review_schema.json"

        # Validate schema exists
        if self.use_review_schema and not self.review_schema_path.exists():
            logger.warning(f"[{self.name}] Review schema not found at {self.review_schema_path}")
            self.use_review_schema = False

    def get_cli_command(self, message: str) -> List[str]:
        """
        Build the Codex CLI command.

        Args:
            message: The prompt/message to send to Codex

        Returns:
            Command list with appropriate flags
        """
        command = [
            self.cli_path,
            "--json",      # JSON output for parsing
            "--quiet",     # Suppress interactive UI elements
        ]

        # Add output schema for structured reviews
        if self.use_review_schema and self.role == "review":
            command.extend([
                "--output-schema",
                str(self.review_schema_path)
            ])

        # Add the prompt
        command.extend(["-p", message])

        return command

    def extract_content_from_json(self, data: dict) -> str:
        """
        Extract content from Codex's JSON response.

        When using --output-schema, Codex returns data conforming to our schema.
        For non-schema mode, handle standard Codex JSON patterns.

        Args:
            data: Parsed JSON response from Codex

        Returns:
            The extracted message content or formatted structured data
        """
        # If using review schema, data should already match our schema
        if self.use_review_schema and self.role == "review":
            return self._format_structured_review(data)

        # Handle standard Codex JSON response patterns
        if isinstance(data, dict):
            # Pattern 1: Direct 'content' field
            if 'content' in data:
                return data['content']

            # Pattern 2: 'result' field
            if 'result' in data:
                return data['result']

            # Pattern 3: 'message' field
            if 'message' in data:
                return data['message']

            # Pattern 4: 'output' field
            if 'output' in data:
                return data['output']

            # Pattern 5: Nested in 'response'
            if 'response' in data and isinstance(data['response'], dict):
                if 'content' in data['response']:
                    return data['response']['content']

        # Fallback to parent class behavior
        logger.warning(f"[{self.name}] Unexpected JSON structure, using fallback")
        return super().extract_content_from_json(data)

    def _format_structured_review(self, review_data: dict) -> str:
        """
        Format structured review data into readable markdown.

        Takes the JSON schema-compliant review and converts it to a
        human-readable format for display and processing.

        Args:
            review_data: Review data matching review_schema.json

        Returns:
            Formatted markdown review
        """
        try:
            output = []

            # Header
            reviewer = review_data.get('reviewer', self.name)
            output.append(f"# Code Review by {reviewer}\n")

            # Overall Assessment
            assessment = review_data.get('overall_assessment', {})
            verdict = assessment.get('verdict', 'unknown')
            summary = assessment.get('summary', 'No summary provided')
            confidence = assessment.get('confidence_score')

            output.append(f"## Overall Assessment\n")
            output.append(f"**Verdict:** {verdict.replace('_', ' ').title()}")
            if confidence is not None:
                output.append(f" (Confidence: {confidence:.1%})")
            output.append(f"\n\n{summary}\n")

            # Metrics (if present)
            metrics = review_data.get('metrics')
            if metrics:
                output.append(f"\n## Metrics\n")
                if 'code_quality_score' in metrics:
                    output.append(f"- **Code Quality:** {metrics['code_quality_score']}/10\n")
                if 'security_score' in metrics:
                    output.append(f"- **Security:** {metrics['security_score']}/10\n")
                if 'maintainability_score' in metrics:
                    output.append(f"- **Maintainability:** {metrics['maintainability_score']}/10\n")
                if 'test_coverage_assessment' in metrics:
                    output.append(f"- **Testing:** {metrics['test_coverage_assessment'].replace('_', ' ').title()}\n")

            # Positive Aspects
            positives = review_data.get('positive_aspects', [])
            if positives:
                output.append(f"\n## Strengths ✅\n")
                for positive in positives:
                    output.append(f"- {positive}\n")

            # Issues
            issues = review_data.get('issues', [])
            if issues:
                output.append(f"\n## Issues & Concerns 🔍\n")

                # Group by severity
                critical = [i for i in issues if i.get('severity') == 'critical']
                high = [i for i in issues if i.get('severity') == 'high']
                medium = [i for i in issues if i.get('severity') == 'medium']
                low = [i for i in issues if i.get('severity') == 'low']

                for severity, items in [('Critical', critical), ('High', high), ('Medium', medium), ('Low', low)]:
                    if items:
                        output.append(f"\n### {severity} Priority\n")
                        for issue in items:
                            output.append(f"\n**{issue.get('title', 'Issue')}** "
                                        f"[{issue.get('category', 'general').upper()}]\n")
                            output.append(f"{issue.get('description', '')}\n")

                            if 'location' in issue:
                                output.append(f"\n*Location:* {issue['location']}\n")

                            if 'suggested_fix' in issue:
                                output.append(f"\n*Suggested Fix:* {issue['suggested_fix']}\n")

                            if 'references' in issue and issue['references']:
                                output.append(f"\n*References:* {', '.join(issue['references'])}\n")

            # Recommendations
            recommendations = review_data.get('recommendations', [])
            if recommendations:
                output.append(f"\n## Recommendations 💡\n")

                # Group by priority
                must_have = [r for r in recommendations if r.get('priority') == 'must_have']
                should_have = [r for r in recommendations if r.get('priority') == 'should_have']
                nice_to_have = [r for r in recommendations if r.get('priority') == 'nice_to_have']

                for priority, items in [('Must Have', must_have), ('Should Have', should_have),
                                       ('Nice to Have', nice_to_have)]:
                    if items:
                        output.append(f"\n### {priority}\n")
                        for rec in items:
                            output.append(f"\n**{rec.get('title', 'Recommendation')}**\n")
                            output.append(f"{rec.get('description', '')}\n")
                            if 'impact' in rec:
                                output.append(f"\n*Impact:* {rec['impact']}\n")

            # Questions
            questions = review_data.get('questions', [])
            if questions:
                output.append(f"\n## Questions for Clarification ❓\n")
                for i, q in enumerate(questions, 1):
                    output.append(f"\n{i}. {q.get('question', '')}\n")
                    if 'context' in q:
                        output.append(f"   *Context:* {q['context']}\n")

            # Also store the raw JSON for programmatic access
            output.append(f"\n---\n")
            output.append(f"\n<details><summary>Raw Structured Data (JSON)</summary>\n\n```json\n")
            output.append(json.dumps(review_data, indent=2))
            output.append(f"\n```\n</details>\n")

            return ''.join(output)

        except Exception as e:
            logger.error(f"[{self.name}] Error formatting structured review: {e}", exc_info=True)
            # Fallback to raw JSON
            return f"# Review Data\n\n```json\n{json.dumps(review_data, indent=2)}\n```"
