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
)
```

**Postconditions**:

- Webhook ID added to `hass.data[DOMAIN]["webhook_registry"]`
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

1. Look up `config_entry_id` from webhook registry
2. Parse query parameters from `request.query`
3. Extract `event` parameter → determines `event_type`
4. Extract additional parameters (`status`, `code`)
5. Validate event type against known set
6. Fire Home Assistant event

### Response Codes

| Condition | HTTP Status | Body |
| --------- | ----------- | ---- |
| Valid known event | 200 OK | Empty |
| Valid unknown event (generic) | 200 OK | Empty |
| Missing `event` parameter | 400 Bad Request | `"Bad Request"` |
| Webhook ID not in registry | N/A (HA returns 200 default) | N/A |

Note: HA's webhook infrastructure handles the routing. If the
webhook ID is not registered, HA itself returns a 200 with
`"Webhook not registered."`. The handler is only called for
registered IDs, so an HTTP 404 per FR-004 is achieved by
unregistering the webhook (HA returns its default response for
unknown webhook IDs).

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
            "status": status_value,  # or None
            "code": code_value,      # or None
        },
    },
)
```

### Coordinator Refresh

When `event_type` is a relay event (`relay_a_triggered`,
`relay_a_closed`, `relay_b_triggered`, `relay_b_closed`) or
`valid_code_entered`:

```python
coordinator = hass.data[DOMAIN][config_entry_id]
await coordinator.async_request_refresh()
```

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
