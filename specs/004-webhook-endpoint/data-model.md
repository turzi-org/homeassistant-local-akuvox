<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Data Model: Webhook Endpoint

**Feature**: 004-webhook-endpoint
**Date**: 2026-03-02

## Config Entry Data

### New Fields (added to existing entry data)

```python
{
    # Existing fields from spec 001...
    "host": str,
    "use_ssl": bool,
    "verify_ssl": bool,
    "auth_method": str,
    "username": str | None,
    "password": str | None,

    # New webhook fields (spec 004)
    "webhook_id": str | None,        # Random 64-char hex string
    "webhook_enabled": bool,         # Whether webhook is active
}
```

- `webhook_id`: Generated via `secrets.token_hex(32)` (256 bits of
  entropy, exceeds FR-003 requirement of 128 bits). Persisted in
  config entry so the endpoint survives restarts (FR-010).
  - `None` when webhook has never been configured (user skipped
    webhook setup during initial config flow).
  - Preserved (non-`None`) when webhook was previously enabled
    and later disabled via options flow, to allow re-enabling
    without generating a new ID.
- `webhook_enabled`: Boolean flag indicating whether the webhook
  endpoint is currently active. Controls registration/unregistration
  on integration load.

### Options Flow Additions

The options flow adds a webhook management section (FR-007):

```python
vol.Schema({
    # Existing connection fields...
    vol.Required(CONF_WEBHOOK_ENABLED, default=current_value): bool,
})
```

## Action URL Configuration Keys

### Device Config Keys (written to device)

When webhook is enabled, the integration writes these keys via
`device.set_device_config()`:

| Key (after `ACTIONURL.`) | URL Template |
| ------------------------ | ------------ |
| `Enable` | `"1"` |
| `RelayATriggered` | `{base}?event=relay_a_triggered&status=$relay1status` |
| `RelayAClosed` | `{base}?event=relay_a_closed&status=$relay1status` |
| `RelayBTriggered` | `{base}?event=relay_b_triggered&status=$relay2status` |
| `RelayBClosed` | `{base}?event=relay_b_closed&status=$relay2status` |
| `InputATriggered` | `{base}?event=input_a_triggered&status=$relay1status` |
| `InputAClosed` | `{base}?event=input_a_closed&status=$relay1status` |
| `InputBTriggered` | `{base}?event=input_b_triggered&status=$relay2status` |
| `InputBClosed` | `{base}?event=input_b_closed&status=$relay2status` |
| `ValidCodeEntered` | `{base}?event=valid_code_entered&code=$code` |
| `InvalidCodeEntered` | `{base}?event=invalid_code_entered&code=$code` |

All keys prefixed with `Config.Features.ACTIONURL.`.
`{base}` is `async_generate_url(hass, webhook_id)`.

When webhook is disabled, the integration writes:

| Config Key | Value |
| ---------- | ----- |
| `Config.Features.ACTIONURL.Enable` | `"0"` |
| All 10 action URL keys | `""` (empty string) |

## Webhook Event Data

### Event Fired on Home Assistant Bus

Event name: `akuvox_webhook` (domain-prefixed)

```python
{
    "device_id": str,           # HA device registry ID
    "config_entry_id": str,     # HA config entry ID
    "event_type": str,          # lowercase_snake_case event name
    "payload": {                # Parsed query parameters
        "event": str,           # Raw event parameter value
        "status": str | None,   # Relay status ("0"/"1")
        "device_user_id": str | None,  # Device-assigned ID
        "user_id": str | None,  # User-defined external ID
        "username": str | None, # User's display name
    },
}
```

**Security: no PIN in events.** The raw access code (`$code`)
received from the device is used ONLY for user lookup against
the coordinator's cached user data (matched on `private_pin`).
The resolved user identity fields (`device_user_id`, `user_id`,
`username`) are emitted instead. The raw PIN MUST NEVER appear
in event payloads.

For `valid_code_entered` events: the handler resolves the user
by matching the raw PIN against the coordinator's cached user
data (`private_pin`). On cache miss, the implementation MAY
perform a best-effort refresh via `device.list_users()` to
obtain fresh data and populate all three identity fields.
However, this lookup MUST NOT cause the webhook HTTP response
to exceed the SC-001 2-second delivery requirement:
implementers SHOULD bound any synchronous refresh with a short
timeout, or emit the event immediately with identity fields
set to `None` and perform the lookup asynchronously. If no
matching user is found (from cache or after refresh), the
identity fields are `None`.

For `invalid_code_entered` events: no user lookup is possible
(the code is invalid). All three identity fields are `None`.

For relay and input events: these events do not carry a code
parameter. All three identity fields are `None`.

### Event Type Mapping

| Query Parameter `event=` | Fired `event_type` | Refresh |
| ------------------------ | ------------------ | ------- |
| `relay_a_triggered` | `relay_a_triggered` | Yes |
| `relay_a_closed` | `relay_a_closed` | Yes |
| `relay_b_triggered` | `relay_b_triggered` | Yes |
| `relay_b_closed` | `relay_b_closed` | Yes |
| `input_a_triggered` | `input_a_triggered` | No |
| `input_a_closed` | `input_a_closed` | No |
| `input_b_triggered` | `input_b_triggered` | No |
| `input_b_closed` | `input_b_closed` | No |
| `valid_code_entered` | `valid_code_entered` | Yes (primary) |
| `invalid_code_entered` | `invalid_code_entered` | No |
| (unrecognized value) | `unknown_{normalized}` | No |

