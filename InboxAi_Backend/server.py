from fastapi import FastAPI
from pydantic import BaseModel
import os
import redis
from dotenv import load_dotenv
import json
from pathlib import Path
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from fastapi.middleware.cors import CORSMiddleware
from agents.agent import root_agent
################### login imports
from authlib.integrations.starlette_client import OAuth
from starlette.requests import Request
from starlette.responses import RedirectResponse
################### database imports
from sqlalchemy import text
from database import engine
#################### Google API imports
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import base64
from datetime import datetime, timezone


env_path = Path(__file__).parent / "agents" / ".env"
load_dotenv(env_path)
oauth = OAuth()

oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={
        "scope": "openid email profile https://www.googleapis.com/auth/gmail.readonly",
        "access_type": "offline",
    }
)


app = FastAPI()

from starlette.middleware.sessions import SessionMiddleware

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET_KEY", "dev-secret-change-me"),
    same_site="lax",
    https_only=False
)



app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "https://inboxai.fastapicloud.dev"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

r = redis.Redis(
    host=os.getenv("REDIS_HOST"),
    port=int(os.getenv("REDIS_PORT", 10942)),
    username=os.getenv("REDIS_USERNAME"),
    password=os.getenv("REDIS_PASSWORD"),
    decode_responses=True
)

class MailSummary(BaseModel):
    summary: str
    task: str
    deadline: str
    priority: str

class AIEmailAnalysis(BaseModel):
    summary: str
    priority: str
    task: str
    deadline: str

@app.post("/save_task")
async def save_task(mail_summary: MailSummary):

    email = json.dumps({
        "id": str(uuid.uuid4()),
        "summary": mail_summary.summary,
        "task": mail_summary.task,
        "deadline": mail_summary.deadline,
        "priority": mail_summary.priority,
        "status": "pending"
    })

    r.rpush("emails", email)

    return {"message": "Email saved successfully"}

import uuid
session_service = InMemorySessionService()

runner = Runner(
    agent=root_agent,
    app_name="InboxAI",
    session_service=session_service,
)
class EmailRequest(BaseModel):
    message: str

@app.post("/analyze")
async def analyze_email(request: EmailRequest):

    print("1. Request received:", request.message)

    user_id = "frontend_user"
    session_id =str(uuid.uuid4())  ### importana!!! every email request should have a new session id to avoid any context from previous requests

    print("2. Creating session...")

    await session_service.create_session(
        app_name="InboxAI",
        user_id=user_id,
        session_id=session_id,
    )

    print("3. Session created")

    content = types.Content(
        role="user",
        parts=[
            types.Part(text=request.message)
        ],
    )

    print("4. Starting agent...")

    final_response = ""

    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=content,
    ):
        print("5. Event received:", event)

        if event.is_final_response():
            if event.content and event.content.parts:
                final_response = event.content.parts[0].text

    print("6. Agent finished")

    return {
        "response": final_response
    }

@app.get("/tasks/count")
async def get_tasks_count():
    count = r.llen("emails")
    return {"count": count}


@app.get("/tasks/pending/count")
async def get_pending_tasks_count():
    tasks = r.lrange("emails", 0, -1)

    pending_count = sum(
        1
        for task in tasks
        if json.loads(task).get("status") == "pending"
    )

    return {"count": pending_count}



@app.get("/tasks/priorities")
async def get_priorities():
    tasks = r.lrange("emails", 0, -1)

    result = []

    for task in tasks:
        task = json.loads(task)

        if task.get("priority") in ["High", "Medium", "Low"]:
            result.append(task)

    return result

@app.get("/tasks/all")
async def get_all_tasks():
    raw_tasks = r.lrange("emails", 0, -1)
    parsed_tasks = []

    for index, task_str in enumerate(raw_tasks):
        task_data = json.loads(task_str)
        if "id" not in task_data:
            task_data["id"] = str(uuid.uuid4())
            r.lset("emails", index, json.dumps(task_data))
        parsed_tasks.append(task_data)

    return parsed_tasks



@app.put("/tasks/status")
async def update_task_status(task_name: str | None = None, status: str = "pending", task_id: str | None = None):
    tasks = r.lrange("emails", 0, -1)

    for index, task in enumerate(tasks):
        task_data = json.loads(task)

        is_match = False
        if task_id and task_data.get("id") == task_id:
            is_match = True
        elif task_name and task_data.get("task") == task_name:
            is_match = True

        if is_match:
            task_data["status"] = status
            r.lset("emails", index, json.dumps(task_data))
            return {
                "message": "Task status updated",
                "status": status
            }

    return {"message": "Task not found"}

@app.get("/tasks/urgent")
async def get_urgent_tasks():
    count=0
    tasks = r.lrange("emails", 0, -1)
    for task in tasks:
        task = json.loads(task)
        if task.get("priority") == "High" and task.get("status") == "pending":
            count += 1
    return count
    
