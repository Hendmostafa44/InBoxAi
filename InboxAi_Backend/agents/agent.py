from google.adk.agents.llm_agent import Agent
from google.adk.models.lite_llm import LiteLlm

from pydantic import BaseModel
from tools.tools import get_current_datetime

class mail_summary(BaseModel):
    summary: str
    task: str
    deadline: str

understand_mails = Agent(
    model=LiteLlm("groq/llama-3.3-70b-versatile"),
    name='understand_mails',
    description="Analyzes emails and extracts their summary, tasks, and deadlines.",
    instruction="""
    You are an email analysis agent for InboxAI.

    Analyze the email provided by the user and extract the following information:

    1. Summary:
    Give a short and clear summary of the email.

    2. Task:
    Identify the action or task that the user needs to complete.
    If there is no task, return "No task".

    3. Deadline:
    Identify the deadline for the task.
    If there is no deadline, return "No deadline".

    Return the result in exactly this format:

    Summary: <short summary>
    Task: <task or No task>
    Deadline: <deadline or No deadline>

    Do not invent information that is not present in the email.
    """,
    output_schema=mail_summary,
    output_key="mail_analysis"
)


priority_agent = Agent(
    model=LiteLlm("groq/llama-3.3-70b-versatile"),
    name='priority_agent',
    description="Determines the priority of tasks based on their deadlines.",
    instruction="""
    Analyze the tasks and deadlines extracted from emails.

    Determine the priority of each task based primarily on how soon
    its deadline is:

    - High: deadline is today or tomorrow.
    - Medium: deadline is within the next 3 to 7 days.
    - Low: deadline is more than 7 days away or there is no urgent deadline.

    Always consider the deadline/time remaining as the main factor
    when determining priority.

    Return the task, deadline, priority, and a brief reason.
    """,
    tools=[get_current_datetime]
)


# task_from_mails = Agent(
#     model=LiteLlm("groq/llama-3.3-70b-versatile"),
#     name='task_from_mails',
#     description='A helpful assistant for user questions.',
#     instruction='Answer user questions to the best of your knowledge',
# )


root_agent = Agent(
    model=LiteLlm("groq/llama-3.3-70b-versatile"),
    name='orchestrator',
    description="Orchestrates the email analysis and prioritization process.",
    instruction="""
    You are the main orchestrator for InboxAI.

    When the user provides an email:
    1. Delegate the email to understand_mails to extract the summary, task, and deadline{mail_summary?}.
    2. If a task and deadline are found, delegate the result to priority_agent.
    3. Return a clear final response containing the summary, task, deadline, and priority.

    Do not invent information that is not present in the email.
    """,
    sub_agents=[understand_mails, priority_agent]
)