Unknown event type normalization:

- Convert raw value to lowercase.
- Replace characters not in `[a-z0-9_]` with `_`.
- Collapse consecutive `_` into a single `_`.
- Trim leading and trailing `_`.
- Truncate to 32 characters.
- If empty after normalization, use `event` as the value.

Final event type: `unknown_{normalized}`.

**Note on valid code events**: When a valid code is entered, the
relay-specific action URLs (`RelayATriggered`, etc.) may NOT fire
even though relays change state. `valid_code_entered` is the only
reliable signal for code-initiated relay changes and MUST always
trigger an immediate coordinator refresh to capture ALL relay states,
since a single valid code may open (or close) more than one relay
simultaneously.

### Status Value Semantics

The `status` query parameter carries the raw electrical state of the
relay: `0` = low, `1` = high. The meaning depends on the relay type
configuration (NO vs NC), using the same inversion logic as the
lock entity's `_parse_relay_state()`:

- **Normally Open (NO, type=0)**: 0=open, 1=closed
- **Normally Closed (NC, type=1)**: 0=closed, 1=open

The status value is included in the event payload as-is; the lock
entity's existing relay type logic handles interpretation.

### Coordinator Refresh Behavior

The webhook handler schedules `coordinator.async_refresh()` as a
background task (`hass.async_create_task()`) for relay events and
valid code events. This provides an *additional* faster path to
update entity state — it does **not** replace the existing
speculative (optimistic) lock state mechanism. The refresh is not
awaited inline so the HTTP response returns to the device
immediately.

**When webhooks are enabled**: Relay and valid code webhook events
trigger an immediate coordinator refresh that:

1. Fetches real device state ahead of the next 30-second poll so the
   coordinator has up-to-date data as soon as possible.
2. Does **not** itself clear the lock entity's `_optimistic_locked`
   override; that override is still cleared only when the existing
   delayed timer fires and calls `_async_finish_optimistic_unlock()`.

**When webhooks are NOT enabled**: The existing behavior is
completely unchanged — speculative state is set on unlock, held
until the delayed refresh fires after the hold delay, then cleared
via `_async_finish_optimistic_unlock()`.

The delayed refresh scheduled by `async_unlock()` always remains
active as a safety net regardless of webhook state. If a
webhook-triggered refresh arrives first, the delayed refresh still
runs the `_async_finish_optimistic_unlock()` path to clear the
optimistic override, but it typically finds that the device state
is already current thanks to the earlier webhook-triggered refresh.

## Webhook Handler Lookup

The handler needs to map a `webhook_id` back to the owning config
entry and device. This is done via a domain-level registry:

```python
# Stored in hass.data[DOMAIN]["webhook_registry"]
webhook_registry: dict[str, str] = {
    webhook_id: config_entry_id,
}
```

From `config_entry_id`, the handler retrieves the coordinator from
`hass.data[DOMAIN][config_entry_id]` and the device registry entry
for `device_id`.

### Initialization and Lifetime

`async_setup_entry` MUST initialize the shared registry if it does
not already exist:

```python
hass.data.setdefault(DOMAIN, {})
hass.data[DOMAIN].setdefault("webhook_registry", {})
```

Each entry's webhook registration adds to the shared registry:

```python
hass.data[DOMAIN]["webhook_registry"][webhook_id] = entry.entry_id
```

### Unload and Cleanup Semantics

`async_unload_entry` cleans up both the per-entry coordinator and
that entry's webhook registrations:

1. Remove the coordinator:
   `hass.data[DOMAIN].pop(entry.entry_id, None)`
2. Remove all `webhook_id` entries pointing to this
   `config_entry_id` from `webhook_registry`.
3. If `webhook_registry` is now empty, remove the
   `"webhook_registry"` key from `hass.data[DOMAIN]`.
4. If `hass.data[DOMAIN]` is empty, pop the `DOMAIN` key
   from `hass.data`.

This ensures `webhook_registry` does not keep
`hass.data[DOMAIN]` alive after the last entry is unloaded.

## Payload Sanitization

Sanitization is applied per FR-013 before logging or event
emission of webhook payload data:

| Rule | Behavior |
| ---- | -------- |
| Sensitive field keys | Replace value with `[REDACTED]` |
| Webhook identifiers | Show first 4 + last 2 chars, `***` middle |
| Field value > 1024 chars | Truncate, append `...[TRUNCATED]` |
| Binary/non-text | Log content type and size only |

Sensitive key patterns (case-insensitive): `token`, `secret`,
`password`, `authorization`, `auth`, `key`, `cookie`, `code`.

## Relationship Diagram

```text
ConfigEntry (1)
  │
  ├── AkuvoxDevice (1) ─── pylocal-akuvox client instance
  │     └── set_device_config() ─── push action URLs to device
  │
  ├── DataUpdateCoordinator (1)
  │     └── async_refresh() ─── triggered by relay/valid_code events
  │
  ├── Webhook Registration (0..1)
  │     ├── webhook_id ─── random 64-char hex
  │     ├── handler ─── parse query params → fire event
  │     └── URL ─── /api/webhook/{webhook_id}
  │
  └── LockEntity (1..N) ─── existing from spec 001
        └── state updated by coordinator refresh
```
