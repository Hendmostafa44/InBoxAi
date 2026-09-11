from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from agents.agent import root_agent
from send_mail_agent.agent import (
    is_cancellation,
    is_confirmation,
)
from send_mail_agent.gmail import get_gmail_account, send_email

from dotenv import load_dotenv

import asyncio
import os
import json
import uuid
import base64
import re
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone


# =========================================================
# ENV
# =========================================================

load_dotenv()


# =========================================================
# APP
# =========================================================

app = FastAPI()


# =========================================================
# SESSION
# =========================================================

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv(
        "SESSION_SECRET_KEY",
        "dev-secret-change-me"
    ),
    same_site="lax",
    https_only=False
)


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5500",
        "http://localhost:3000",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# DATABASE
# =========================================================

# Keep your existing engine import here.
# Example:
#
# from database import engine

from database import engine


# =========================================================
# GOOGLE CONFIG
# =========================================================

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

GOOGLE_REDIRECT_URI = os.getenv(
    "GOOGLE_REDIRECT_URI",
    "http://localhost:8007/auth/google/callback"
)

GOOGLE_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]


# =========================================================
# ADK
# =========================================================

session_service = InMemorySessionService()

runner = Runner(
    agent=root_agent,
    app_name="InboxAI",
    session_service=session_service,
)


# =========================================================
# HELPERS
# =========================================================

def require_user_id(request: Request) -> int:
    """
    Get the logged-in user ID from the session.
    """

    user_id = request.session.get("user_id")

    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Not logged in"
        )

    return user_id


def get_google_flow() -> Flow:
    """
    Create Google OAuth flow.
    """

    client_config = {
        "web": {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [
                GOOGLE_REDIRECT_URI
            ],
        }
    }

    flow = Flow.from_client_config(
        client_config,
        scopes=GOOGLE_SCOPES,
        redirect_uri=GOOGLE_REDIRECT_URI,
    )

    return flow


def get_header(headers, name):
    """
    Get a Gmail header value.
    """

    for header in headers:
        if header["name"].lower() == name.lower():
            return header["value"]

    return ""


def decode_gmail_body(data):
    """
    Decode Gmail base64url body.
    """

    if not data:
        return ""

    try:
        decoded = base64.urlsafe_b64decode(
            data.encode("UTF-8")
        )

        return decoded.decode(
            "UTF-8",
            errors="ignore"
        )

    except Exception:
        return ""


def extract_gmail_body(payload):
    """
    Extract text/plain body from Gmail message.
    """

    # Direct body
    body_data = payload.get("body", {}).get("data")

    if body_data:
        return decode_gmail_body(body_data)

    # Multipart body
    parts = payload.get("parts", [])

    for part in parts:

        mime_type = part.get("mimeType", "")

        if mime_type == "text/plain":

            data = part.get(
                "body",
                {}
            ).get("data")

            if data:
                return decode_gmail_body(data)

        # Nested multipart
        if part.get("parts"):

            nested_body = extract_gmail_body(part)

            if nested_body:
                return nested_body

    return ""


def parse_received_date(date_string):
    """
    Convert Gmail Date header into datetime.
    """

    if not date_string:
        return None

    try:
        return parsedate_to_datetime(
            date_string
        )

    except Exception:
        return None


def extract_json_object(raw_response):
    if not raw_response:
        return None

    text = str(raw_response).strip()
    text = text.replace("_output_", "", 1).strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        return None

    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None

def persist_gmail_tokens(
    gmail_account_id,
    credentials
):
    """
    Save updated Google OAuth credentials.
    """

    token = credentials.token

    refresh_token = credentials.refresh_token

    expiry = credentials.expiry

    with engine.begin() as connection:

        connection.execute(
            text("""
                UPDATE gmail_accounts
                SET
                    access_token = :access_token,
                    refresh_token = COALESCE(
                        :refresh_token,
                        refresh_token
                    ),
                    token_expiry = :token_expiry
                WHERE id = :gmail_account_id
            """),
            {
                "access_token": token,
                "refresh_token": refresh_token,
                "token_expiry": expiry,
                "gmail_account_id": gmail_account_id,
            }
        )


# =========================================================
# GOOGLE AUTH
# =========================================================

