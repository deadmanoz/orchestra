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

CRITICAL RESTRICTIONS:
- You are in READ-ONLY mode for all code and configuration files
- Do NOT modify, create, edit, or delete ANY files except the plan document
- Do NOT run any commands that modify the filesystem or codebase
- Do NOT execute code, run tests, install packages, or make commits
- ONLY output your plan as markdown text in your response
- Your plan output will be automatically saved by the system

WHAT YOU CAN DO:
- Read and analyze existing code to inform your plan
- Present your plan in markdown format in your response
- Reference files and code you've read

Focus on creating the best possible plan.
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

CRITICAL RESTRICTIONS:
- You are in READ-ONLY mode for all code and configuration files
- Do NOT modify, create, edit, or delete ANY files except the plan document
- Do NOT run any commands that modify the filesystem or codebase
- Do NOT execute code, run tests, install packages, or make commits
- ONLY output your plan as markdown text in your response
- Your plan output will be automatically saved by the system

WHAT YOU CAN DO:
- Read and analyze existing code to inform your plan
- Present your plan in markdown format in your response
- Reference files and code you've read

REVISION GUIDANCE:
- Reference what was tried before and why it didn't work
- Address all feedback from review agents
- Build on previous iterations rather than starting from scratch
- Remember user preferences expressed in earlier messages

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

CRITICAL RESTRICTIONS:
- You are in READ-ONLY mode for all code and configuration files
- Do NOT modify, create, edit, or delete ANY files
- Do NOT run any commands that modify the filesystem or codebase
- Do NOT execute code, run tests, install packages, or make commits
- ONLY output your revised plan as markdown text in your response

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

CRITICAL RESTRICTIONS - READ THIS CAREFULLY:
- You are in STRICT READ-ONLY mode
- Do NOT modify, create, edit, or delete ANY files whatsoever
- Do NOT run ANY commands that modify the filesystem or codebase
- Do NOT execute code, run tests, install packages, or make commits
- Do NOT write code implementations or create new files
- ONLY provide your review feedback as text in your response

WHAT YOU CAN DO:
- Read existing code to inform your review
- Provide written feedback and suggestions
- Analyze the plan and identify issues

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

CRITICAL RESTRICTIONS - READ THIS CAREFULLY:
- You are in STRICT READ-ONLY mode
- Do NOT modify, create, edit, or delete ANY files whatsoever
- Do NOT run ANY commands that modify the filesystem or codebase
- Do NOT execute code, run tests, install packages, or make commits
- Do NOT write code implementations or create new files
- ONLY provide your review feedback as text in your response

WHAT YOU CAN DO:
- Read existing code to inform your review
- Provide written feedback and suggestions
- Analyze the plan and identify issues

Based on the conversation history above, please provide your expert review feedback.

REVIEW GUIDANCE:
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

    @staticmethod
    def review_summary(review_feedback: list[dict]) -> str:
        """
        Build prompt for the review summary agent to consolidate all reviewer feedback.
        """
        feedback_sections = []
        reviewer_list = []
        for idx, review in enumerate(review_feedback, 1):
            agent_id = review.get('agent_identifier', f'REVIEW AGENT {idx}')
            reviewer_list.append(agent_id)
            feedback_sections.append(
                f"=== {agent_id} ===\n{review['feedback']}\n"
            )

        all_feedback = "\n".join(feedback_sections)
        reviewer_names = ", ".join(reviewer_list)

        return f"""You are a REVIEW SUMMARY AGENT. Your task is to:
1. Evaluate each reviewer's verdict on the plan
2. Provide a brief, actionable summary of the feedback

CRITICAL RESTRICTIONS - READ THIS CAREFULLY:
- You are in STRICT READ-ONLY mode
- Do NOT modify, create, edit, or delete ANY files whatsoever
- Do NOT run ANY commands that modify the filesystem or codebase
- Do NOT execute code, run tests, install packages, or make commits
- Do NOT write code implementations or create new files
- ONLY provide your summary as text in your response

The following review agents have analyzed a development plan:

{all_feedback}

## PART 1: REVIEWER VERDICTS

For each reviewer ({reviewer_names}), determine their verdict. Output EXACTLY in this format:

```verdicts
REVIEW AGENT 1: APPROVED | APPROVED_WITH_SUGGESTIONS | NEEDS_REVISION
REVIEW AGENT 2: APPROVED | APPROVED_WITH_SUGGESTIONS | NEEDS_REVISION
REVIEW AGENT 3: APPROVED | APPROVED_WITH_SUGGESTIONS | NEEDS_REVISION
```

Verdict definitions:
- APPROVED: No blocking concerns, ready to proceed
- APPROVED_WITH_SUGGESTIONS: Minor/optional improvements suggested, but can proceed
- NEEDS_REVISION: Has blocking concerns or required changes before implementation

## PART 2: EXECUTIVE SUMMARY

Provide a CONCISE summary (5-10 bullet points) covering:

1. **Key Issues**: Critical concerns raised (prioritize issues from multiple reviewers)
2. **Common Themes**: Patterns across reviews
3. **Quick Wins**: Easy-to-address suggestions
4. **Blockers**: Showstopper issues that must be resolved (if any)

Keep each bullet point to 1-2 sentences maximum.
"""