@app.get("/auth/google/login")
async def google_login(request: Request):
    redirect_uri = request.url_for("google_callback")

    return await oauth.google.authorize_redirect(
        request,
        redirect_uri,
        access_type="offline",
        prompt="consent"
    )


@app.get("/auth/google/callback")
async def google_callback(request: Request):

    token = await oauth.google.authorize_access_token(request)

    userinfo = token.get("userinfo")

    if not userinfo:
        userinfo = await oauth.google.userinfo(token=token)

    google_id = userinfo.get("sub")
    email = userinfo.get("email")
    name = userinfo.get("name")

    access_token = token.get("access_token")
    refresh_token = token.get("refresh_token")

    user_id = None

    with engine.begin() as connection:

        # 1. Check if user already exists
        result = connection.execute(
            text("""
                SELECT id
                FROM users
                WHERE google_id = :google_id
            """),
            {
                "google_id": google_id
            }
        )

        existing_user = result.fetchone()

        # 2. Create user if this is the first login
        if existing_user:

            user_id = existing_user[0]

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

        # 3. Check if Gmail account already exists
        result = connection.execute(
            text("""
                SELECT id
                FROM gmail_accounts
                WHERE user_id = :user_id
                AND gmail_email = :gmail_email
            """),
            {
                "user_id": user_id,
                "gmail_email": email
            }
        )

        existing_gmail = result.fetchone()

        # 4. Update existing Gmail account
        if existing_gmail:

            connection.execute(
                text("""
                    UPDATE gmail_accounts
                    SET
                        access_token = :access_token,
                        refresh_token = COALESCE(
                            :refresh_token,
                            refresh_token
                        )
                    WHERE id = :id
                """),
                {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "id": existing_gmail[0]
                }
            )

        # 5. Create Gmail account
        else:

            connection.execute(
                text("""
                    INSERT INTO gmail_accounts (
                        user_id,
                        gmail_email,
                        access_token,
                        refresh_token
                    )
                    VALUES (
                        :user_id,
                        :gmail_email,
                        :access_token,
                        :refresh_token
                    )
                """),
                {
                    "user_id": user_id,
                    "gmail_email": email,
                    "access_token": access_token,
                    "refresh_token": refresh_token
                }
            )

    # 6. Create server-side session
    request.session["user_id"] = user_id
    request.session["email"] = email
    request.session["name"] = name

    # 7. Redirect back to frontend
    return RedirectResponse(
    url="http://localhost:5500/InboxAI_frontend/index.html"
        )

@app.get("/gmail/emails")
async def get_gmail_emails():

    # 1. Get the latest connected Gmail account
    with engine.connect() as connection:
        result = connection.execute(
            text("""
                SELECT id, access_token, refresh_token
                FROM gmail_accounts
                ORDER BY id DESC
                LIMIT 1
            """)
        )

        gmail_account = result.fetchone()

    if not gmail_account:
        return {
            "error": "No Gmail account connected"
        }

    gmail_account_id = gmail_account[0]
    access_token = gmail_account[1]
    refresh_token = gmail_account[2]

    # 2. Create Google credentials
    credentials = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        scopes=[
            "https://www.googleapis.com/auth/gmail.readonly"
        ]
    )

    # 3. Create Gmail API client
    gmail = build(
        "gmail",
        "v1",
        credentials=credentials
    )

    # 4. Get latest 10 emails
    response = gmail.users().messages().list(
        userId="me",
        maxResults=10
    ).execute()

    messages = response.get("messages", [])

    saved_emails = []

    # 5. Process every email
    for message in messages:

        message_id = message["id"]

        # Get full email details
        email_data = gmail.users().messages().get(
            userId="me",
            id=message_id,
            format="full"
        ).execute()

        payload = email_data.get("payload", {})

        # --------------------------------
        # Get headers
        # --------------------------------

        headers = payload.get("headers", [])

        sender = ""
        subject = ""

        for header in headers:

            header_name = header.get("name", "").lower()
            header_value = header.get("value", "")

            if header_name == "from":
                sender = header_value

            elif header_name == "subject":
                subject = header_value

        # --------------------------------
        # Get received date
        # --------------------------------

        internal_date = email_data.get("internalDate")

        received_at = None

        if internal_date:
            from datetime import datetime, timezone

            received_at = datetime.fromtimestamp(
                int(internal_date) / 1000,
                tz=timezone.utc
            )

        # --------------------------------
        # Get email body
        # --------------------------------

        body = ""

        # Case 1: Simple email body
        if payload.get("body", {}).get("data"):

            data = payload["body"]["data"]

            body = base64.urlsafe_b64decode(
                data
            ).decode(
                "utf-8",
                errors="ignore"
            )

        # Case 2: Multipart email
        elif payload.get("parts"):

            for part in payload["parts"]:

                mime_type = part.get("mimeType", "")

                if mime_type == "text/plain":

                    data = part.get("body", {}).get("data")

                    if data:

                        body = base64.urlsafe_b64decode(
                            data
                        ).decode(
                            "utf-8",
                            errors="ignore"
                        )

                        break

        # --------------------------------
        # Check if email already exists
        # --------------------------------

        with engine.connect() as connection:

            existing = connection.execute(
                text("""
                    SELECT id
                    FROM emails
                    WHERE gmail_account_id = :gmail_account_id
                    AND gmail_message_id = :gmail_message_id
                """),
                {
                    "gmail_account_id": gmail_account_id,
                    "gmail_message_id": message_id
                }
            ).fetchone()

        # --------------------------------
        # Save new email
        # --------------------------------

        if not existing:

            with engine.begin() as connection:

                connection.execute(
                    text("""
                        INSERT INTO emails (
                            gmail_account_id,
                            gmail_message_id,
                            sender,
                            subject,
                            body,
                            received_at
                        )
                        VALUES (
                            :gmail_account_id,
                            :gmail_message_id,
                            :sender,
                            :subject,
                            :body,
                            :received_at
                        )
                    """),
                    {
                        "gmail_account_id": gmail_account_id,
                        "gmail_message_id": message_id,
                        "sender": sender,
                        "subject": subject,
                        "body": body,
                        "received_at": received_at
                    }
                )

            saved_emails.append({
                "gmail_message_id": message_id,
                "sender": sender,
                "subject": subject
            })

    # --------------------------------
    # Response
    # --------------------------------

    return {
        "message": "Emails fetched successfully",
        "fetched": len(messages),
        "saved": len(saved_emails),
        "emails": saved_emails
    }


