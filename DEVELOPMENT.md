# Turzi Local Akuvox — Development Context

> **Last updated:** 2026-05-08
> **Repository:** `turzi-org/homeassistant-local-akuvox`
> **Forked from:** `tykeal/homeassistant-local-akuvox`

---

## Overview

This is a **forked and extended** Home Assistant custom integration for Akuvox access control devices. The upstream integration (`tykeal/homeassistant-local-akuvox`) provides the core library (`pylocal-akuvox`), coordinator/polling infrastructure, lock entities, and service calls. Our fork extends it with:

- **Switch entities** for manual relay control
- **Binary sensor entities** for dry-contact inputs, tamper alarms, and break-in alarms
- **Event entities** for access events (card, code, face, QR)
- **Full model coverage** across 20+ Akuvox hardware models
- **Configurable entity options** (custom names, device classes, lock toggles, autolatch, hold delay)
- **Improved logging** (connection errors at WARNING level)
- **Rebranding** to "Turzi Local Akuvox"

---

## Architecture

### Directory Structure

```
homeassistant-local-akuvox/
├── custom_components/local_akuvox/
│   ├── __init__.py          # Integration setup, platform forwarding
│   ├── config_flow.py       # Setup wizard + options flow (multi-step)
│   ├── const.py             # All constants, model registry, event types
│   ├── coordinator.py       # DataUpdateCoordinator (polling)
│   ├── entity.py            # Base AkuvoxEntity class
│   ├── lock.py              # Lock platform (relay-based, with services)
│   ├── switch.py            # Switch platform (relay manual control)
│   ├── binary_sensor.py     # Binary sensors (inputs, tamper, break-in)
│   ├── event.py             # Event platform (access events)
│   ├── webhook.py           # Webhook registration + action URL builder
│   ├── strings.json         # Source translation strings
│   ├── translations/en.json # Runtime translations (MUST match strings.json)
│   ├── manifest.json        # Integration metadata
│   └── services.yaml        # Service definitions
├── hacs.json                # HACS configuration
└── README.md                # User documentation
```

### Key Design Decisions

#### 1. Fork-and-Extend Strategy
We keep the upstream `pylocal-akuvox` library and coordinator intact. Our additions are in separate platform files (`switch.py`, `binary_sensor.py`, `event.py`) and extensions to existing files (`const.py`, `webhook.py`, `config_flow.py`).

#### 2. Entity Configuration via Options Flow
Entity customization (names, lock toggles, device classes, hold delays) is stored in `entry.options["entity_config"]` as a nested dict:

```json
{
  "entity_config": {
    "relay_a": {"name": "Front Door", "create_lock": true, "autolatch": true, "hold_delay": 5},
    "relay_b": {"name": "Gate", "create_lock": false, "autolatch": false, "hold_delay": 10},
    "input_a": {"name": "Door Sensor", "device_class": "door"},
    "input_b": {"name": "Motion", "device_class": "motion"}
  }
}
```

Each platform reads from this config at setup time. The options flow has two steps:
1. **Connection settings** (host, SSL, auth, webhooks)
2. **Entity configuration** (model-aware relay/input fields)

The entity configuration step also appears during **initial setup** (config flow), not just in the options flow.

#### 3. Model-Aware Configuration
The device model is auto-detected via `device.get_info().model` during setup and stored in `entry.data["device_model"]`. A `MODEL_CAPABILITIES` registry in `const.py` maps 20+ models to their relay/input counts. The options flow only shows fields for ports the model actually has.

Fuzzy matching handles model variants (e.g., `E16V2-IP` → `E16V2`).

#### 4. Webhook Event Architecture
Webhooks use Akuvox "Action URLs" — the device is configured to HTTP GET a HA webhook URL when events occur. The URL templates in `webhook.py` embed device variables:

```
?event=input_a_triggered&status=$input1status
?event=valid_code_entered&code=$code
?event=tamper_alarm_triggered&status=$alarmstatus
```

**Critical:** Input events use `$input1status`/`$input2status` (NOT `$relay1status`). This was a bug fix.

#### 5. Translations
- `strings.json` is the **source of truth** for all UI strings
- `translations/en.json` is the **runtime file** that HA actually reads
- **These MUST be kept in sync** — HA does NOT auto-generate `en.json` for custom integrations
- After updating either, a **full HA restart + browser hard refresh** (Cmd+Shift+R) is required

---

## Model Coverage

All events from the official Akuvox "Action URLs Supported by Different Models" spreadsheet are supported:

| Category | Events | Variable |
|---|---|---|
| Relay A-D | triggered / closed | `$relay1-4status` |
| Input A-D | triggered / closed | `$input1-4status` |
| Code | valid / invalid | `$code` |
| Card | valid / invalid | `$card_sn` |
| Face | valid / invalid | `$open_type` |
| QR Code | valid / invalid | `$open_type` |
| Tamper | alarm triggered | `$alarmstatus` |
| Break-in A-D | alarm | `$input1-4status` |
| Call | make / hang up | `$remote` |
| Door Timeout A-B | alarm | `$relay_id` |

### Model Capabilities Registry (const.py)