@app.get("/auth/google/login")
async def google_login(request: Request):

    print("[auth/google/login] Starting OAuth flow")
    flow = get_google_flow()

    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )

    request.session["oauth_state"] = state
    request.session["oauth_code_verifier"] = flow.code_verifier

    return RedirectResponse(url=authorization_url)


# =========================================================
# GOOGLE CALLBACK
# =========================================================

@app.get("/auth/google/callback")
async def google_callback(
    request: Request
):

    code = request.query_params.get("code")

    if not code:
        raise HTTPException(
            status_code=400,
            detail="Missing authorization code"
        )

    returned_state = request.query_params.get("state")
    expected_state = request.session.pop("oauth_state", None)
    if not expected_state or returned_state != expected_state:
        raise HTTPException(
            status_code=400,
            detail="Invalid OAuth state"
        )

    flow = get_google_flow()
    code_verifier = request.session.pop("oauth_code_verifier", None)

    if not code_verifier:
        raise HTTPException(
            status_code=400,
            detail="OAuth session expired. Please start Gmail connection again."
        )

    flow.fetch_token(
        code=code,
        code_verifier=code_verifier
    )
    
    credentials = flow.credentials
    print("GRANTED SCOPES:", credentials.scopes)
    print("[auth/google/callback] Token exchange succeeded")

    # -----------------------------------------
    # Get Google user information
    # -----------------------------------------

    oauth_service = build(
        "oauth2",
        "v2",
        credentials=credentials
    )

    google_user = oauth_service.userinfo().get().execute()

    google_id = google_user.get("id")
    email = google_user.get("email")
    name = google_user.get("name")

    if not google_id or not email:
        raise HTTPException(
            status_code=400,
            detail="Could not get Google user information"
        )

    print(f"[auth/google/callback] Google user={email}")

    # -----------------------------------------
    # Create / update user
    # -----------------------------------------

    with engine.begin() as connection:

        existing_user = connection.execute(
            text("""
                SELECT id
                FROM users
                WHERE google_id = :google_id
            """),
            {
                "google_id": google_id
            }
        ).fetchone()

        if existing_user:

            user_id = existing_user[0]

            connection.execute(
                text("""
                    UPDATE users
                    SET
                        email = :email,
                        name = :name
                    WHERE id = :user_id
                """),
                {
                    "email": email,
                    "name": name,
                    "user_id": user_id
                }
            )

        else:

            result = connection.execute(
                text("""
                    INSERT INTO users (
                        google_id,
                        email,
                        name
                    )
                    VALUES (
                        :google_id,
                        :email,
                        :name
                    )
                    RETURNING id
                """),
                {
                    "google_id": google_id,
                    "email": email,
                    "name": name
                }
            )

            user_id = result.fetchone()[0]
            print(f"[auth/google/callback] Created user_id={user_id}")

    # -----------------------------------------
    # Gmail account
    # -----------------------------------------

    with engine.begin() as connection:

        existing_account = connection.execute(
            text("""
                SELECT id
                FROM gmail_accounts
                WHERE user_id = :user_id
            """),
            {
                "user_id": user_id
            }
        ).fetchone()

        if existing_account:

            gmail_account_id = existing_account[0]

            connection.execute(
                text("""
                    UPDATE gmail_accounts
                    SET
                        gmail_email = :email,
                        access_token = :access_token,
                        refresh_token = COALESCE(
                            :refresh_token,
                            refresh_token
                        ),
                        token_expiry = :token_expiry
                    WHERE id = :gmail_account_id
                """),
                {
                    "email": email,
                    "access_token": credentials.token,
                    "refresh_token": credentials.refresh_token,
                    "token_expiry": credentials.expiry,
                    "gmail_account_id": gmail_account_id,
                }
            )
            print(f"[auth/google/callback] Updated gmail_account_id={gmail_account_id}")

        else:

            result = connection.execute(
                text("""
                    INSERT INTO gmail_accounts (
                        user_id,
                        gmail_email,
                        access_token,
                        refresh_token,
                        token_expiry
                    )
                    VALUES (
                        :user_id,
                        :email,
                        :access_token,
                        :refresh_token,
                        :token_expiry
                    )
                    RETURNING id
                """),
                {
                    "user_id": user_id,
                    "email": email,
                    "access_token": credentials.token,
                    "refresh_token": credentials.refresh_token,
                    "token_expiry": credentials.expiry,
                }
            )

            gmail_account_id = result.fetchone()[0]
            print(f"[auth/google/callback] Created gmail_account_id={gmail_account_id}")

    # -----------------------------------------
    # Create login session
    # -----------------------------------------

    request.session["user_id"] = user_id
    request.session["email"] = email
    request.session["name"] = name
    print(f"[auth/google/callback] Session user_id={user_id}")

    return RedirectResponse(
        url=os.getenv(
            "FRONTEND_URL",
            "http://localhost:5500/InboxAI_frontend/index.html"
        )
    )


