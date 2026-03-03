<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Contracts: Payload Sanitization

**Feature**: 004-webhook-endpoint
**Component**: `sanitize.py` (new module)

## Sanitization Function

```python
def sanitize_payload(
    payload: dict[str, str],
    webhook_id: str | None = None,
) -> dict[str, str]:
    """Apply FR-013 Payload Sanitization Rules."""
```

> **Note**: `aiohttp.web.Request.query` returns a
> `MultiDictProxy[str]` which can have duplicate keys. The
> webhook handler MUST convert it to a plain `dict[str, str]`
> using `dict(request.query)` (last-value-wins) before passing
> it to this function. Duplicate keys in query strings are not
> expected from Akuvox devices and are safely collapsed.

### Rules (FR-013)

Applied in order:

1. **Sensitive field masking**: If a key contains any of `token`,
   `secret`, `password`, `authorization`, `auth`, `key`, `cookie`,
   or `code` (case-insensitive match), replace the value with
   `[REDACTED]`.

   **Note on `code`**: The raw PIN (`$code` query parameter) is
   NEVER included in HA event payloads. The webhook handler uses
   the raw code only for user lookup (matching against
   `private_pin` in coordinator cache, with device fallback).
   Event payloads contain resolved user identity fields
   (`device_user_id`, `user_id`, `username`) instead. The
   sanitization rule for `code` applies to **log entries** and
   **raw query parameter dumps** to ensure the PIN is redacted
   wherever it might appear in diagnostic output.

2. **Webhook ID masking**: If `webhook_id` is provided, replace any
   value containing the full webhook ID with a masked version
   showing the first 4 and last 2 characters with `***` in between.
   If the ID is 8 or fewer characters, use `[REDACTED_ID]`.

3. **Field truncation**: If any value exceeds 1024 characters,
   truncate to 1010 characters and append `...[TRUNCATED]`
   (total capped at 1024 characters).

4. **Binary exclusion**: Not applicable for query parameter payloads
   (always text). Included for completeness if POST payloads are
   added in future.

### Return Value

A new dict with sanitized values. The original dict is not mutated.

## Webhook ID Masking Helper

```python
def mask_webhook_id(webhook_id: str) -> str:
    """Mask a webhook ID per FR-013(b)."""
```

- Input: `"a1b2c3d4e5f6...7890"` (64 chars)
- Output: `"a1b2***90"`
- Input: `"short"` (≤8 chars)
- Output: `[REDACTED_ID]`

Used in log messages wherever the webhook ID appears.