@app.get("/emails")
async def get_saved_emails():

    with engine.connect() as connection:

        result = connection.execute(
            text("""
                SELECT
                    id,
                    gmail_account_id,
                    gmail_message_id,
                    sender,
                    subject,
                    body,
                    received_at
                FROM emails
                ORDER BY received_at DESC
            """)
        )

        rows = result.fetchall()

    emails = []

    for row in rows:
        emails.append({
            "id": row[0],
            "gmail_account_id": row[1],
            "gmail_message_id": row[2],
            "sender": row[3],
            "subject": row[4],
            "body": row[5],
            "received_at": row[6]
        })

    return {
        "count": len(emails),
        "emails": emails
    }

@app.post("/emails/{email_id}/analyze")
async def analyze_saved_email(email_id: int):

    # 1. Get email from Supabase
    with engine.connect() as connection:
        result = connection.execute(
            text("""
                SELECT
                    id,
                    sender,
                    subject,
                    body
                FROM emails
                WHERE id = :email_id
            """),
            {
                "email_id": email_id
            }
        )

        email = result.fetchone()

    if not email:
        return {
            "error": "Email not found"
        }

    # 2. Prepare email for AI
    email_content = f"""
From: {email[1]}
Subject: {email[2]}

Body:
{email[3]}
"""

    # 3. Create AI session
    user_id = "email_analysis_user"
    session_id = str(uuid.uuid4())

    await session_service.create_session(
        app_name="InboxAI",
        user_id=user_id,
        session_id=session_id,
    )

    # 4. Send email to AI
    content = types.Content(
        role="user",
        parts=[
            types.Part(text=email_content)
        ],
    )

    # 5. Run AI workflow
    final_response = ""

    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=content,
    ):

        if event.is_final_response():

            if event.content and event.content.parts:

                final_response = event.content.parts[0].text

    # 6. Convert AI JSON string to Python dictionary
    try:
        analysis = json.loads(final_response)
    except json.JSONDecodeError:
        return {
            "error": "AI returned invalid JSON",
            "raw_response": final_response
        }

    # 7. Extract fields
    summary = analysis.get("summary", "")
    task = analysis.get("task", "No task")
    deadline = analysis.get("deadline", "No deadline")
    priority = analysis.get("priority", "Medium")

    # 8. Save AI analysis to Supabase
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
                "email_id": email_id
            }
        )

    # 9. Return result
    return {
        "message": "Email analyzed and saved successfully",
        "email_id": email_id,
        "analysis": {
            "summary": summary,
            "task": task,
            "deadline": deadline,
            "priority": priority
        }
    }

@app.get("/auth/me")
async def get_current_user(request: Request):

    user_id = request.session.get("user_id")

    if not user_id:
        return {
            "authenticated": False
        }

    return {
        "authenticated": True,
        "user_id": user_id,
        "email": request.session.get("email"),
        "name": request.session.get("name")
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8007)

