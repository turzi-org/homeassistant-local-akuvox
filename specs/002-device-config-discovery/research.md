<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Research: Device Config Discovery

## R1: DeviceConfig API Shape and Key Naming

**Decision**: Use `DeviceConfig.get(key, default)` for all config reads with
dotted, dot-separated key names.

**Rationale**: `DeviceConfig` is a frozen dataclass wrapping `dict[str, str]`.
All values are strings. The `.get()` method with a default safely handles
missing keys. Keys follow the pattern `Config.DoorSetting.RELAY.{Property}{Letter}`.

**Key mapping** (from live E18 device polling):

| Config Key | Purpose | Default |
| --- | --- | --- |
| `...DEVICENODE.Location` | Device name | `""` → "Akuvox {model}" |
| `...RELAY.NameA` | Relay A name | `""` → "Relay A" |
| `...RELAY.NameB` | Relay B name | `""` → "Relay B" |
| `...RELAY.HoldDelayA` | Relay A delay (s) | `"5"` |
| `...RELAY.HoldDelayB` | Relay B delay (s) | `"5"` |
| `...RELAY.RelayAType` | A type (0=NO, 1=NC) | `"0"` |
| `...RELAY.RelayBType` | B type (0=NO, 1=NC) | `"0"` |
| `...RELAY.RelayAMode` | A mode (0=Auto, 1=Man) | `"0"` |
| `...RELAY.RelayBMode` | B mode (0=Auto, 1=Man) | `"0"` |
| `...RELAY.TriggerDelayA` | Pre-trigger delay | `"0"` |

All keys are prefixed with `Config.DoorSetting`.

**Alternatives considered**:

- Parsing keys generically with regex: Rejected — known key set is small and
  static, explicit mapping is clearer and easier to test.

## R2: Config Refresh Timing

**Decision**: Fetch config in the coordinator's `_async_update_data` on first
successful poll and whenever the device transitions from unavailable to
available. Cache the config in the coordinator and only re-fetch on
reconnection events.

**Rationale**: The spec requires config refresh on: (1) initial setup,
(2) integration reload, (3) unavailable→available transition. The coordinator
already handles (1) and (2) via `async_config_entry_first_refresh`. For (3),
we detect when `_cached_device_info` was previously set but the last update
failed (device was unavailable) and then succeeds again, triggering a config
re-read.

**Implementation approach**: Add a `_was_unavailable` flag to the coordinator.
When an update fails (raises `UpdateFailed`), set the flag. On the next
successful update, if the flag is set, re-fetch config and clear the flag.
This naturally handles the unavailable→available transition.

**Alternatives considered**:

- Fetching config on every poll: Rejected — unnecessary HTTP overhead for data
  that rarely changes. Config only needs refreshing on connection events.
- Using HA's `async_on_unload` with event listeners: Rejected — the
  coordinator's existing update cycle already provides the right hook points.

## R3: Relay Letter Suffix Mapping

**Decision**: Map relay key suffix letter to config key suffix letter directly.
`RelayA` → suffix `A`, `RelayB` → suffix `B`. Build config key by
concatenating property name + suffix letter.

**Rationale**: The existing `_RELAY_NUM_RE` regex already extracts the letter.
Config keys use the same letter: `NameA`, `HoldDelayA`, `RelayAType`, etc.
Note the inconsistency: some keys use `{Property}{Letter}` (e.g., `NameA`,
`HoldDelayA`) while type/mode keys use `Relay{Letter}{Property}` (e.g.,
`RelayAType`, `RelayAMode`). This must be handled in the key builder.

**Alternatives considered**:

- Mapping by relay number: Rejected — adds unnecessary conversion step.

## R4: NO/NC State Interpretation

**Decision**: Invert the state interpretation when relay type is NC (1).
For NO relays: 0=locked, 1=unlocked (current behavior).
For NC relays: 0=unlocked, 1=locked (inverted).

**Rationale**: In a NO relay, the circuit is open (de-energized) at rest, so
state 0 = locked. Energizing closes the circuit (state 1 = unlocked). In NC,
the circuit is closed at rest, so state 0 = unlocked (circuit is already
closed/door open). This matches the spec acceptance scenarios.

The `level` parameter in `trigger_relay` corresponds to the relay type value:

- NO relay: `level=0` (trigger NO-COM contact)
- NC relay: `level=1` (trigger NC-COM contact)

**Alternatives considered**:

- Making state interpretation user-configurable: Rejected — the device already
  stores the correct relay type, and the spec says to read it from config.

## R5: Config Value Validation

**Decision**: Parse string config values with safe fallbacks. Use `int()` with
try/except for numeric values. Log warnings for invalid values and fall back
to factory defaults.

**Rationale**: All `DeviceConfig` values are strings. Hold delay must be
parsed to int, relay type to int (0 or 1). Invalid or out-of-range values
should not crash the integration.

**Validation rules**:

- Hold delay: Positive integer ≥1. Default: 5.
- Relay type: Must be 0 or 1. Default: 0 (NO).
- Relay mode: Must be 0 or 1. Default: 0 (Auto).
- Names: Any non-empty string is valid. Empty/missing → use existing fallback.

**Alternatives considered**:

- Strict validation that rejects the entire config: Rejected — partial config
  is better than no config.

## R6: Device Name from Config

**Decision**: Use `Config.DoorSetting.DEVICENODE.Location` as the HA device
name if non-empty. Fall back to existing "Akuvox {model}" pattern.

**Rationale**: The entity.py `device_info` property currently hardcodes
`name=f"Akuvox {lib_info.model}"`. The spec requires using the device's
location name. This property needs access to the cached config.

**Implementation approach**: Store the parsed device name in the coordinator
data alongside `device_info` and `relay_status`. The entity base class reads
it from there.

**Alternatives considered**:

- Storing the name in the config entry: Rejected — name should update on
  reconnect without config entry modification.
