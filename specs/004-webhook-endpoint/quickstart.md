<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Quickstart: Webhook Endpoint

**Feature**: 004-webhook-endpoint
**Date**: 2026-03-02

## Prerequisites

- Python ≥3.13.2
- uv package manager
- Existing local-akuvox integration (specs 001-003 implemented)
- Home Assistant development environment (or
  pytest-homeassistant-custom-component for testing)

## New Files

```text
custom_components/akuvox/
├── webhook.py           # Webhook handler + registration helpers
├── sanitize.py          # FR-013 payload sanitization
├── const.py             # + new webhook constants
├── config_flow.py       # + webhook setup step + options toggle
├── __init__.py          # + webhook lifecycle in setup/unload
├── strings.json         # + webhook UI strings
└── translations/
    └── en.json          # + webhook translations

tests/
├── test_webhook.py      # Webhook handler tests
├── test_sanitize.py     # Sanitization rule tests
├── test_config_flow.py  # + webhook config flow tests
└── test_init.py         # + webhook setup/teardown tests
```

## Running Tests

```bash
uv run pytest tests/ -x -q
```

## Running Linters

```bash
uv run ruff check custom_components/ tests/
uv run ruff format --check custom_components/ tests/
uv run mypy custom_components/
```

## Key Implementation Order

1. `const.py` — Add webhook-related constants (config keys, event
   name, action URL key mapping, known event types)
2. `sanitize.py` — Payload sanitization (FR-013); standalone module
   with no HA dependencies for easy unit testing
3. `webhook.py` — Webhook handler, registration/unregistration
   helpers, action URL construction
4. `__init__.py` — Wire webhook lifecycle into setup_entry and
   unload_entry
5. `config_flow.py` — Add webhook step to config flow and webhook
   toggle to options flow
6. `strings.json` + `translations/en.json` — Webhook UI strings

## Config Flow User Experience (Updated)

1. User adds "Akuvox" integration
2. Enter device IP, toggle "Use SSL"
3. If SSL → "Verify SSL" checkbox
4. Select auth mode (None/AllowList/Basic/Digest)
5. If Basic or Digest → enter username/password
6. Integration tests connection
7. **NEW** → "Enable webhook events?" toggle
8. If enabled → integration pushes action URLs to device
9. If push fails → error with retry/skip option
10. Integration creates config entry with lock entities + webhook

## Webhook Event Testing

Simulate a webhook delivery locally:

```bash
# Relay A triggered (status=1 means open)
curl "http://localhost:8123/api/webhook/{webhook_id}\
?event=relay_a_triggered&status=1"

# Valid code entered (handler resolves user identity from PIN)
curl "http://localhost:8123/api/webhook/{webhook_id}\
?event=valid_code_entered&code=1234"
```

Listen for events in HA Developer Tools → Events →
`akuvox_webhook`. Code events emit `device_user_id`, `user_id`,
and `username` (resolved from PIN lookup) — the raw PIN is never
included in the event payload.
