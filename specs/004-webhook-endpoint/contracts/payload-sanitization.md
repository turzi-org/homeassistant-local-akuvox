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

### Rules (FR-013)

Applied in order:

1. **Sensitive field masking**: If a key contains any of `token`,
   `secret`, `password`, `authorization`, `auth`, `key`, `cookie`,
   or `code` (case-insensitive match), replace the value with
   `[REDACTED]`.

   **Note on `code`**: Access codes (PINs) are intentionally
   included in plain text in the event bus payload so automations
   can react to specific codes. The sanitization rule for `code`
   applies only to **log entries** and **generic event payloads
   for unrecognized types** (per FR-013). The recognized event
   payload fired on the HA event bus preserves `code` in plain
   text as a deliberate design decision.

2. **Webhook ID masking**: If `webhook_id` is provided, replace any
   value containing the full webhook ID with a masked version
   showing the first 4 and last 2 characters with `***` in between.
   If the ID is 8 or fewer characters, use `[REDACTED_ID]`.

3. **Field truncation**: If any value exceeds 1024 characters,
   truncate to 1024 and append `...[TRUNCATED]`.

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
