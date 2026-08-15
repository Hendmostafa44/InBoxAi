import os
import json
import redis
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).parent.parent / "agents" / ".env"
load_dotenv(env_path)

r = redis.Redis(
    host=os.getenv("REDIS_HOST"),
    port=int(os.getenv("REDIS_PORT", 10942)),
    username=os.getenv("REDIS_USERNAME"),
    password=os.getenv("REDIS_PASSWORD"),
    decode_responses=True
)


async def get_current_datetime() -> str:
    from datetime import datetime

    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


async def create_task(task: str, deadline: str, priority: str) -> dict:
    return {
        "status": "success",
        "task": task,
        "deadline": deadline,
        "priority": priority
    }


def save_task(summary: str, task: str, deadline: str):
    email = json.dumps({
        "summary": summary,
        "task": task,
        "deadline": deadline
    })

    r.rpush("emails", email)

    return {
        "status": "success",
        "message": "Task saved successfully"
    }