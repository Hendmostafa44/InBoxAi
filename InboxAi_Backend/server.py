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

env_path = Path(__file__).parent / "agents" / ".env"
load_dotenv(env_path)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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


@app.post("/save_task")
async def save_task(mail_summary: MailSummary):
    # return {
    #     "summary": mail_summary.summary,
    #     "task": mail_summary.task,
    #     "deadline": mail_summary.deadline
    # }
    email= json.dumps({
    "summary": mail_summary.summary,
    "task": mail_summary.task,
    "deadline": mail_summary.deadline
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8007)

