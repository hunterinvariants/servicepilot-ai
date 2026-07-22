import hashlib
import hmac
import secrets
import time
from collections import defaultdict, deque
from dataclasses import dataclass

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ApiKey, User


def hash_secret(value: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", value.encode(), salt.encode(), 210_000).hex()
    return f"{salt}${digest}"


def verify_secret(value: str, encoded: str) -> bool:
    try:
        salt, expected = encoded.split("$", 1)
    except ValueError:
        return False
    actual = hashlib.pbkdf2_hmac("sha256", value.encode(), salt.encode(), 210_000).hex()
    return hmac.compare_digest(actual, expected)


@dataclass(frozen=True)
class Principal:
    user_id: str
    organization_id: str
    email: str
    role: str


def current_principal(request: Request, db: Session) -> Principal | None:
    user_id = request.session.get("user_id")
    if user_id:
        user = db.scalar(select(User).where(User.id == user_id, User.active.is_(True)))
        if user:
            return Principal(user.id, user.organization_id, user.email, user.role)
    presented = request.headers.get("X-API-Key", "")
    if presented:
        prefix = presented[:12]
        keys = db.scalars(select(ApiKey).where(ApiKey.prefix == prefix, ApiKey.active.is_(True))).all()
        key = next((item for item in keys if verify_secret(presented, item.key_hash)), None)
        if key:
            return Principal(f"api:{key.id}", key.organization_id, key.name, "operator")
    return None


def require_principal(request: Request, db: Session, roles: set[str] | None = None) -> Principal:
    principal = current_principal(request, db)
    if not principal:
        raise HTTPException(401, "Authentication required")
    if roles and principal.role not in roles:
        raise HTTPException(403, "Insufficient role")
    return principal


class RateLimiter:
    def __init__(self):
        self.events: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str, limit: int, window_seconds: int = 60):
        now = time.monotonic()
        bucket = self.events[key]
        while bucket and bucket[0] <= now - window_seconds:
            bucket.popleft()
        if len(bucket) >= limit:
            raise HTTPException(429, "Rate limit exceeded")
        bucket.append(now)


rate_limiter = RateLimiter()

