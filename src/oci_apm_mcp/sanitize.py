"""Bounded redaction for query rows and explicitly requested span attributes."""

from __future__ import annotations

from datetime import datetime
import re
from typing import Any, Mapping


MAX_VALUE_LENGTH = 512
MAX_ATTRIBUTE_COUNT = 50
REDACTED = "[REDACTED]"
_SENSITIVE_PARTS = (
    "authorization",
    "accesstoken",
    "refreshtoken",
    "password",
    "secret",
    "cookie",
    "header",
    "requestbody",
    "responsebody",
    "sqltext",
    "stacktrace",
    "username",
    "userid",
    "sessionid",
    "queryparam",
    "url",
)


def _normalized_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def is_sensitive_key(key: str) -> bool:
    """Classify fields conservatively using normalized key fragments."""
    normalized = _normalized_key(key)
    return any(part in normalized for part in _SENSITIVE_PARTS)


def safe_scalar(value: Any) -> str | int | float | bool | None:
    """Convert one value to a JSON-safe scalar with bounded string size."""
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    rendered = str(value)
    if len(rendered) > MAX_VALUE_LENGTH:
        return f"{rendered[:MAX_VALUE_LENGTH]}...[TRUNCATED]"
    return rendered


def sanitize_mapping(
    values: Mapping[str, Any], *, maximum_items: int = MAX_ATTRIBUTE_COUNT
) -> tuple[dict[str, Any], int, int]:
    """Redact sensitive keys and exclude nested payloads from one mapping."""
    safe: dict[str, Any] = {}
    redacted = 0
    truncated = 0
    for index, (raw_key, value) in enumerate(values.items()):
        if index >= maximum_items:
            truncated += 1
            continue
        key = str(raw_key)[:128]
        if is_sensitive_key(key):
            safe[key] = REDACTED
            redacted += 1
        elif isinstance(value, (dict, list, tuple, set)):
            safe[key] = "[COMPLEX_VALUE_OMITTED]"
            truncated += 1
        else:
            safe[key] = safe_scalar(value)
    return safe, redacted, truncated


def sanitize_tags(tags: list[Any] | None) -> tuple[dict[str, Any], int, int]:
    """Normalize OCI Tag objects without returning logs or tag metadata."""
    values: dict[str, Any] = {}
    for tag in tags or []:
        name = getattr(tag, "tag_name", None)
        if name:
            values[str(name)] = getattr(tag, "tag_value", None)
    return sanitize_mapping(values)
