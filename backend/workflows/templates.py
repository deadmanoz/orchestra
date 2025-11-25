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

IMPORTANT:
- Present your plan in markdown format directly in your response
- Do NOT attempt to save files or use /save-plan command
- Your output will be automatically saved to the workspace
- Focus on creating the best possible plan
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
                    # Generic role for review agents
                    role = "REVIEW AGENT"
                content = msg.content
            else:
                continue

            history_lines.append(f"\n--- {role} ---\n{content}\n")

        history_text = "".join(history_lines)

        # Add current review feedback if present
        feedback_section = ""
        if review_feedback:
            feedback_text = "\n\n".join([
                f"**** {review.get('agent_identifier', 'REVIEW AGENT')} FEEDBACK START ****\n{review['feedback']}\n**** {review.get('agent_identifier', 'REVIEW AGENT')} FEEDBACK END ****"
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
- Present your plan in markdown format directly in your response
- Do NOT attempt to save files or use /save-plan command
- Your output will be automatically saved to the workspace

Provide your revised plan now.
"""

    @staticmethod
    def planning_revision(current_plan: str, review_feedback: list[dict]) -> str:
        feedback_text = "\n\n".join([
            f"**** {review.get('agent_identifier', 'REVIEW AGENT')} FEEDBACK START ****\n{review['feedback']}\n**** {review.get('agent_identifier', 'REVIEW AGENT')} FEEDBACK END ****"
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
    def review_request(plan: str, agent_index: int) -> str:
        return f"""You are REVIEW AGENT {agent_index} helping review a development plan.

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

    @staticmethod
    def review_with_history(messages: list[BaseMessage], plan: str, agent_index: int) -> str:
        """
        Build review prompt with full conversation history for context.

        This allows review agents to reference their previous reviews and see
        how the plan evolved based on their feedback.
        """
        # Build conversation history section
        history_lines = [f"You are REVIEW AGENT {agent_index}. Here is the conversation history:\n"]

        # Track which review agent index corresponds to which message index
        review_agent_counter = 0
        for msg in messages:
            if isinstance(msg, HumanMessage):
                # User messages (requirements, feedback)
                role = "USER"
                content = msg.content
            elif isinstance(msg, AIMessage):
                # Previous plans and reviews
                if msg.name == "planning_agent":
                    role = "PLANNING AGENT"
                    content = msg.content
                elif msg.name and msg.name.startswith("review_agent"):
                    # Assign generic review agent number based on order
                    review_agent_counter += 1
                    # Check if this could be our previous review (matching index)
                    role = f"YOU (previous review)" if review_agent_counter % 3 == (agent_index - 1) else f"OTHER REVIEWER"
                    content = msg.content
                else:
                    role = "AGENT"
                    content = msg.content
            else:
                continue

            history_lines.append(f"\n--- {role} ---\n{content}\n")

        history_text = "".join(history_lines)

        return f"""{history_text}

The PLANNING AGENT has now revised the plan. Here is the CURRENT VERSION to review:

**** CURRENT PLAN (v{len([m for m in messages if isinstance(m, AIMessage) and m.name == 'planning_agent']) + 1}) START ****
{plan}
**** CURRENT PLAN END ****

Based on the conversation history above, please provide your expert review feedback.

IMPORTANT:
- Reference your previous reviews if you gave feedback before
- Note if your previous concerns were addressed or ignored
- Acknowledge improvements made since your last review
- Identify new issues introduced in this version
- Be specific about what changed and whether it's better or worse

Focus on:
- Technical feasibility
- Architecture concerns
- Missing considerations
- Timeline realism
- Security and scalability

Provide direct, unambiguous feedback that will help improve the plan.
"""
