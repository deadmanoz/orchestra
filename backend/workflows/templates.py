from typing import Optional

class PromptTemplates:
    """Templates for agent prompts"""

    @staticmethod
    def planning_initial(requirements: str) -> str:
        return f"""You are a PLANNING AGENT helping develop a comprehensive plan.

The user has the following requirements:

{requirements}

Please create a detailed development plan that addresses these requirements.

IMPORTANT: Respond directly with your plan. Do NOT use any tools or try to read files.
Base your plan on the requirements provided above.

Include:
- Architecture overview
- Implementation steps
- Timeline estimates
- Potential challenges

Your plan will be reviewed by multiple REVIEW AGENTS before implementation.

Provide your complete plan in your response."""

    @staticmethod
    def planning_revision(current_plan: str, review_feedback: list[dict]) -> str:
        feedback_text = "\n\n".join([
            f"**** {review['agent_name']} FEEDBACK START ****\n{review['feedback']}\n**** {review['agent_name']} FEEDBACK END ****"
            for review in review_feedback
        ])

        return f"""The REVIEW AGENT(s) have provided feedback on your plan.

**** CURRENT PLAN START ****
{current_plan}
**** CURRENT PLAN END ****

{feedback_text}

Please revise your plan based on the feedback above.
Address the concerns raised and incorporate the suggestions.
"""

    @staticmethod
    def review_request(plan: str, agent_name: str) -> str:
        return f"""You are a REVIEW AGENT ({agent_name}) helping review a development plan.

The PLANNING AGENT has prepared the following plan:

**** PLAN START ****
{plan}
**** PLAN END ****

Please provide expert review feedback on the plan.
Focus on:
- Technical feasibility
- Architecture concerns
- Missing considerations
- Timeline realism
- Security and scalability

Provide direct, unambiguous feedback that will help improve the plan.
"""
