async def get_current_datetime() -> str:
    """
    Returns the current date and time in a human-readable format.
    """
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")