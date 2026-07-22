from redis import Redis
from rq import Queue

from app.config import get_settings


def queue():
    return Queue("servicepilot", connection=Redis.from_url(get_settings().redis_url), default_timeout=60)


def enqueue_webhook(ticket_id: str) -> bool:
    try:
        queue().enqueue("app.workflow.dispatch_webhook", ticket_id, retry=3)
        return True
    except Exception:
        return False
