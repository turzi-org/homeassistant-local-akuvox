<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Contracts: Coordinator

**Feature**: 001-akuvox-lock-integration
**Component**: `__init__.py` (AkuvoxDataUpdateCoordinator)

## Coordinator Contract

### Constructor

```python
class AkuvoxDataUpdateCoordinator(DataUpdateCoordinator):
    def __init__(
        self,
        hass: HomeAssistant,
        device: AkuvoxDevice,
    ) -> None
```

- `update_interval`: `timedelta(seconds=30)`
- Stores `device` reference for API calls

### Data Fetch: `_async_update_data`

**Returns**: `AkuvoxCoordinatorData`

```python
@dataclass
class AkuvoxCoordinatorData:
    device_info: DeviceInfo
    relay_status: dict[str, Any]
```

**Behavior**:

1. Call `await device.get_relay_status()`
2. Call `await device.get_info()` (cached after first successful call)
3. Return combined data

**Error Handling**:

| Exception | Action |
| --------- | ------ |
| `AkuvoxConnectionError` | `UpdateFailed` → unavailable |
| `AkuvoxAuthenticationError` | `ConfigEntryAuthFailed` |
| `AkuvoxDeviceError` | `UpdateFailed` → unavailable |
| `AkuvoxParseError` | `UpdateFailed` → retry |

### Integration Setup: `async_setup_entry`

1. Create `AkuvoxDevice` from config entry data
2. Create `AkuvoxDataUpdateCoordinator` with device
3. Call `coordinator.async_config_entry_first_refresh()`
4. Store coordinator in `hass.data[DOMAIN][entry.entry_id]`
5. Forward setup to `lock` platform

### Integration Teardown: `async_unload_entry`

1. Unload `lock` platform
2. Close `AkuvoxDevice` connection
3. Remove coordinator from `hass.data[DOMAIN]`