# =========================================================
# CURRENT USER
# =========================================================

@app.get("/auth/me")
async def auth_me(request: Request):

    user_id = request.session.get("user_id")
    print(f"[auth/me] session user_id={user_id}")

    if not user_id:
        raise HTTPException(status_code=401, detail="Not logged in")

    with engine.connect() as connection:

        user = connection.execute(
            text("""
                SELECT
                    id,
                    created_at,
                    email,
                    name
                FROM users
                WHERE id = :user_id
            """),
            {
                "user_id": user_id
            }
        ).fetchone()

    if not user:

        request.session.clear()
        raise HTTPException(status_code=401, detail="Not logged in")

    return {
        "logged_in": True,
        "authenticated": True,
        "id": user[0],
        "email": user[2],
        "name": user[3],
    }


# =========================================================
# LOGOUT
# =========================================================

@app.post("/auth/logout")
async def logout(request: Request):

    request.session.clear()
    print("[auth/logout] Session cleared")

    return {
        "message": "Logged out successfully"
    }


# =========================================================
# ANALYZE EMAIL
# =========================================================

async def analyze_email_by_id(
    email_id: int,
    user_id: int
):
    """
    Analyze an email that already exists in SQL.

    IMPORTANT:
    This function is the single source of truth
    for email analysis.

    Both:
        POST /emails/{email_id}/analyze

    and:

        Gmail sync

    use this same function.
    """

    print(f"[analysis] Starting email_id={email_id} user_id={user_id}")

    # -----------------------------------------
    # Get email
    # -----------------------------------------

    with engine.connect() as connection:

        email = connection.execute(
            text("""
                SELECT
                    emails.id,
                    emails.sender,
                    emails.subject,
                    emails.body
                FROM emails
                JOIN gmail_accounts
                    ON gmail_accounts.id =
                       emails.gmail_account_id
                WHERE
                    emails.id = :email_id
                    AND gmail_accounts.user_id = :user_id
            """),
            {
                "email_id": email_id,
                "user_id": user_id
            }
        ).fetchone()

    if not email:

        raise HTTPException(
            status_code=404,
            detail="Email not found"
        )

    # -----------------------------------------
    # Build AI input
    # -----------------------------------------

    email_content = f"""
From: {email[1]}

Subject: {email[2]}

Body:
{email[3]}
"""

    # -----------------------------------------
    # Create fresh ADK session
    # -----------------------------------------

    analysis_user_id = f"inboxai_user_{user_id}"

    session_id = str(uuid.uuid4())

    await session_service.create_session(
        app_name="InboxAI",
        user_id=analysis_user_id,
        session_id=session_id,
    )

    # -----------------------------------------
    # Send email to agent
    # -----------------------------------------

    content = types.Content(
        role="user",
        parts=[
            types.Part(
                text=email_content
            )
        ],
    )

    final_response = ""

    try:
        async for event in runner.run_async(
            user_id=analysis_user_id,
            session_id=session_id,
            new_message=content,
        ):

            if event.is_final_response():

                if (
                    event.content
                    and event.content.parts
                ):

                    final_response = (
                        event.content.parts[0].text
                    )
    except Exception as error:
        print(f"AI analysis failed for email {email_id}: {error}")

    # -----------------------------------------
    # Parse AI response
    # -----------------------------------------

    analysis = extract_json_object(final_response)
    if not analysis:
        analysis = {
            "summary": email[2] or "Email received",
            "task": "No task",
            "deadline": "No deadline",
            "priority": "Medium",
        }

    # -----------------------------------------
    # Extract analysis
    # -----------------------------------------

    summary = analysis.get("summary") or email[2] or "Email received"
    task = analysis.get("task") or "No task"
    deadline = analysis.get("deadline") or "No deadline"
    priority = analysis.get("priority") or "Medium"

    # -----------------------------------------
    # SAVE ONLY ANALYSIS RESULT
    # -----------------------------------------

    with engine.begin() as connection:

        connection.execute(
            text("""
                UPDATE emails
                SET
                    summary = :summary,
                    task = :task,
                    deadline = :deadline,
                    priority = :priority
                WHERE id = :email_id
            """),
            {
                "summary": summary,
                "task": task,
                "deadline": deadline,
                "priority": priority,
                "email_id": email_id,
            }
        )

    print(f"[analysis] Saved analysis for email_id={email_id}")

    return {
        "summary": summary,
        "task": task,
        "deadline": deadline,
        "priority": priority,
    }


