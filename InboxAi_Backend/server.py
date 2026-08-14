from fastapi import FastAPI
from pydantic import BaseModel
import os
import redis
from dotenv import load_dotenv
import json
from pathlib import Path

env_path = Path(__file__).parent / "agents" / ".env"
load_dotenv(env_path)

app = FastAPI()

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



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8007)

