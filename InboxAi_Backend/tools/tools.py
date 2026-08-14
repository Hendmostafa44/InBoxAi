async def get_current_datetime() -> str:
    """
    Returns the current date and time in a human-readable format.
    """
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


async def create_task(task: str, deadline: str, priority: str) -> dict:
    """
    Creates a new task from an analyzed email.

    Args:
        task: The task to create.
        deadline: The task deadline.
        priority: The task priority.

    Returns:
        Information about the created task.
    """
    
    return {
        "status": "success",
        "task": task,
        "deadline": deadline,
        "priority": priority
    }


import requests

def save_email(summary: str, task: str, deadline: str):
    response = requests.post(
        "http://localhost:8007/save_task",
        json={
            "summary": summary,
            "task": task,
            "deadline": deadline
        }
    )

    return response.json()