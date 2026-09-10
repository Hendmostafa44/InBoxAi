import re

from google.adk.agents.llm_agent import Agent


CONFIRMATIONS = {
    "yes",
    "yes send",
    "yes send it",
    "send",
    "send it",
    "nice send it",
    "okay send it",
    "ok send it",
    "looks good send it",
    "ابعتها",
    "ابعت",
}
CANCELLATIONS = {"no", "no send", "no don't send", "cancel", "cancel it", "لا", "الغاء", "إلغاء"}


def _normalise(message: str) -> str:
    normalised = re.sub(r"[.!؟?،,]+", " ", message.strip().lower())
    return re.sub(r"\s+", " ", normalised).strip()


def is_confirmation(message: str) -> bool:
    return _normalise(message) in CONFIRMATIONS


def is_cancellation(message: str) -> bool:
    return _normalise(message) in CANCELLATIONS or "don't send" in message.lower()


send_mail_agent = Agent(
    model="gemini-3.5-flash-lite",
    name="send_mail_agent",
    description="Prepares email drafts and waits for explicit user confirmation before sending.",
    instruction="""
Prepare or modify an email draft. Never send an email and never call a sending tool.

For a new email request, extract a real recipient email address, write a concise subject
and professional body, and show the complete draft. If the recipient email or message
content is missing, respond normally and explain what is missing.

For a modification request containing CURRENT_DRAFT, preserve the recipient, sender,
sender name, original intent, and all important facts. Change only what the user asks for.

For every email draft or modification, return ONLY valid JSON in this exact structure:
{
    "response": "The complete draft shown to the user, followed by a confirmation question.",
    "draft": {
        "recipient": "...",
        "subject": "...",
        "body": "...",
        "sender": "...",
        "sender_name": "..."
    }
}
Do not add markdown fences or explanations around this JSON.
""",
)

root_agent = send_mail_agent
