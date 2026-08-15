from google.adk.agents.llm_agent import Agent
from google.adk.models.lite_llm import LiteLlm
from pydantic import BaseModel
from google.adk.agents import SequentialAgent
from tools.tools import get_current_datetime
from tools.tools import create_task
from tools.tools import save_task



understand_mails = Agent(
    model=LiteLlm("groq/llama-3.3-70b-versatile"),
    name="understand_mails",
    description="Analyzes emails and extracts their summary, tasks, and deadlines.",
    instruction="""
    You are an email analysis agent for InboxAI.

    Analyze the email provided by the user.

    Extract:
    - summary: a short and clear summary
    - task: the action the user needs to complete
    - deadline: the deadline mentioned in the email
    and return them in a structured format.

    If there is no task, use "No task".
    If there is no deadline, use "No deadline".
    and then call the save_task tool with the summary, task, and deadline.
    Do not invent information.
    """,
    output_key="mail_analysis",
    tools=[save_task]
)


priority_agent = Agent(
    model=LiteLlm("groq/llama-3.3-70b-versatile"),
    name="priority_agent",
    description="Determines task priority based on the deadline.",
    instruction="""
    You are a priority analysis agent for InboxAI.

    Analyze the task and deadline from the email analysis:
    {mail_analysis}

    First, use the get_current_datetime tool to get the current date and time.

    Calculate exactly how many days remain until the deadline.

    Priority rules:

    - High: deadline is today or within the next 2 days.
    - Medium: deadline is 3 to 7 days away.
    - Low: deadline is more than 7 days away.
    - If there is no deadline, use Medium.
    - After determining the priority, ALWAYS call the create_task tool
        with the task, deadline, and priority.
    Return:
    - task
    - deadline
    - priority
    - reason
    The reason must state the actual number of days remaining.
    Do not guess the current date.
    """,
    tools=[get_current_datetime, create_task],
    output_key="priority_analysis"
)


# root_agent = Agent(
#     model=LiteLlm("groq/llama-3.3-70b-versatile"),
#     name="orchestrator",
#     description="Orchestrates the email analysis and prioritization process.",
#     instruction="""
#     You are the main orchestrator for InboxAI.

#     Follow these steps:

#     1. Delegate the user's email to understand_mails.
#     2. Wait for the email analysis.
#     3. If a task exists, delegate to priority_agent.
#     4. Return the final result containing:
#        - Summary
#        - Task
#        - Deadline
#        - Priority
#        - Reason

#     Do not invent information.
#     """,
#     sub_agents=[understand_mails, priority_agent]
# )


email_workflow = SequentialAgent(
    name="email_workflow",
    sub_agents=[
        understand_mails,
        priority_agent
    ]
)

root_agent = email_workflow