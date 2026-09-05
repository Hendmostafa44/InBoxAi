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
@app.get("/test-redis")
async def test_redis():
    try:
        result = r.ping()
        return {
            "redis": "connected",
            "ping": result
        }
    except Exception as e:
        return {
            "redis": "error",
            "message": str(e)
        }

class MailSummary(BaseModel):
    summary: str
    task: str
    deadline: str
    priority: str


class UserRequest(BaseModel):
    name: str

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
    
@app.post("/users/login")
async def login_user(user: UserRequest):

    name = user.name.strip()

    if not name:
        return {
            "success": False,
            "message": "Name is required"
        }

    users_key = "users"
    user_emails_key = f"user:{name}:emails"

    exists = r.sismember(users_key, name)

    if not exists:
        r.sadd(users_key, name)

        return {
            "success": True,
            "new_user": True,
            "name": name
        }

    return {
        "success": True,
        "new_user": False,
        "name": name
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8007)

