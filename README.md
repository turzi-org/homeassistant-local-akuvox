<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Turzi Local Akuvox — Home Assistant Integration

[![HACS][hacs-badge]][hacs-url]
[![GitHub Release][release-badge]][release-url]
[![License][license-badge]][license-url]

A [Home Assistant](https://www.home-assistant.io/) custom integration for
locally controlling [Akuvox](https://www.akuvox.com/) intercoms and access
control devices. All communication happens over your local network — no
cloud services required.

> **Fork of [tykeal/homeassistant-local-akuvox](https://github.com/tykeal/homeassistant-local-akuvox)**
> with extended entity support, model-aware configuration, and full
> event coverage.

---

## Features

- **Lock Entities** — One lock per relay. Unlock doors and gates
  directly from Home Assistant with configurable hold delay and
  autolatch behaviour.
- **Switch Entities** — Relays as simple on/off switches for gates,
  lights, or other non-lock devices (manual toggle mode).
- **Binary Sensor Entities** — Dry-contact inputs (door, window,
  motion), tamper alarms, and break-in alarms with real-time state
  updates via webhooks.
- **Event Entities** — Access events (code, card, face, QR) as proper
  HA Event entities for easy automation.
- **Model-Aware Configuration** — Auto-detects 20+ Akuvox models and
  shows only the relays and inputs your device actually has.
- **Configurable Entity Options** — Custom names, device classes, lock
  on/off toggles, autolatch, and hold delay — all from the UI.
- **Webhook Events** — Real-time notifications for relay triggers,
  input changes, access attempts, tamper alarms, break-in alarms,
  call events, and door-open timeouts.
- **User, Schedule, Contact & Group Management** — Full CRUD services
  for managing access codes, PINs, cards, schedules, contacts, and
  contact groups.
- **Local Polling** — Device state updates every 30 seconds via direct
  HTTP communication.
- **Flexible Authentication** — Supports no-auth (IP allowlist), HTTP
  Basic, and HTTP Digest authentication.
- **SSL Support** — Optional HTTPS with configurable certificate
  verification.

## Supported Models

The integration auto-detects your device model and adapts accordingly.
Fuzzy matching handles model variants (e.g., `E16V2-IP` → `E16V2`).

| Series | Models |
| ------ | ------ |
| **S** | S532, S535, S539 |
| **X** | X910, X912, X915, X915V2, X916 |
| **R** | R20, R25, R28, R28V2, R29 |
| **E** | E12, E13, E16, E16V2, E18 |
| **A** | A01, A02, A03, A05, A094, A095 |

Unknown models default to 2 relays and 2 inputs.

## Requirements

- Home Assistant 2026.2.0 or later
- An Akuvox intercom or access control device with HTTP API access
- Network connectivity between Home Assistant and the device

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant.
2. Go to **Integrations** → click the three-dot menu → **Custom
   repositories**.
3. Add `https://github.com/turzi-org/homeassistant-local-akuvox` with
   category **Integration**.
4. Search for **"Turzi Local Akuvox"** and install it.
5. Restart Home Assistant.

### Manual

1. Download the latest release from the
   [releases page][release-url].
2. Copy the `custom_components/local_akuvox` directory into your Home
   Assistant `config/custom_components/` directory.
3. Restart Home Assistant.

## Configuration

### Adding the Integration

1. Go to **Settings** → **Devices & Services** → **Add Integration**.
2. Search for **Turzi Local Akuvox**.
3. Follow the setup wizard:

| Step | Description |
| --- | --- |
| **Device Connection** | Enter the IP/hostname and whether to use SSL. |
| **SSL Options** | Choose whether to verify the SSL certificate. |
| **Authentication** | Select: None / AllowList, Basic, or Digest. |
| **Credentials** | Enter username and password (if required). |
| **Webhook Events** | Optionally enable webhook event delivery. |
| **Entity Configuration** | Configure relay/input names, lock toggles, device classes, hold delays, and autolatch. Fields are shown based on your detected model. |

### Reconfiguration

Go to **Settings** → **Devices & Services** → **Turzi Local Akuvox** →
**Configure** to update connection settings, entity configuration, or
webhook settings at any time. The options flow has two steps:

1. **Connection settings** — Host, SSL, authentication, and webhooks.
2. **Entity configuration** — Names, lock toggles, device classes,
   hold delays, and autolatch (pre-filled with current values).

### Entity Configuration Options

These options are available per relay and per input, depending on your
device model:

**Per relay:**

| Option | Description | Default |
| --- | --- | --- |
| **Name** | Custom display name for the relay | `Relay A`, `Relay B`, … |
| **Create Lock** | Whether to create a lock entity for this relay | `true` |
| **Autolatch** | Prevent auto-relock when disabled | `true` |
| **Hold Delay** | How long the relay stays triggered (seconds) | `5` |

**Per input:**

| Option | Description | Default |
| --- | --- | --- |
| **Name** | Custom display name for the input | `Input A`, `Input B`, … |
| **Device Class** | HA device class for the binary sensor | `door` |

Supported device classes: `door`, `garage_door`, `gate`, `window`,
`motion`, `opening`, `tamper`, `safety`, `none`.

## Entities

### Lock

One `lock` entity is created for each relay where **Create Lock** is
enabled. Each lock supports:

| Action | Description |
| --- | --- |
| **Unlock** | Triggers the relay for the configured hold duration. |
| **Lock** | Mode-aware: auto-close refreshes state, bistable sends command. |

**Name priority:** user config → device config → default label.
**Hold delay priority:** user config → device config → 5 seconds.

### Switch

One `switch` entity is created for **every** relay (regardless of
the lock toggle), providing simple on/off control using manual mode
(`mode=1`). Ideal for relays controlling:

- Gates and barriers
- Lights and sirens
- Any device that should stay on/off until toggled

State is updated via the coordinator's 30-second polling cycle.

### Binary Sensor

| Entity Type | Description | Updated via |
| --- | --- | --- |
| **Input (A–D)** | Dry-contact input with configurable device class | Webhook |
| **Tamper** | Tamper alarm sensor | Webhook |
| **Break-in (A–D)** | Break-in alarm per input | Webhook |

Input sensors are **disabled by default** — enable them from the entity
settings in Home Assistant.

### Event

An **Access Event** entity fires when access credentials are used:

| Event Type | Description |
| --- | --- |
| `valid_code` | A valid PIN code was entered. |
| `invalid_code` | An invalid PIN code was entered. |
| `valid_card` | A valid card was presented. |
| `invalid_card` | An invalid card was presented. |
| `valid_face` | A valid face was recognised. |
| `invalid_face` | An invalid face recognition attempt. |
| `valid_qr` | A valid QR code was scanned. |
| `invalid_qr` | An invalid QR code was scanned. |

Event data includes resolved user identity (`username`, `user_id`,
`device_user_id`) when available from the device's user cache.

## Webhook Events

When webhooks are enabled, the integration configures your Akuvox device
to send event notifications to Home Assistant. Events are fired on the
Home Assistant event bus as `local_akuvox_webhook_received`.

### Listening for Events

Use **Developer Tools** → **Events** → **Listen to events** and enter
`local_akuvox_webhook_received` to monitor incoming webhooks.

You can also use these events in automations:

```yaml
automation:
  - alias: "Notify on door unlock"
    trigger:
      - platform: event
        event_type: local_akuvox_webhook_received
        event_data:
          event_type: relay_a_triggered
    action:
      - service: notify.mobile_app
        data:
          message: "Front door was unlocked!"
```

### Event Types

| Category | Events | Variable |
| --- | --- | --- |
| Relay A–D | `relay_{a..d}_triggered` / `_closed` | `$relay1-4status` |
| Input A–D | `input_{a..d}_triggered` / `_closed` | `$input1-4status` |
| Code | `valid_code_entered` / `invalid_code_entered` | `$code` |
| Card | `valid_card_entered` / `invalid_card_entered` | `$card_sn` |
| Face | `valid_face_recognition` / `invalid_face_recognition` | `$open_type` |
| QR Code | `valid_qr_code_entered` / `invalid_qr_code_entered` | `$open_type` |
| Tamper | `tamper_alarm_triggered` | `$alarmstatus` |
| Break-in A–D | `break_in_alarm_{a..d}` | `$input1-4status` |
| Call | `make_call` / `hang_up` | `$remote` |
| Door Timeout A–B | `alarm_door_opened_timeout_{a,b}` | `$relay_id` |

Unrecognised events from the device are emitted as
`unknown_<normalized_name>` with sanitised query parameters (sensitive
fields such as `code` are redacted) as the payload.

### Event Payload

```json
{
  "device_id": "ha_device_registry_id",
  "config_entry_id": "ha_config_entry_id",
  "event_type": "relay_a_triggered",
  "payload": {
    "event": "relay_a_triggered",
    "status": "1",
    "device_user_id": "42",
    "user_id": "john.doe",
    "username": "John Doe"
  }
}
```

| Field | Description |
| --- | --- |
| `device_id` | HA device registry ID (may be null). |
| `config_entry_id` | Home Assistant config entry ID. |
| `event_type` | Normalised event type string. |
| `payload.event` | Event name from webhook query param. |
| `payload.status` | Relay/input status (null for code events). |
| `payload.device_user_id` | Device-internal user ID (code events). |
| `payload.user_id` | External user identifier (code events). |
| `payload.username` | Display name of the user (code events). |

> **Note:** User identity fields (`device_user_id`, `user_id`,
> `username`) are populated from a local cache and may be `null` on
> first use. The cache refreshes automatically.
>
> **Security:** Raw PIN codes are never included in event payloads.
> Only the resolved user identity is emitted.

## Services

All services target lock entities belonging to this integration. Call
them via **Developer Tools** → **Services** or from automations and
scripts.

### Schedule Management

| Service | Description |
| --- | --- |
| `local_akuvox.list_schedules` | Retrieve all access schedules. |
| `local_akuvox.add_schedule` | Create a new access schedule. |
| `local_akuvox.modify_schedule` | Update an existing schedule. |
| `local_akuvox.delete_schedule` | Remove a schedule. |

**Schedule types** (`schedule_type` must be a string):

- `"0"` — Date Range (specific start/end dates)
- `"1"` — Weekly (selected days of the week)
- `"2"` — Daily (every day)

### User Management

| Service | Description |
| --- | --- |
| `local_akuvox.list_users` | Retrieve all user codes. |
| `local_akuvox.add_user` | Create a user (PIN/card). |
| `local_akuvox.modify_user` | Update an existing user. |
| `local_akuvox.delete_user` | Remove a user. |
| `local_akuvox.add_user_schedule_relay` | Assign a schedule-relay pair. |
| `local_akuvox.remove_user_schedule_relay` | Remove a schedule-relay pair. |

### Contact Management

| Service | Description |
| --- | --- |
| `local_akuvox.list_contacts` | Retrieve all contacts. |
| `local_akuvox.add_contact` | Create a contact. |
| `local_akuvox.modify_contact` | Update an existing contact. |
| `local_akuvox.delete_contact` | Remove one or more contacts. |

### Group Management

| Service | Description |
| --- | --- |
| `local_akuvox.list_groups` | Retrieve all contact groups. |
| `local_akuvox.add_group` | Create a contact group. |
| `local_akuvox.modify_group` | Update a group name. |
| `local_akuvox.delete_group` | Remove a contact group. |

### Example: Add a User with PIN Access

```yaml
service: local_akuvox.add_user
target:
  entity_id: lock.local_akuvox_front_gate
data:
  name: "Jane Doe"
  schedules: "10, 20"
  lift_floor_num: "3"
  private_pin: "5678"
```

## Troubleshooting

### Cannot connect to device

- Verify the device IP address is correct and reachable from your
  Home Assistant host.
- Check that the HTTP API is enabled on the device.
- If using authentication, confirm the credentials are correct.
- If using SSL, try disabling certificate verification to rule out
  certificate issues.
- Check **Settings → System → Logs** for detailed error messages
  (connection errors are logged at WARNING level).

### Webhook events not received

- Ensure your Home Assistant instance is accessible from the device's
  network.
- Check that webhooks are enabled in the integration options.
- Verify the device's action URL configuration points to the correct
  Home Assistant webhook URL.
- Use HTTPS/TLS for webhook URLs. `valid_code_entered` webhooks
  include the entered PIN in the query string; using HTTP transmits
  it in plaintext. Only use HTTP on a trusted network for testing.

### Lock entity shows unknown state

- The device may not have responded to the initial status poll. Wait
  for the next polling interval (30 seconds).
- Check Home Assistant logs for connection errors.

### Cloud-provisioned users or schedules

Users and schedules provisioned via Akuvox cloud services cannot be
modified or deleted through this integration. The integration will
return a clear error message when this is attempted.

## Documentation

Full documentation is available in the
[Wiki](https://github.com/turzi-org/homeassistant-local-akuvox/wiki):

- [Installation](https://github.com/turzi-org/homeassistant-local-akuvox/wiki/Installation)
- [Device Setup](https://github.com/turzi-org/homeassistant-local-akuvox/wiki/Device-Setup)
- [Configuration](https://github.com/turzi-org/homeassistant-local-akuvox/wiki/Configuration)
- [Webhook Events](https://github.com/turzi-org/homeassistant-local-akuvox/wiki/Webhook-Events)
- [Services](https://github.com/turzi-org/homeassistant-local-akuvox/wiki/Services)
- [Troubleshooting](https://github.com/turzi-org/homeassistant-local-akuvox/wiki/Troubleshooting)

## Credits

This is a fork of
[tykeal/homeassistant-local-akuvox](https://github.com/tykeal/homeassistant-local-akuvox)
by Andrew Grimberg. Extended with switch, binary sensor, and event
entity platforms, model-aware configuration, and full event coverage
by [Turzi](https://github.com/turzi-org).

## License

This project is licensed under the Apache License 2.0. See the
[LICENSE](LICENSE) file for details. This project follows the
[REUSE specification](https://reuse.software/) for license compliance.

[hacs-badge]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg
[hacs-url]: https://hacs.xyz/
[release-badge]: https://img.shields.io/github/v/release/turzi-org/homeassistant-local-akuvox
[release-url]: https://github.com/turzi-org/homeassistant-local-akuvox/releases
[license-badge]: https://img.shields.io/github/license/turzi-org/homeassistant-local-akuvox
[license-url]: https://github.com/turzi-org/homeassistant-local-akuvox/blob/main/LICENSE