async def analyze_new_emails(email_ids: list[int], user_id: int):
    for email_id in email_ids:
        try:
            print(f"[analysis] Background analysis started for email_id={email_id}")
            await analyze_email_by_id(
                email_id=email_id,
                user_id=user_id,
            )
        except Exception as error:
            print(f"Background analysis failed for email {email_id}: {error}")


async def run_assistant_message(request: Request, user_id: int, message: str) -> str:
    assistant_user_id = f"inboxai_user_{user_id}"
    session_id = request.session.get("adk_session_id")

    session = None
    if session_id:
        session = await session_service.get_session(
            app_name="InboxAI",
            user_id=assistant_user_id,
            session_id=session_id,
        )

    if not session:
        session_id = str(uuid.uuid4())
        await session_service.create_session(
            app_name="InboxAI",
            user_id=assistant_user_id,
            session_id=session_id,
        )
        request.session["adk_session_id"] = session_id

    content = types.Content(
        role="user",
        parts=[types.Part(text=message)],
    )

    final_response = ""
    async for event in runner.run_async(
        user_id=assistant_user_id,
        session_id=session_id,
        new_message=content,
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final_response = "\n".join(
                part.text
                for part in event.content.parts
                if part.text
            )

    return final_response or "I could not generate a response. Please try again."


def build_agent_message(message: str, pending_draft: dict | None) -> str:
    if not pending_draft:
        return message

    return f"""
CURRENT_DRAFT
{json.dumps(pending_draft, ensure_ascii=False)}

USER_MESSAGE
{message}
""".strip()


def extract_agent_draft_response(
    model_response: str,
    original_draft: dict | None,
    sender_name: str,
) -> tuple[str, dict[str, str]] | None:
    result = extract_json_object(model_response)
    if isinstance(result, dict):
        draft = result.get("draft") or result
        response = result.get("response")
        if (
            isinstance(response, str)
            and (
                not isinstance(draft, dict)
                or not {"recipient", "subject", "body"}.issubset(draft)
            )
        ):
            result = None
            model_response = response
    else:
        draft = None
        response = None

    if not isinstance(result, dict):
        plain_text = str(model_response).strip()
        recipient_match = re.search(
            r"\bTo:\s*([^\s,;<>]+@[^\s,;<>]+)",
            plain_text,
            flags=re.IGNORECASE,
        )
        subject_match = re.search(
            r"\bSubject:\s*(.*?)(?=\s+Body:|\n|$)",
            plain_text,
            flags=re.IGNORECASE,
        )
        body_match = re.search(
            r"\bBody:\s*(.*?)(?=\s+(?:Would you like|Should I|Would you prefer)|$)",
            plain_text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not recipient_match or not subject_match or not body_match:
            return None

        draft = {
            "recipient": recipient_match.group(1).rstrip(".,"),
            "subject": subject_match.group(1).strip(),
            "body": body_match.group(1).strip(),
        }
        response = plain_text

    if not isinstance(draft, dict):
        return None
    if not isinstance(response, str):
        response = "Here is the email draft I prepared. Would you like me to send it?"

    required_fields = {"recipient", "subject", "body"}
    if not required_fields.issubset(draft):
        return None
    if not all(isinstance(draft[field], str) for field in required_fields):
        return None
    if not draft["recipient"].strip() or not draft["subject"].strip() or not draft["body"].strip():
        return None

    if original_draft:
        draft["recipient"] = original_draft["recipient"]
        draft["sender"] = original_draft.get("sender", "")
        draft["sender_name"] = original_draft.get("sender_name", sender_name)
    else:
        draft["sender"] = draft.get("sender", "")
        draft["sender_name"] = draft.get("sender_name", sender_name)

    return response, draft


@app.post("/analyze")
async def analyze_message(request: Request):
    user_id = require_user_id(request)
    payload = await request.json()
    message = payload.get("message", "").strip() if isinstance(payload, dict) else ""

    if not message:
        raise HTTPException(status_code=400, detail="Message is required")

    pending_draft = request.session.get("pending_email_draft")

    if pending_draft:
        if is_confirmation(message):
            try:
                send_email(
                    engine=engine,
                    user_id=user_id,
                    draft=pending_draft,
                    client_id=GOOGLE_CLIENT_ID,
                    client_secret=GOOGLE_CLIENT_SECRET,
                    scopes=GOOGLE_SCOPES,
                )
            except RuntimeError as error:
                return {"response": str(error)}

            request.session.pop("pending_email_draft", None)
            return {"response": "Email sent successfully."}

        if is_cancellation(message):
            request.session.pop("pending_email_draft", None)
            return {"response": "Okay, I cancelled the email."}

    try:
        agent_response = await run_assistant_message(
            request,
            user_id,
            build_agent_message(message, pending_draft),
        )
    except Exception as error:
        print(f"Assistant request failed for user_id={user_id}: {error}")
        return {"response": "I couldn't process that request right now. Please try again."}

    draft_result = extract_agent_draft_response(
        model_response=agent_response,
        original_draft=pending_draft,
        sender_name=request.session.get("name", ""),
    )
    if draft_result:
        response, draft = draft_result
        gmail_account = get_gmail_account(engine, user_id)
        if gmail_account:
            draft["sender"] = gmail_account[1]
        draft["sender_name"] = (
            pending_draft.get("sender_name", request.session.get("name", ""))
            if pending_draft
            else request.session.get("name", "")
        )
        request.session["pending_email_draft"] = draft
        return {"response": response, "draft": draft}

    return {"response": agent_response}


# =========================================================
# MANUAL EMAIL ANALYSIS
# =========================================================

@app.post("/emails/{email_id}/analyze")
async def analyze_saved_email(
    email_id: int,
    request: Request
):

    user_id = require_user_id(request)

    analysis = await analyze_email_by_id(
        email_id=email_id,
        user_id=user_id
    )

    return {
        "message": "Email analyzed and saved successfully",
        "email_id": email_id,
        "analysis": analysis
    }


# =========================================================
# GET EMAILS
# =========================================================

@app.get("/emails")
async def get_emails(
    request: Request
):

    user_id = require_user_id(request)
    print(f"[/emails] Loading emails for user_id={user_id}")

    with engine.connect() as connection:

        rows = connection.execute(
            text("""
                SELECT
                    emails.id,
                    emails.gmail_account_id,
                    emails.gmail_message_id,
                    emails.sender,
                    emails.subject,
                    emails.body,
                    emails.received_at,
                    emails.summary,
                    emails.task,
                    emails.deadline,
                    emails.priority,
                    emails.is_deleted,
                    emails.status
                FROM emails
                JOIN gmail_accounts
                    ON gmail_accounts.id =
                       emails.gmail_account_id
                                WHERE gmail_accounts.user_id = :user_id
                                    AND emails.is_deleted = FALSE
                ORDER BY emails.received_at DESC
            """),
            {
                "user_id": user_id
            }
        ).fetchall()

    emails = []

    for row in rows:

        emails.append({
            "id": row[0],
            "gmail_account_id": row[1],
            "gmail_message_id": row[2],
            "sender": row[3],
            "subject": row[4],
            "body": row[5],
            "received_at": row[6],
            "summary": row[7],
            "task": row[8],
            "deadline": row[9],
            "priority": row[10],
            "is_deleted": row[11],
            "status": row[12],
        })

    return emails


# =========================================================
# UPDATE EMAIL TASK STATUS
# =========================================================

@app.patch("/emails/{email_id}/status")
async def update_email_status(
    email_id: int,
    request: Request,
):

    user_id = require_user_id(request)
    payload = await request.json()
    status = payload.get("status") if isinstance(payload, dict) else None

    if status not in {"Pending", "Completed"}:
        raise HTTPException(
            status_code=400,
            detail="Status must be Pending or Completed",
        )

    try:
        with engine.begin() as connection:
            result = connection.execute(
                text("""
                    UPDATE emails
                    SET status = :status
                    WHERE id = :email_id
                        AND is_deleted = FALSE
                        AND gmail_account_id IN (
                            SELECT id
                            FROM gmail_accounts
                            WHERE user_id = :user_id
                        )
                """),
                {
                    "email_id": email_id,
                    "status": status,
                    "user_id": user_id,
                },
            )

        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Email not found")

        return {
            "email_id": email_id,
            "status": status,
        }
    except HTTPException:
        raise
    except SQLAlchemyError as error:
        print(f"Email status update failed for {email_id}: {error}")
        raise HTTPException(
            status_code=500,
            detail="Unable to update email status",
        )


# =========================================================
# GMAIL EMAILS
# =========================================================

@app.get("/gmail/emails")
async def get_gmail_emails(
    request: Request
):

    user_id = require_user_id(request)
    print(f"[/gmail/emails] Sync requested for user_id={user_id}")

    # -----------------------------------------
    # Get Gmail account for logged-in user
    # -----------------------------------------

    with engine.connect() as connection:

        gmail_account = connection.execute(
            text("""
                SELECT
                    id,
                    gmail_email,
                    access_token,
                    refresh_token,
                    token_expiry
                FROM gmail_accounts
                WHERE user_id = :user_id
            """),
            {
                "user_id": user_id
            }
        ).fetchone()

    if not gmail_account:

        raise HTTPException(
            status_code=404,
            detail="No Gmail account connected"
        )

    gmail_account_id = gmail_account[0]

    # -----------------------------------------
    # Google credentials
    # -----------------------------------------

    token_expiry = gmail_account[4]
    if token_expiry:
        try:
            token_expiry = datetime.fromisoformat(
                str(token_expiry).replace("Z", "+00:00")
            )
        except ValueError:
            token_expiry = None

    credentials = Credentials(
        token=gmail_account[2],
        refresh_token=gmail_account[3],
        expiry=token_expiry,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        scopes=GOOGLE_SCOPES,
    )

    if credentials.expired and credentials.refresh_token:
        print(f"[/gmail/emails] Refreshing Gmail token for account_id={gmail_account_id}")
        credentials.refresh(GoogleRequest())

    # -----------------------------------------
    # Gmail API
    # -----------------------------------------

    gmail_service = build(
        "gmail",
        "v1",
        credentials=credentials
    )

    # -----------------------------------------
    # Get latest messages
    # -----------------------------------------

    messages_response = (
        gmail_service
        .users()
        .messages()
        .list(
            userId="me",
            labelIds=["INBOX"],
            maxResults=10
        )
        .execute()
    )

    messages = messages_response.get(
        "messages",
        []
    )
    print(f"[/gmail/emails] Gmail returned {len(messages)} messages")

    saved_emails = []
    new_email_ids = []
    inserted_count = 0

    # =====================================================
    # PROCESS EACH GMAIL MESSAGE
    # =====================================================

    for message_item in messages:

        message_id = message_item["id"]

        # -----------------------------------------
        # Check duplicate
        # -----------------------------------------

        with engine.connect() as connection:

            existing = connection.execute(
                text("""
                    SELECT id, is_deleted
                    FROM emails
                    WHERE
                        gmail_account_id =
                        :gmail_account_id

                        AND gmail_message_id =
                        :gmail_message_id
                """),
                {
                    "gmail_account_id":
                        gmail_account_id,

                    "gmail_message_id":
                        message_id,
                }
            ).fetchone()

        # -----------------------------------------
        # Already exists
        # -----------------------------------------

        if existing:
            print(
                f"[/gmail/emails] Skipping existing email_id={existing[0]} "
                f"deleted={existing[1]}"
            )
            continue

        # -----------------------------------------
        # Get complete Gmail message
        # -----------------------------------------

        message = (
            gmail_service
            .users()
            .messages()
            .get(
                userId="me",
                id=message_id,
                format="full"
            )
            .execute()
        )

        payload = message.get(
            "payload",
            {}
        )

        headers = payload.get(
            "headers",
            []
        )

        # -----------------------------------------
        # Extract fields
        # -----------------------------------------

        sender = get_header(
            headers,
            "From"
        )

        subject = get_header(
            headers,
            "Subject"
        )

        date_header = get_header(
            headers,
            "Date"
        )

        received_at = parse_received_date(
            date_header
        )

        if received_at is None and message.get("internalDate"):
            received_at = datetime.fromtimestamp(
                int(message["internalDate"]) / 1000,
                tz=timezone.utc
            )

        body = extract_gmail_body(
            payload
        )

        # =================================================
        # STEP 1
        # SAVE BASE EMAIL ONLY
        # =================================================

        with engine.begin() as connection:

            result = connection.execute(
                text("""
                    INSERT INTO emails (
                        gmail_account_id,
                        gmail_message_id,
                        sender,
                        subject,
                        body,
                        received_at,
                        status,
                        is_deleted
                    )
                    VALUES (
                        :gmail_account_id,
                        :gmail_message_id,
                        :sender,
                        :subject,
                        :body,
                        :received_at,
                        'Pending',
                        FALSE
                    )
                    ON CONFLICT (gmail_account_id, gmail_message_id)
                    DO NOTHING
                    RETURNING id
                """),
                {
                    "gmail_account_id":
                        gmail_account_id,

                    "gmail_message_id":
                        message_id,

                    "sender":
                        sender,

                    "subject":
                        subject,

                    "body":
                        body,

                    "received_at":
                        received_at,
                }
            )

            inserted_email = result.fetchone()

            if not inserted_email:
                print(
                    f"[/gmail/emails] Skipping duplicate message_id={message_id}"
                )
                continue

            email_id = inserted_email[0]
            new_email_ids.append(email_id)
            inserted_count += 1

        # -----------------------------------------
        # Response
        # -----------------------------------------

        saved_emails.append({
            "id": email_id,
            "gmail_message_id": message_id,
            "sender": sender,
            "subject": subject,
            "status": "saved",
            "analysis": None
        })

    # -----------------------------------------
    # Save refreshed token if needed
    # -----------------------------------------

    persist_gmail_tokens(
        gmail_account_id,
        credentials
    )

    if new_email_ids:
        asyncio.create_task(
            analyze_new_emails(
                email_ids=new_email_ids,
                user_id=user_id,
            )
        )

    print(f"[/gmail/emails] Inserted {inserted_count} new emails")

    return {
        "count": len(saved_emails),
        "emails": saved_emails
    }


# =========================================================
# DELETE TASK EMAIL
# =========================================================

@app.delete("/tasks/{task_id}")
async def delete_task(
    task_id: int,
    request: Request
):

    user_id = require_user_id(request)

    try:
        with engine.begin() as connection:
            result = connection.execute(
                text("""
                                        UPDATE emails
                                        SET is_deleted = TRUE
                                        WHERE id = :task_id
                                            AND is_deleted = FALSE
                                            AND gmail_account_id IN (
                          SELECT id
                          FROM gmail_accounts
                          WHERE user_id = :user_id
                      )
                """),
                {
                    "task_id": task_id,
                    "user_id": user_id,
                }
            )

        if result.rowcount == 0:
            raise HTTPException(
                status_code=404,
                detail="Task email not found"
            )

        return {
            "message": "Email deleted from InboxAI",
            "task_id": task_id,
        }

    except HTTPException:
        raise
    except SQLAlchemyError as error:
        print(f"Task deletion failed for email {task_id}: {error}")
        raise HTTPException(
            status_code=500,
            detail="Unable to delete task"
        )


# =========================================================
# HEALTH CHECK
# =========================================================

@app.get("/")
async def root():

    return {
        "message": "InboxAI backend is running"
    }


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8007
    )