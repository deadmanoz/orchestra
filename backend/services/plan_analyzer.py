"""
Plan Analysis Service

Uses an LLM to analyze plan content and extract semantic information
like feature names and subdirectory names.
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


def extract_semantic_name_from_plan(plan_content: str) -> str:
    """
    Extract a semantic, kebab-case directory name from plan content.

    Uses heuristics to identify the feature/task being planned:
    1. Look for markdown H1 headers (# Title)
    2. Look for common patterns like "Implementation Plan", "Plan for X"
    3. Extract key domain terms
    4. Convert to kebab-case

    Args:
        plan_content: The full plan markdown content

    Returns:
        Kebab-case directory name (e.g., "hecs-debt", "currency-conversion")
    """
    # Extract first H1 header
    h1_match = re.search(r'^#\s+(.+?)(?:\s*-\s*Plan)?$', plan_content, re.MULTILINE)
    if h1_match:
        title = h1_match.group(1).strip()
        # Remove common suffixes
        title = re.sub(r'\s*-?\s*(Implementation\s+)?Plan\s*(V\d+)?', '', title, flags=re.IGNORECASE)
        return _to_kebab_case(title)

    # Look for "Plan for X" or "X Implementation" patterns
    plan_for_match = re.search(r'(?:Plan for|Implementation of)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', plan_content)
    if plan_for_match:
        return _to_kebab_case(plan_for_match.group(1))

    # Extract from first line if it looks like a title
    first_line = plan_content.split('\n')[0].strip('#').strip()
    if first_line and len(first_line) < 100:
        return _to_kebab_case(first_line)

    # Fallback: generic name
    logger.warning("Could not extract semantic name from plan, using 'general-plan'")
    return "general-plan"


def _to_kebab_case(text: str) -> str:
    """
    Convert text to kebab-case.

    Examples:
        "HECS-HELP Debt" -> "hecs-help-debt"
        "Currency Conversion System" -> "currency-conversion-system"
        "API Authentication" -> "api-authentication"
    """
    # Remove special characters except spaces and hyphens
    text = re.sub(r'[^\w\s-]', '', text)
    # Replace spaces with hyphens
    text = re.sub(r'[\s_]+', '-', text)
    # Convert to lowercase
    text = text.lower()
    # Remove duplicate hyphens
    text = re.sub(r'-+', '-', text)
    # Trim hyphens from ends
    text = text.strip('-')
    # Limit length (max 50 chars)
    if len(text) > 50:
        # Try to cut at word boundary
        text = text[:50]
        last_hyphen = text.rfind('-')
        if last_hyphen > 20:  # Keep at least 20 chars
            text = text[:last_hyphen]
    return text or "plan"


def get_next_version_number(directory_path) -> int:
    """
    Determine the next version number by examining existing plan files.

    Args:
        directory_path: Path object to the plan directory

    Returns:
        Next version number (1 if no plans exist)
    """
    from pathlib import Path

    if not directory_path.exists():
        return 1

    # Find all plan files matching plan-v{N}.md pattern
    version_pattern = re.compile(r'plan-v(\d+)\.md$')
    versions = []

    for file in directory_path.glob('plan-v*.md'):
        match = version_pattern.match(file.name)
        if match:
            versions.append(int(match.group(1)))

    return max(versions) + 1 if versions else 1
