# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Tests for the Akuvox payload sanitization module."""

from __future__ import annotations

import pytest

from custom_components.local_akuvox.sanitize import mask_webhook_id, sanitize_payload

# ── mask_webhook_id tests ────────────────────────────────────


def test_mask_webhook_id_long() -> None:
    """Test masking a 64-char webhook ID shows first 4 and last 2."""
    wid = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a190"
    result = mask_webhook_id(wid)
    assert result == "a1b2***90"


def test_mask_webhook_id_short() -> None:
    """Test masking an 8-char or shorter ID returns REDACTED_ID."""
    assert mask_webhook_id("short") == "[REDACTED_ID]"
    assert mask_webhook_id("12345678") == "[REDACTED_ID]"


def test_mask_webhook_id_nine_chars() -> None:
    """Test masking a 9-char ID shows first 4 and last 2."""
    result = mask_webhook_id("123456789")
    assert result == "1234***89"


# ── sanitize_payload: sensitive field masking ────────────────


@pytest.mark.parametrize(
    "key",
    [
        "token",
        "secret",
        "password",
        "authorization",
        "auth",
        "key",
        "cookie",
        "code",
        # Substring matches
        "my_token_value",
        "reauth",
        "monkey",
        "api_key_id",
        "access_code",
    ],
)
def test_sensitive_key_masked(key: str) -> None:
    """Test keys containing sensitive patterns are masked."""
    payload = {key: "sensitive_value"}
    result = sanitize_payload(payload)
    assert result[key] == "[REDACTED]"


def test_non_sensitive_key_preserved() -> None:
    """Test keys without sensitive patterns are preserved."""
    payload = {"event": "relay_a_triggered", "status": "1"}
    result = sanitize_payload(payload)
    assert result["event"] == "relay_a_triggered"
    assert result["status"] == "1"


def test_sensitive_matching_case_insensitive() -> None:
    """Test sensitive pattern matching is case-insensitive."""
    payload = {"Authorization": "Bearer xyz", "API_KEY": "abc"}
    result = sanitize_payload(payload)
    assert result["Authorization"] == "[REDACTED]"
    assert result["API_KEY"] == "[REDACTED]"


# ── sanitize_payload: webhook ID masking ─────────────────────


def test_webhook_id_substring_replaced() -> None:
    """Test webhook ID is replaced in values via substring match."""
    wid = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a190"
    payload = {
        "url": f"http://ha.local/api/webhook/{wid}?event=test",
    }
    result = sanitize_payload(payload, webhook_id=wid)
    assert wid not in result["url"]
    assert "a1b2***90" in result["url"]
    # URL structure preserved
    assert "http://ha.local/api/webhook/" in result["url"]
    assert "?event=test" in result["url"]


def test_webhook_id_short_replaced() -> None:
    """Test short webhook ID replaced with REDACTED_ID."""
    wid = "abc"
    payload = {"url": f"http://ha.local/api/webhook/{wid}"}
    result = sanitize_payload(payload, webhook_id=wid)
    assert "[REDACTED_ID]" in result["url"]
    assert wid not in result["url"]


def test_webhook_id_none_no_masking() -> None:
    """Test no masking when webhook_id is None."""
    payload = {"url": "http://ha.local/api/webhook/abc123"}
    result = sanitize_payload(payload)
    assert result["url"] == payload["url"]


# ── sanitize_payload: field truncation ───────────────────────


def test_field_truncation_at_1024() -> None:
    """Test long values are truncated to 1024 chars."""
    long_value = "x" * 2000
    payload = {"data": long_value}
    result = sanitize_payload(payload)
    assert len(result["data"]) == 1024
    assert result["data"].endswith("...[TRUNCATED]")


def test_field_at_1024_not_truncated() -> None:
    """Test value exactly at 1024 is not truncated."""
    exact = "x" * 1024
    payload = {"data": exact}
    result = sanitize_payload(payload)
    assert result["data"] == exact
    assert len(result["data"]) == 1024


# ── sanitize_payload: original not mutated ───────────────────


def test_original_not_mutated() -> None:
    """Test sanitize_payload returns a new dict without mutating."""
    payload = {"code": "1234", "event": "test"}
    original = dict(payload)
    result = sanitize_payload(payload)
    assert payload == original
    assert result is not payload
    assert result["code"] == "[REDACTED]"
    assert payload["code"] == "1234"


# ── sanitize_payload: combined rules ─────────────────────────


def test_sanitization_order() -> None:
    """Test rules apply in order: sensitive, webhook ID, truncation."""
    wid = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a190"
    payload = {
        "code": "1234",
        "url": f"http://ha.local/api/webhook/{wid}",
        "data": "x" * 2000,
        "event": "relay_a_triggered",
    }
    result = sanitize_payload(payload, webhook_id=wid)
    assert result["code"] == "[REDACTED]"
    assert wid not in result["url"]
    assert len(result["data"]) == 1024
    assert result["event"] == "relay_a_triggered"