| Model | Relays | Inputs | Notes |
|---|---|---|---|
| E16V2 | 1 | 1 | Single relay, single input |
| E18 | 2 | 3 | + tamper, face |
| A02 | 1 | 2 | + tamper, door timeout |
| S535 | 1 | 2 | + face, QR |
| S532 | 2 | 4 | 4 inputs, no face |
| X916 | 4 | 4 | Full model |
| A095 | 4 | 4 | Uses "Door1-4" naming |
| ... | ... | ... | See `MODEL_CAPABILITIES` in const.py |

---

## Platform Details

### Lock (`lock.py`)
- **Upstream code** — we only modified `async_setup_entry` and `__init__`
- Reads `entity_config` for: `create_lock` (skip if false), `custom_name`, `hold_delay` override, `autolatch`
- Name priority: user config → device config → default label
- Hold delay priority: user config → device config → `DEFAULT_HOLD_DELAY_SECONDS` (5)
- Supports bistable (mode=1) and auto-close (mode=0) relay modes
- Contains all service call implementations (schedules, users, contacts, groups)

### Switch (`switch.py`)
- Creates a switch for every relay (always, unlike locks which can be toggled off)
- Uses manual mode (mode=1) for on/off control
- Reads custom names from `entity_config`
- Name format: `"{custom_name} Switch"` or `"Relay {letter} Switch"`

### Binary Sensor (`binary_sensor.py`)
- **AkuvoxInputSensor** — one per input (A-D), disabled by default
  - Configurable `device_class` from options (door, motion, window, tamper, etc.)
  - Custom name from `entity_config`
  - State updated via webhook events
- **AkuvoxTamperSensor** — single tamper alarm sensor
- **AkuvoxBreakInSensor** — one per input (A-D), break-in alarm

### Event (`event.py`)
- Single `AkuvoxAccessEvent` entity per device
- Fires events for: valid/invalid code, card, face, QR
- Resolves user identity from webhook payload when available

---

## Config Flow Steps

### Initial Setup (config_flow.py → AkuvoxConfigFlow)
1. **user** — Host + SSL toggle
2. **ssl** — Verify SSL certificate
3. **auth** — Auth method (none/basic/digest)
4. **credentials** — Username + password (if auth enabled)
5. **webhook** — Enable webhook event delivery
6. **entities** — Model-aware entity configuration (names, locks, device classes)

### Options Flow (config_flow.py → AkuvoxOptionsFlow)
1. **init** — All connection settings on one page
2. **entities** — Same entity configuration as initial setup, pre-filled with current values

---

## Important Files to Understand

| File | What to know |
|---|---|
| `const.py` | All constants, `ACTIONURL_KEYS`, `KNOWN_EVENT_TYPES`, `MODEL_CAPABILITIES`, `get_model_capabilities()` |
| `webhook.py` | `_URL_TEMPLATES` maps event names to webhook URL query params with correct device variables |
| `config_flow.py` | Two flow classes: `AkuvoxConfigFlow` (initial) and `AkuvoxOptionsFlow` (reconfigure) |
| `coordinator.py` | Upstream — polls device for relay status, relay configs, device info |
| `entity.py` | Base class providing coordinator + device access |

---

## HACS Configuration

```json
// hacs.json
{
  "name": "Turzi Local Akuvox",
  "render_readme": true
}
```

- No `zip_release` — HACS downloads the repo source directly
- Install via: HACS → Custom Repositories → `https://github.com/turzi-org/homeassistant-local-akuvox`

---

## Pending Work / Future Considerations

### High Priority
- [ ] **Logo/icon** — Generate or place `icon.png` and `icon@2x.png` in the integration directory
- [ ] **Autolatch implementation** — The `config_autolatch` flag is stored but not yet wired into the lock entity's unlock logic to prevent auto-relock when disabled
- [ ] **Existing installs missing model** — Devices added before the model storage change won't have `device_model` in entry.data. Consider adding a migration in `__init__.py` that re-fetches model on first load

### Medium Priority
- [ ] **A095 "Door" naming** — The A095 uses "Door1-4" instead of "Relay A-D" in the spreadsheet. May need special handling
- [ ] **Suspicious Object Movement Detection** — E13/E12 support this event, not yet handled in webhook templates
- [ ] **POST method support** — Some models (S539, S535, X916, etc.) support POST action URLs. Currently only GET is implemented
- [ ] **Door open timeout events** — The `$relay_id` and `$location` variables in A01/A02 may need different handling

### Low Priority
- [ ] **CI/CD** — Port upstream build/test workflows
- [ ] **Upstream sync** — Periodically pull changes from `tykeal/homeassistant-local-akuvox`
- [ ] **HA Brands submission** — Submit logo to `home-assistant/brands` repo for global display
- [ ] **Config flow validation** — Validate that entity config changes trigger platform reload

---

## Reference: Spreadsheet Source

The event coverage is based on:
`assets/Action URLs Supported by Different Models.xlsx`

This spreadsheet contains per-model event lists with URL formats and variables. It was the authoritative source for:
- `ACTIONURL_KEYS` in `const.py`
- `_URL_TEMPLATES` in `webhook.py`
- `MODEL_CAPABILITIES` in `const.py`
- `KNOWN_EVENT_TYPES` in `const.py`

---

## Quick Commands

```bash
# Push to fork
git push fork main

# Check git status
git status --short

# View recent commits
git log --oneline -10
```
