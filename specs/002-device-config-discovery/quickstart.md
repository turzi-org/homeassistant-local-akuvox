<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Quickstart: Device Config Discovery

## Overview

This feature adds device configuration reading to the Akuvox integration.
Instead of hardcoded relay names, unlock delays, and state interpretation,
the integration reads these values from the device itself on every connection
event.

## Development Phases

### Phase 1 — Device-Sourced Naming (US1, P1)

**Goal**: Use device-configured names for the HA device and relay entities.

**Files to modify**:

- `coordinator.py`: Add `DeviceConfig` fetch, `RelayConfig` dataclass,
  `device_name` and `relay_configs` to `AkuvoxCoordinatorData`
- `entity.py`: Use `device_name` from coordinator data for device name
- `lock.py`: Use `RelayConfig.name` for entity name (with fallback)
- `const.py`: Add config key constants
- `tests/conftest.py`: Add `DeviceConfig` mock fixture
- `tests/test_coordinator.py`: Test config fetch and parsing
- `tests/test_lock.py`: Test entity naming from config
- `tests/test_init.py`: Update if entity.py device name changes affect setup

**Key changes**:

1. Coordinator fetches `get_device_config()` on first successful update
2. Parses location name and per-relay names from config keys
3. Entity base class uses parsed device name
4. Lock entity uses per-relay name from config

### Phase 2 — Config-Driven Relay Delay (US2, P2)

**Goal**: Use per-relay hold-delay from device config for unlock timing.

**Files to modify**:

- `lock.py`: Replace `_RELAY_UNLOCK_DELAY_SECONDS` constant with
  per-relay `hold_delay` from `RelayConfig`; adjust refresh timer
- `tests/test_lock.py`: Test unlock delay from config, fallback behavior

**Key changes**:

1. Lock entity reads `hold_delay` from its `RelayConfig`
2. Passes config delay to `trigger_relay(delay=hold_delay)`
3. Adjusts delayed refresh timer to `hold_delay + 1s` buffer
   (existing `_RELAY_REFRESH_BUFFER_SECONDS` constant)
4. Falls back to 5 seconds if config unavailable

### Phase 3 — Relay Type Awareness (US3, P3)

**Goal**: Correctly interpret lock state for NO/NC relay wiring.

**Files to modify**:

- `lock.py`: Update state parsing to account for relay type; pass `level`
  and `mode` to `trigger_relay()`
- `tests/test_lock.py`: Test all NO/NC state combinations

**Key changes**:

1. Lock entity reads `relay_type` from its `RelayConfig`
2. State parsing inverts interpretation for NC relays
3. `trigger_relay` call includes `level=relay_type` and `mode=relay_mode`
4. Falls back to NO interpretation if config unavailable

## Testing Strategy

- **TDD**: Every change starts with a failing test
- **Mock DeviceConfig**: Fixture returns `DeviceConfig(data={...})` with
  configurable keys
- **Fallback tests**: Verify safe defaults when config is missing/invalid
- **Reconnection tests**: Verify config refresh on unavailable→available
