import base64
import hashlib
import hmac
import json
from typing import Any

SECRET_KEY = "change-me-before-production"


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    return hmac.compare_digest(hash_password(password), password_hash)


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def create_token(payload: dict[str, Any]) -> str:
    body = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(
        SECRET_KEY.encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return f"{body}.{_b64encode(signature)}"


def verify_token(token: str) -> dict[str, Any] | None:
    try:
        body, signature = token.split(".", maxsplit=1)
    except ValueError:
        return None

    expected_signature = hmac.new(
        SECRET_KEY.encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256,
    ).digest()

    try:
        actual_signature = _b64decode(signature)
    except ValueError:
        return None

    if not hmac.compare_digest(expected_signature, actual_signature):
        return None

    try:
        return json.loads(_b64decode(body))
    except (json.JSONDecodeError, ValueError):
        return None
