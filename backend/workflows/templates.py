from typing import Optional
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

class PromptTemplates:
    """Templates for agent prompts"""

    @staticmethod
    def planning_initial(requirements: str) -> str:
        return f"""You are a PLANNING AGENT helping develop a comprehensive plan.

The user has the following requirements:

{requirements}

Please create a detailed development plan that addresses these requirements.
Include:
- Architecture overview
- Implementation steps
- Timeline estimates
- Potential challenges

Your plan will be reviewed by multiple REVIEW AGENTS before implementation.
"""

    @staticmethod
    def planning_with_history(messages: list[BaseMessage], review_feedback: list[dict] = None) -> str:
        """
        Build planning prompt with full conversation history for context.

        This allows the agent to understand previous iterations and why changes were requested.
        """
        # Build conversation history section
        history_lines = ["Here is the conversation history so far:\n"]

        for msg in messages:
            if isinstance(msg, HumanMessage):
                # User messages (requirements, feedback, rejections)
                role = "USER"
                content = msg.content
            elif isinstance(msg, AIMessage):
                # Previous plans from planning agent or reviews
                if msg.name == "planning_agent":
                    role = "YOU (previous iteration)"
                else:
                    role = f"REVIEW AGENT ({msg.name})"
                content = msg.content[:500] + "..." if len(msg.content) > 500 else msg.content
            else:
                continue

            history_lines.append(f"\n--- {role} ---\n{content}\n")

        history_text = "".join(history_lines)

        # Add current review feedback if present
        feedback_section = ""
        if review_feedback:
            feedback_text = "\n\n".join([
                f"**** {review['agent_name']} FEEDBACK START ****\n{review['feedback']}\n**** {review['agent_name']} FEEDBACK END ****"
                for review in review_feedback
            ])
            feedback_section = f"\n\nThe REVIEW AGENTS have provided new feedback:\n\n{feedback_text}\n\n"

        return f"""{history_text}
{feedback_section}
Based on the conversation history above, please revise your plan.

IMPORTANT:
- Reference what was tried before and why it didn't work
- Address all feedback from review agents
- Build on previous iterations rather than starting from scratch
- Remember user preferences expressed in earlier messages

Provide your revised plan now.
"""

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
