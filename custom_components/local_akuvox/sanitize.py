# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Payload sanitization for Akuvox webhook events (FR-013)."""

from __future__ import annotations

import re
from typing import Final

# Sensitive key patterns — contains-match (case-insensitive)
_SENSITIVE_PATTERNS: Final[tuple[str, ...]] = (
    "token",
    "secret",
    "password",
    "authorization",
    "auth",
    "key",
    "cookie",
    "code",
)

_SENSITIVE_RE: Final[re.Pattern[str]] = re.compile(
    "|".join(re.escape(p) for p in _SENSITIVE_PATTERNS),
    re.IGNORECASE,
)

# Truncation constants
_MAX_FIELD_LENGTH: Final = 1024
_TRUNCATION_SUFFIX: Final = "...[TRUNCATED]"
_TRUNCATED_BODY_LENGTH: Final = _MAX_FIELD_LENGTH - len(_TRUNCATION_SUFFIX)


def mask_webhook_id(webhook_id: str) -> str:
    """Mask a webhook ID per FR-013(b).

    Args:
        webhook_id: The full webhook ID string.

    Returns:
        Masked form showing first 4 and last 2 chars, or
        ``[REDACTED_ID]`` if 8 chars or fewer.

    """
    if len(webhook_id) <= 8:
        return "[REDACTED_ID]"
    return f"{webhook_id[:4]}***{webhook_id[-2:]}"


def sanitize_payload(
    payload: dict[str, str],
    webhook_id: str | None = None,
) -> dict[str, str]:
    """Apply FR-013 sanitization rules to a webhook payload.

    Rules applied in order:
    1. Sensitive field masking (contains-match on key)
    2. Webhook ID substring replacement in values
    3. Field value truncation at 1024 characters

    The original dict is not mutated.

    Args:
        payload: Raw query parameters as a plain dict.
        webhook_id: Optional webhook ID to mask in values.

    Returns:
        A new dict with sanitized values.

    """
    result: dict[str, str] = {}
    masked_id = mask_webhook_id(webhook_id) if webhook_id else None

    for key, value in payload.items():
        # 1. Sensitive field masking
        if _SENSITIVE_RE.search(key):
            result[key] = "[REDACTED]"
            continue

        sanitized = value

        # 2. Webhook ID substring replacement
        if webhook_id and masked_id and webhook_id in sanitized:
            sanitized = sanitized.replace(webhook_id, masked_id)

        # 3. Field truncation
        if len(sanitized) > _MAX_FIELD_LENGTH:
            sanitized = sanitized[:_TRUNCATED_BODY_LENGTH] + _TRUNCATION_SUFFIX

        result[key] = sanitized

    return result
