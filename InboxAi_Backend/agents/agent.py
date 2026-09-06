from google.adk.agents.llm_agent import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.agents import SequentialAgent

from tools.tools import (
    get_current_datetime,
    create_task,
    save_task
)


# ==========================================
# MODEL
# ==========================================

model="gemini-3.5-flash-lite"

# ==========================================
# 1. UNDERSTAND EMAIL
# ==========================================

understand_mails = Agent(
    model=model,
    name="understand_mails",

    description="""
    Analyzes emails and extracts summary, task, and deadline.
    """,

    instruction="""
You are an email analysis agent for InboxAI.

Analyze the email provided by the user.

Extract exactly these fields:

- summary: a short and clear summary of the email
- task: the action the user needs to complete
- deadline: the deadline mentioned in the email

Rules:

1. If there is no task, use:
   "No task"

2. If there is no deadline, use:
   "No deadline"

3. If a deadline exists, return it in:
   YYYY-MM-DD

4. Do not invent information.

5. Return ONLY a JSON object.

The JSON must have exactly this structure:

{
    "summary": "...",
    "task": "...",
    "deadline": "..."
}

Do not add explanations.
Do not add markdown.
Do not add ```json.
""",

    output_key="mail_analysis",

    tools=[]
)


# ==========================================
# 2. PRIORITY AGENT
# ==========================================

priority_agent = Agent(
    model=model,
    name="priority_agent",

    description="""
    Determines task priority based on the email deadline.
    """,

    instruction="""
You are a priority analysis agent for InboxAI.

You will receive the email analysis:

{mail_analysis}

First, use the get_current_datetime tool to get the current date and time.

Determine the priority based on the deadline.

Priority rules:

- High: deadline is today or within the next 2 days.
- Medium: deadline is 3 to 7 days away.
- Low: deadline is more than 7 days away.
- If there is no deadline, use Medium.

Do not guess the current date.

If there is no task:
- task = "No task"
- priority = "Medium"

You MUST call create_task when there is a real task.

Then ALWAYS call save_task to save the task, deadline, and priority in Redis.

Return ONLY a JSON object with exactly:

{
    "summary": "...",
    "task": "...",
    "deadline": "...",
    "priority": "...",
    "reason": "..."
}

The summary must be taken from the original email analysis.

The reason must state the actual number of days remaining.

Do not add explanations.
Do not add markdown.
Do not add ```json.
""",

    tools=[
        get_current_datetime,
        create_task,
        save_task
    ],

    output_key="priority_analysis"
)


# ==========================================
# EMAIL WORKFLOW
# ==========================================

email_workflow = SequentialAgent(
    name="email_workflow",

    sub_agents=[
        understand_mails,
        priority_agent
    ]
)


# ==========================================
# ORCHESTRATOR
# ==========================================

orchestrator = Agent(
    model=model,

    name="orchestrator",

    description="""
    Routes casual messages and email-management requests.
    """,

    instruction="""
You are the main routing agent for InboxAI.

Your job is to determine whether the user's message is casual conversation
or an email-management request.

Rules:

1. If the user sends a casual message such as:
   "Hi"
   "Hello"
   "Hey"
   "How are you?"

   Respond naturally and politely.

   Do NOT call the email workflow.

2. If the user provides an email or asks to:
   - analyze an email
   - summarize an email
   - extract a task
   - extract a deadline
   - determine priority

   Route the request to the email-processing workflow.

3. Do not modify or cut off the user's email.

4. Do not create tasks for casual messages.

5. When ambiguous, treat it as casual conversation.

6. Keep casual responses concise.

Your main responsibility is routing.
""",

    sub_agents=[
        email_workflow
    ]
)


# ==========================================
# ROOT AGENT
# ==========================================

root_agent = orchestrator