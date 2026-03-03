<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Contracts: Webhook Handler

**Feature**: 004-webhook-endpoint
**Component**: `webhook.py` (new module)

## Webhook Registration

### Register Webhook

Called during `async_setup_entry()` when `webhook_enabled` is True,
or when the user enables webhook in config/options flow.

```python
from homeassistant.components.webhook import async_register

async_register(
    hass,
    domain=DOMAIN,                          # "akuvox"
    name=f"Akuvox {device_name}",           # Human-readable
    webhook_id=entry.data["webhook_id"],    # 64-char hex
    handler=async_handle_webhook,           # Callback
    allowed_methods=["GET"],                # Akuvox sends GET
)
```

**Postconditions**:

- Webhook ID added to `hass.data[DOMAIN]["webhook_registry"]`
  **only after** `async_register()` succeeds (avoids stale
  registry entries if HA registration fails)
- Endpoint `/api/webhook/{webhook_id}` accepts GET requests

### Unregister Webhook

Called during `async_unload_entry()`, when user disables webhook in
options flow, or when integration entry is removed.

```python
from homeassistant.components.webhook import async_unregister

async_unregister(hass, webhook_id)
```

**Postconditions**:

- Webhook ID removed from `hass.data[DOMAIN]["webhook_registry"]`
- Endpoint returns 200 with `"Webhook not registered."` (HA default)

## Webhook Handler

### Signature

```python
async def async_handle_webhook(
    hass: HomeAssistant,
    webhook_id: str,
    request: web.Request,
) -> web.Response | None:
```

### Request Processing

1. Look up `config_entry_id` from webhook registry.
   If the `webhook_id` is not found in the integration's
   `webhook_registry` (e.g., race during startup or
   registration ordering bug), log a warning and return
   200 OK with an empty body — do not proceed further.
2. Parse query parameters from `request.query`
3. Extract `event` parameter → determines `event_type`
4. Extract additional parameters (`status`, `code`)
5. Validate event type against known set
6. **User lookup** (valid code events only): If `code` parameter
   is present and event is `valid_code_entered`, look up the PIN
   against the coordinator's cached user data (match on
   `private_pin`). On cache miss, fall back to
   `device.list_users()` to fetch fresh data, but this fallback
   MUST NOT delay the webhook HTTP response beyond 2 seconds
   (SC-001). Implementations SHOULD apply a short timeout on
   the device call or emit the event immediately with `None`
   identity fields and perform the lookup asynchronously.
   Resolve `device_user_id`, `user_id`, and `username`. If
   still no match after fallback, set all three to `None`.
7. Fire Home Assistant event (with user identity, never raw PIN)

### Response Codes

| Condition | HTTP Status | Body |
| --------- | ----------- | ---- |
| Valid known event | 200 OK | Empty |
| Valid unknown event (generic) | 200 OK | Empty |
| Missing `event` parameter | 400 Bad Request | `"Bad Request"` |
| Webhook ID not in registry | N/A (HA returns 200 default) | N/A |
| Registry hit but coordinator missing | 200 OK | Empty |

> **Note**: For unknown event types, a warning-level message
> identifying the unknown type MUST also be logged per FR-013.

Note: HA's webhook infrastructure handles the routing. If the
webhook ID is not registered, HA itself returns a 200 with
`"Webhook not registered."`. FR-004 in `spec.md` has been
updated to reflect this (HTTP 200 instead of 404). The
security goal (no diagnostic details, no event fired) is met
since the response body is generic and the handler is never
invoked.

If the `webhook_id` is found in the registry but the
corresponding coordinator is no longer in
`hass.data[DOMAIN][config_entry_id]` (e.g., due to a race
during unload), the handler MUST catch the `KeyError`, log a
warning, and return HTTP 200 with an empty body rather than
raising an unhandled exception.

### Event Firing

```python
hass.bus.async_fire(
    f"{DOMAIN}_webhook",
    {
        "device_id": device_id,
        "config_entry_id": config_entry_id,
        "event_type": event_type,
        "payload": {
            "event": raw_event,
            "status": status_value,        # or None
            "device_user_id": user.id,     # or None
            "user_id": user.user_id,       # or None
            "username": user.name,         # or None
        },
    },
)
```

**Security**: The raw PIN (`$code` query parameter) is used ONLY
for the user lookup and MUST NOT appear in the event payload or
be stored anywhere. Log entries that include the raw query string
MUST apply FR-013 sanitization (the `code` key is in the
sensitive pattern list).

### Coordinator Refresh

When `event_type` is a relay event (`relay_a_triggered`,
`relay_a_closed`, `relay_b_triggered`, `relay_b_closed`) or
`valid_code_entered`:

```python
coordinator = hass.data[DOMAIN][config_entry_id]
hass.async_create_task(coordinator.async_refresh())
```

The refresh is scheduled as a background task so the HTTP response
is returned to the device immediately, avoiding slow-device
timeouts. This is consistent with the existing
`_schedule_delayed_refresh()` pattern in `lock.py`.

Input events (`input_a_triggered`, `input_a_closed`,
`input_b_triggered`, `input_b_closed`) do NOT trigger a refresh.
Inputs report external sensor state, not relay-controlled lock
state, so a coordinator refresh would not yield new lock data.
Invalid code events also do not trigger a refresh.

This is an *additional* faster path to update entity state. It does
**not** replace the existing speculative (optimistic) lock state
mechanism, which MUST remain intact for devices without webhooks
enabled. The delayed refresh scheduled by `async_unlock()` always
stays active as a safety net.

**Important**: When a valid code is entered on the device, the
relay-specific action URLs (`RelayATriggered`, etc.) may NOT fire
even though relays change state. `valid_code_entered` is the only
reliable signal for code-initiated relay changes. The refresh on
`valid_code_entered` is therefore critical — it is the primary
path for updating lock entity state after code entry.

Input events and invalid code events do not trigger a refresh
as they do not affect relay state.
