from google.adk.agents.llm_agent import Agent
from google.adk.models.lite_llm import LiteLlm
from pydantic import BaseModel
from google.adk.agents import SequentialAgent
from tools.tools import get_current_datetime
from tools.tools import create_task
from tools.tools import save_task



understand_mails = Agent(
    model="gemini-3.5-flash-lite",
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

    Do not invent information.
    
    """,
    output_key="mail_analysis",
    tools=[]
)


priority_agent = Agent(
    model="gemini-3.5-flash-lite",
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
    after that all use the save_task tool to save the task, deadline, and priority in Redis.
    """,
    tools=[get_current_datetime, create_task,save_task],
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
    description="Orchestrates the email analysis and prioritization process.",
    sub_agents=[
        understand_mails,
        priority_agent
    ]
)

orchestrator = Agent(
    model="gemini-3.5-flash-lite",
    name="orchestrator",
    description="Orchestrates the email analysis and prioritization process.",
    instruction="""
    You are the Registration Agent for InboxAI.

Your job is to classify the user's message and decide whether it is a casual conversation or an email-management request.

Rules:

1. If the user sends a casual message such as "Hi", "Hello", "Hey", "How are you?", or general conversation, respond naturally and politely. Do NOT save it, analyze it as an email, or call any other agent.
2. If the user provides an email or asks to analyze, summarize, prioritize, or extract tasks/deadlines from an email, route the request to the InboxAI email-processing workflow.
3. Do not modify, summarize, or cut off the user's message.
4. Do not create or save tasks for casual messages.
5. When the message is ambiguous, treat it as casual conversation unless there is clear evidence that it is an email-management request.
6. Keep your response concise and natural.

Your main responsibility is routing, not email analysis.

    """,
    sub_agents=[email_workflow]
)

root_agent = orchestrator