import re
from email.utils import parseaddr

from google.adk.agents.llm_agent import Agent


EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
CONFIRMATIONS = {"yes", "yes send", "yes send it", "send", "send it", "ابعتها", "ابعت"}
CANCELLATIONS = {"no", "no send", "no don't send", "cancel", "cancel it", "لا", "الغاء", "إلغاء"}


def _normalise(message: str) -> str:
    normalised = re.sub(r"[.!؟?،,]+", " ", message.strip().lower())
    return re.sub(r"\s+", " ", normalised).strip()


def is_confirmation(message: str) -> bool:
    return _normalise(message) in CONFIRMATIONS


def is_cancellation(message: str) -> bool:
    return _normalise(message) in CANCELLATIONS or "don't send" in message.lower()


def is_send_request(message: str) -> bool:
    lowered = message.lower()
    return bool(
        re.search(r"\b(send|email|mail|write)\b", lowered)
        or re.search(r"\bإرسل|ارسل|ابعت|ابعث\b", message)
    )


def extract_recipient(message: str) -> str | None:
    match = EMAIL_PATTERN.search(message)
    if not match:
        return None
    address = parseaddr(match.group(0))[1].lower()
    return address if EMAIL_PATTERN.fullmatch(address) else None


def _extract_request_content(message: str, recipient: str) -> str:
    content = message.replace(recipient, " ")
    content = re.sub(
        r"^\s*(?:please\s+)?(?:send|email|mail|write)\s+(?:an?\s+)?email\s*(?:to)?\s*",
        "",
        content,
        flags=re.IGNORECASE,
    )
    content = re.sub(r"^\s*(?:saying|that|telling\s+(?:him|her|them)?)\s*", "", content, flags=re.IGNORECASE)
    content = re.sub(r"^\s*(?:لـ|الى|إلى)\s*", "", content)
    return re.sub(r"\s+", " ", content).strip(" .")


def _display_name(email_address: str) -> str:
    local_part = email_address.split("@", 1)[0]
    return re.sub(r"[._-]+", " ", local_part).title()


def _subject(content: str) -> str:
    days = "Sunday|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday"
    day_match = re.search(days, content, flags=re.IGNORECASE)
    if day_match and re.search(r"attend|come|work|unable|can't|cannot|won't", content, flags=re.IGNORECASE):
        return f"Unable to Attend on {day_match.group(0).title()}"
    words = re.findall(r"[A-Za-z0-9']+", content)
    summary = " ".join(words[:7]).strip()
    return f"Regarding {summary}" if summary else "A Note for You"


def prepare_draft(message: str, sender_email: str, sender_name: str = "") -> dict[str, str]:
    recipient = extract_recipient(message)
    if not recipient:
        raise ValueError("Please provide the recipient's email address.")

    content = _extract_request_content(message, recipient)
    if not content:
        raise ValueError("Please tell me what you would like the email to say.")

    if content[-1] not in ".!?؟":
        content += "."

    greeting_name = _display_name(recipient)
    body = f"Hi {greeting_name},\n\n{content}\n\nBest regards,"
    if sender_name.strip():
        body += f"\n{sender_name.strip()}"

    return {
        "recipient": recipient,
        "subject": _subject(content),
        "body": body,
        "sender": sender_email,
        "sender_name": sender_name,
    }


def modify_draft(draft: dict[str, str], request: str) -> dict[str, str]:
    updated = dict(draft)
    lowered = request.lower()
    if "subject" in lowered:
        subject_match = re.search(r"(?:subject|عنوان)\s*(?:to|بـ|هو)?\s*[:\-]?\s*(.+)$", request, re.IGNORECASE)
        if subject_match:
            updated["subject"] = subject_match.group(1).strip().rstrip(".!؟?")
    if "formal" in lowered or "رسمي" in request:
        updated["body"] = updated["body"].replace("Hi ", "Dear ", 1)
        updated["body"] = updated["body"].replace("won't be able to", "will be unable to")
        updated["body"] = updated["body"].replace("can't", "cannot")
    return updated


send_mail_agent = Agent(
    model="gemini-3.5-flash-lite",
    name="send_mail_agent",
    description="Prepares email drafts and waits for explicit user confirmation before sending.",
    instruction="""
Prepare an email draft from the user's request. Extract a real recipient email address,
write a concise subject and professional body, and show the complete draft. Never send an
email while preparing a draft. Sending is handled only by the backend after explicit confirmation.
If the recipient email or message content is missing, ask for the missing information.
""",
)

root_agent = send_mail_agent
