import hashlib
import hmac
import json
import time


def canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def signature(payload: dict, secret: str, timestamp: int | None = None) -> str:
    timestamp = timestamp or int(time.time())
    body = str(timestamp).encode() + b"." + canonical(payload)
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"


def verify_signature(payload: dict, header: str, secret: str, tolerance: int = 300) -> bool:
    try:
        parts = dict(item.split("=", 1) for item in header.split(","))
        timestamp = int(parts["t"])
        supplied = parts["v1"]
    except (KeyError, ValueError):
        return False
    if abs(int(time.time()) - timestamp) > tolerance:
        return False
    expected = signature(payload, secret, timestamp).split("v1=", 1)[1]
    return hmac.compare_digest(supplied, expected)

