"""
Review Analysis Service

Analyzes review agent outputs to determine approval status.
"""

import re
from typing import Literal


def analyze_review_approval(review_content: str) -> Literal["approved", "has_feedback", "unclear"]:
    """
    Analyze review content to determine if it's an approval or has concerns.

    Uses keyword-based heuristics to classify reviews:
    - "approved": Review explicitly approves or has only minor/optional suggestions
    - "has_feedback": Review has concerns, issues, or required changes
    - "unclear": Cannot determine (fallback)

    Args:
        review_content: The review text from review agent

    Returns:
        Classification: "approved", "has_feedback", or "unclear"
    """
    content_lower = review_content.lower()

    # Strong approval signals
    approval_patterns = [
        r'\bapproved?\b',
        r'\blooks?\s+good\b',
        r'\bready\s+to\s+(proceed|implement|continue)\b',
        r'\bno\s+(concerns?|issues?|problems?)\b',
        r'\bexcellent\s+plan\b',
        r'\bwell[-\s]structured\b',
        r'\bcomprehensive\s+plan\b',
        r'\bno\s+major\s+(concerns?|issues?)\b',
        r'\ball\s+good\b',
        r'\bproceed\s+with\s+implementation\b',
    ]

    # Strong concern/feedback signals
    concern_patterns = [
        r'\b(critical|major|serious)\s+(issue|concern|problem)\b',
        r'\bmust\s+(address|fix|change|add|update)\b',
        r'\brequired?\s+(change|update|fix)\b',
        r'\bmissing\s+(critical|important|essential)\b',
        r'\bshould\s+(add|include|consider|address)\b.*\bbefore\s+implementation\b',
        r'\bsignificant\s+(concern|issue|problem)\b',
        r'\bnot\s+ready\b',
        r'\bneeds?\s+(revision|more\s+work|improvement)\b',
        r'\breject\b',
    ]

    # Count matches
    approval_score = sum(1 for pattern in approval_patterns if re.search(pattern, content_lower))
    concern_score = sum(1 for pattern in concern_patterns if re.search(pattern, content_lower))

    # Decision logic
    if approval_score > 0 and concern_score == 0:
        return "approved"

    if concern_score > 0:
        # Has concerns, even if also has some positive statements
        return "has_feedback"

    # Check for "should" statements (suggestions that may or may not be blockers)
    should_count = len(re.findall(r'\bshould\b', content_lower))

    # If has many "should" statements, classify as has_feedback
    if should_count >= 3:
        return "has_feedback"

    # If has some approval signals but also minor suggestions
    if approval_score > 0:
        return "approved"

    # Default: unclear (probably has some feedback if it's a real review)
    # Most reviews will have at least some suggestions
    return "has_feedback" if len(content_lower) > 200 else "unclear"


def get_approval_summary(reviews: list[dict]) -> dict:
    """
    Get approval summary across all reviews.

    Args:
        reviews: List of review dicts with 'feedback' and 'agent_identifier' keys

    Returns:
        Dict with:
        - approved_count: Number of approvals
        - feedback_count: Number with feedback/concerns
        - unclear_count: Number unclear
        - all_approved: Boolean, True if all reviews approved
        - reviews_by_status: Dict mapping status to list of agent identifiers
    """
    approved = []
    has_feedback = []
    unclear = []

    for review in reviews:
        feedback = review.get('feedback', '')
        agent_id = review.get('agent_identifier', review.get('agent_name', 'Unknown'))

        status = analyze_review_approval(feedback)

        if status == "approved":
            approved.append(agent_id)
        elif status == "has_feedback":
            has_feedback.append(agent_id)
        else:
            unclear.append(agent_id)

    return {
        "approved_count": len(approved),
        "feedback_count": len(has_feedback),
        "unclear_count": len(unclear),
        "all_approved": len(approved) == len(reviews) and len(reviews) > 0,
        "reviews_by_status": {
            "approved": approved,
            "has_feedback": has_feedback,
            "unclear": unclear
        }
    }
