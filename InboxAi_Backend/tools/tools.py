async def get_current_datetime() -> str:
    from datetime import datetime

    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


async def create_task(task: str, deadline: str, priority: str) -> dict:
    return {
        "status": "pending",
        "task": task,
        "deadline": deadline,
        "priority": priority
    }
