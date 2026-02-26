<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Data Model: Device Config Discovery

## Entities

### RelayConfig

Per-relay configuration extracted from device config.

| Field | Type | Description | Default |
| --- | --- | --- | --- |
| name | str | Display name from config | `""` (→ "Relay {L}") |
| hold_delay | int | Unlock duration in seconds | 5 |
| relay_type | int | 0=NO, 1=NC | 0 |
| relay_mode | int | 0=Auto-close, 1=Manual | 0 |

**Validation rules**:

- `name`: Any non-empty string; empty/missing triggers fallback
- `hold_delay`: Positive integer ≥1; invalid values fall back to 5
- `relay_type`: Must be 0 or 1; invalid values fall back to 0
- `relay_mode`: Must be 0 or 1; invalid values fall back to 0

**Implementation**: Python dataclass in coordinator.py (or a new module if
complexity grows). Created by parsing `DeviceConfig` keys per relay letter.

### AkuvoxCoordinatorData (updated)

Extended coordinator data to include device config information.

| Field | Type | Description |
| --- | --- | --- |
| device_info | DeviceInfo | Library device info (model, MAC, fw) |
| relay_status | dict[str, Any] | Current relay states from polling |
| device_name | str | Device name from config or fallback |
| relay_configs | dict[str, RelayConfig] | Per-relay config keyed by letter |

**State transitions**:

- On first successful poll: `relay_configs` populated from device config
- On unavailable→available: `relay_configs` refreshed from device config
- On config fetch failure: `relay_configs` retains previous values (or
  defaults if never fetched)

## Key Mappings

### Relay Letter → Config Key Mapping

Given a relay letter suffix (e.g., "A"):

| Property | Config Key Pattern | Example |
| --- | --- | --- |
| Name | `...RELAY.Name{L}` | `...RELAY.NameA` |
| Hold Delay | `...RELAY.HoldDelay{L}` | `...RELAY.HoldDelayA` |
| Type | `...RELAY.Relay{L}Type` | `...RELAY.RelayAType` |
| Mode | `...RELAY.Relay{L}Mode` | `...RELAY.RelayAMode` |

All keys are prefixed with `Config.DoorSetting`.

### Device Location Key

`Config.DoorSetting.DEVICENODE.Location` → device name

## Relationships

```text
AkuvoxDataUpdateCoordinator
  ├── device: AkuvoxDevice (library client)
  ├── data: AkuvoxCoordinatorData
  │     ├── device_info: DeviceInfo
  │     ├── relay_status: dict[str, Any]
  │     ├── device_name: str
  │     └── relay_configs: dict[str, RelayConfig]
  └── _was_unavailable: bool (tracks reconnection)

AkuvoxLockEntity
  ├── reads relay_configs[letter] for hold_delay, relay_type, relay_mode
  ├── uses relay_type for state interpretation (NO/NC inversion)
  ├── passes hold_delay to trigger_relay(delay=...)
  └── passes relay_type as trigger_relay(level=...)

AkuvoxEntity (base)
  └── reads device_name for DeviceInfo.name
```
