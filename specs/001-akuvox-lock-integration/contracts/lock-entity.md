<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Contracts: Lock Entity

**Feature**: 001-akuvox-lock-integration
**Component**: `lock.py`

## Lock Entity Contract

### Base Class: `AkuvoxEntity` (in `entity.py`)

Inherits from `CoordinatorEntity`. Provides shared `device_info`
property that converts the library's `DeviceInfo` to HA's
`DeviceInfo` (identifiers, name, manufacturer, model,
sw_version, hw_version).

### Class: `AkuvoxLockEntity` (in `lock.py`)

Inherits from `AkuvoxEntity` and `LockEntity`.

### Constructor

```python
class AkuvoxLockEntity(AkuvoxEntity, LockEntity):
    def __init__(
        self,
        coordinator: AkuvoxDataUpdateCoordinator,
        relay_number: int,
    ) -> None
```

### Properties

| Property | Type | Source | Description |
| -------- | ---- | ------ | ----------- |
| `unique_id` | `str` | `{mac}_relay_{num}` | Stable identifier |
| `name` | `str` | `Relay {num}` | Entity name (device name prepended by HA) |
| `is_locked` | `bool \| None` | Coordinator data | Parsed from relay_status |
| `available` | `bool` | CoordinatorEntity | Auto-managed by coordinator |
| `device_info` | `DeviceInfo` | Coordinator data | Links to device registry |

### Methods

#### `async_lock(**kwargs) -> None`

Lock entities for intercom relays do not support explicit locking
because intercom doors auto-lock via hardware.
Calling `async_lock` **MUST** raise `HomeAssistantError` with
the message
`"Lock operation not supported; door auto-locks via hardware."`

#### `async_unlock(**kwargs) -> None`

1. Call `await coordinator.device.trigger_relay(num=self._relay_number, delay=5)`
2. Set an internal optimistic override so that `is_locked` returns
   `False` and write state to HA

The relay **MUST** be triggered with a non-zero `delay` so the door
unlocks momentarily and then re-locks after the specified number of
seconds. A `delay` of 0 (the library default) causes the relay to
remain in a sustained unlock state. The integration uses 5 seconds,
matching the Akuvox factory default auto-relock delay. Once the
library supports reading the device's configured delay, this value
should be sourced from the device configuration instead.

After a successful trigger, the entity **MUST** optimistically report
unlocked because the device may not have processed the command by
the time a coordinator poll occurs. The optimistic unlocked state
**MUST NOT** be cleared by any coordinator update that occurs during
the configured unlock-delay window, even if that update reports the
relay as locked. Instead, the optimistic override **MUST** be retained
until the delayed refresh callback fires after the unlock-delay
window expires, at which point the real device state is trusted.
A delayed coordinator refresh **MUST** be scheduled for immediately
after the unlock delay expires so the entity re-syncs with the
device without waiting for the full polling interval.

**Error Handling**:

| Exception | Action |
| --------- | ------ |
| `AkuvoxConnectionError` | `HomeAssistantError` |
| `AkuvoxAuthenticationError` | `HomeAssistantError` |
| `AkuvoxError` | `HomeAssistantError` |

### Platform Setup: `async_setup_entry`

1. Get coordinator from `hass.data[DOMAIN][entry.entry_id]`
2. Parse relay count from coordinator data
3. Create one `AkuvoxLockEntity` per relay
4. Register via `async_add_entities(entities)`
