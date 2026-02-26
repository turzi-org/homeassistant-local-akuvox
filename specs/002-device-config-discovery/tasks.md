<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Tasks: Device Config Discovery

**Feature**: 002-device-config-discovery
**Date**: 2026-02-26
**Input**: Design documents from `specs/002-device-config-discovery/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md,
quickstart.md

**Tests**: Required — constitution mandates TDD (red-green-refactor).
Every unit of production code MUST be preceded by a failing test.

**Organization**: Tasks grouped by user story for independent
implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story (US1, US2, US3)
- Exact file paths included in descriptions

## Path Conventions

```text
custom_components/akuvox/   # Source code
tests/                      # Test files
```

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add constants, imports, and test fixtures needed by
all subsequent phases.

- [ ] T001 Add device config key constants and default values
  to custom_components/akuvox/const.py — add
  `CONFIG_KEY_PREFIX = "Config.DoorSetting"`,
  `CONFIG_KEY_LOCATION = "Config.DoorSetting.DEVICENODE.Location"`,
  relay key patterns (Name, HoldDelay, Type, Mode),
  `DEFAULT_HOLD_DELAY_SECONDS = 5`,
  `DEFAULT_RELAY_TYPE = 0`, `DEFAULT_RELAY_MODE = 0`
- [ ] T002 [P] Add DeviceConfig mock fixture to
  tests/conftest.py — import `DeviceConfig` from
  `pylocal_akuvox`, create `mock_device_config` factory
  fixture returning `DeviceConfig` with configurable keys;
  add `get_device_config` mock to `mock_akuvox_device`
  fixture returning default DeviceConfig
- [ ] T003 [P] Add `DeviceConfig` import to
  custom_components/akuvox/coordinator.py — import
  `DeviceConfig` from `pylocal_akuvox` alongside existing
  imports

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data structures, config parsing, and coordinator
integration that ALL user stories depend on.

**⚠️ CRITICAL**: No user story work can begin until this phase is
complete.

### Tests for Foundational

> **NOTE: Write these tests FIRST, ensure they FAIL before
> implementation**

- [ ] T004 [P] Write tests for RelayConfig dataclass creation
  with defaults and field validation in
  tests/test_coordinator.py — verify default field values
  (name="", hold_delay=5, relay_type=0, relay_mode=0),
  verify frozen/immutable behavior
- [ ] T005 [P] Write tests for `_parse_config_int` helper in
  tests/test_coordinator.py — valid int string returns int,
  non-numeric string returns default, empty string returns
  default, out-of-range value returns default, negative
  value returns default; verify warning logged for invalid
- [ ] T006 [P] Write tests for `_build_relay_config` helper in
  tests/test_coordinator.py — given DeviceConfig with all
  keys for letter "A", returns populated RelayConfig; given
  empty DeviceConfig, returns RelayConfig with all defaults;
  given partial config (some keys missing), fills in
  defaults for missing keys

### Implementation for Foundational

- [ ] T007 Implement `RelayConfig` frozen dataclass in
  custom_components/akuvox/coordinator.py — fields: name
  (str, default ""), hold_delay (int, default 5),
  relay_type (int, default 0), relay_mode (int, default 0)
- [ ] T008 Implement `_parse_config_int` helper in
  custom_components/akuvox/coordinator.py — parse string to
  int with try/except, validate against min/max/allowed
  values, return default on failure, log warning for
  invalid values
- [ ] T009 Implement `_build_relay_config` helper in
  custom_components/akuvox/coordinator.py — accepts
  DeviceConfig and relay letter suffix, builds full config
  keys using patterns from research.md R3 (Name{L},
  HoldDelay{L}, Relay{L}Type, Relay{L}Mode), returns
  RelayConfig with parsed values or defaults

### Coordinator Integration Tests

- [ ] T010 Write tests for updated AkuvoxCoordinatorData in
  tests/test_coordinator.py — verify data includes
  device_name (str) and relay_configs (dict[str,
  RelayConfig]) fields alongside existing device_info and
  relay_status
- [ ] T011 Write tests for DeviceConfig fetch on first
  successful poll in tests/test_coordinator.py — mock
  device.get_device_config, verify called once on first
  _async_update_data, verify device_name and relay_configs
  populated from DeviceConfig values
- [ ] T012 Write tests for config fetch failure graceful
  degradation in tests/test_coordinator.py — cover BOTH:
  (a) first-ever config fetch failure: when initial
  get_device_config call raises AkuvoxConnectionError and
  no cached config exists, verify coordinator returns data
  with default device_name ("Akuvox {model}") and default
  RelayConfigs and logs a warning; and (b) subsequent
  config fetch failure: when get_device_config raises
  AkuvoxConnectionError after a previous successful fetch,
  verify coordinator keeps the previously cached
  device_name and RelayConfigs unchanged and logs a
  warning
- [ ] T013 Write tests for `_was_unavailable` reconnection
  config refresh in tests/test_coordinator.py — simulate
  update failure (UpdateFailed) followed by successful
  update, verify get_device_config called again on
  recovery; verify config NOT re-fetched on normal
  successive polls

### Coordinator Integration Implementation

- [ ] T014 Add device_name and relay_configs fields to
  AkuvoxCoordinatorData in
  custom_components/akuvox/coordinator.py — device_name:
  str, relay_configs: dict[str, RelayConfig]; update
  _async_update_data return to populate these fields
- [ ] T015 Implement DeviceConfig fetch and parsing in
  _async_update_data in
  custom_components/akuvox/coordinator.py — call
  get_device_config on first successful poll, parse
  location for device_name (fallback to "Akuvox {model}"),
  build RelayConfig per relay letter from relay_status
  keys; on config fetch failure: if no cached config
  exists use defaults, if cached config exists preserve
  last known-good values (do NOT overwrite with defaults
  on transient failure); log warning on failure
- [ ] T016 Implement `_was_unavailable` flag and reconnection
  logic in custom_components/akuvox/coordinator.py — add
  `_was_unavailable: bool = False` to `__init__`, set True
  when `_async_update_data` raises UpdateFailed (via
  override or tracking), on next successful update if flag
  is True re-fetch DeviceConfig and clear flag
- [ ] T017 Update existing coordinator tests that may break
  due to AkuvoxCoordinatorData field changes in
  tests/test_coordinator.py — existing tests asserting on
  AkuvoxCoordinatorData may need updates for new fields;
  ensure all existing tests pass with updated dataclass

**Checkpoint**: Foundation ready — RelayConfig, config parsing,
coordinator fetch, and reconnection logic all working. User story
implementation can begin.

---

## Phase 3: User Story 1 — Device-Sourced Naming (P1) 🎯 MVP

**Goal**: Use device-configured names for the HA device and relay
entities.

**Independent Test**: Set up a device whose config has custom
relay names and verify entities appear with those names.

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before
> implementation**

- [ ] T018 [P] [US1] Write tests for device name from config
  location in tests/test_init.py — when DeviceConfig has
  location "Front Door", verify HA device name is "Front
  Door"; when location is empty, verify fallback to
  "Akuvox {model}"
- [ ] T019 [P] [US1] Write tests for relay entity naming from
  config in tests/test_lock.py — when DeviceConfig has
  NameA="Main Gate", verify entity name is "Main Gate";
  when NameA is empty, verify fallback to "Relay A"
- [ ] T020 [P] [US1] Write tests for name update on
  reconnection in tests/test_coordinator.py — simulate
  unavailable→available with changed location name, verify
  device_name updates to new value

### Implementation for User Story 1

- [ ] T021 [US1] Update `device_info` property to use
  device_name from coordinator data in
  custom_components/akuvox/entity.py — replace hardcoded
  `f"Akuvox {lib_info.model}"` with
  `self.coordinator.data.device_name`
- [ ] T022 [US1] Update AkuvoxLockEntity to use
  RelayConfig.name for entity naming in
  custom_components/akuvox/lock.py — in `__init__`, look up
  relay letter in coordinator.data.relay_configs, if
  config name is non-empty use it, otherwise fall back to
  existing `_relay_key_to_label(relay_key)`
- [ ] T023 [US1] Update existing tests that reference
  hardcoded entity IDs in tests/ — entity IDs derived
  from device name may change when config provides a
  custom name; ensure test fixtures provide consistent
  names so existing tests remain stable

**Checkpoint**: Device and relay entities show config-sourced
names. Fallback to defaults when config missing. Names refresh on
reconnection.

---

## Phase 4: User Story 2 — Config-Driven Relay Delay (P2)

**Goal**: Use per-relay hold-delay from device config for unlock
timing.

**Independent Test**: Change hold-delay on device config and
verify unlock command uses the updated value.

### Tests for User Story 2

> **NOTE: Write these tests FIRST, ensure they FAIL before
> implementation**

- [ ] T024 [P] [US2] Write tests for per-relay hold_delay in
  trigger_relay call in tests/test_lock.py — when
  RelayConfig has hold_delay=7, verify trigger_relay
  called with delay=7; verify different relays use their
  own hold_delay values
- [ ] T025 [P] [US2] Write tests for refresh timer using
  config hold_delay + buffer in tests/test_lock.py —
  verify async_call_later uses hold_delay +
  _RELAY_REFRESH_BUFFER_SECONDS (1s); when hold_delay=7,
  timer should be 8s
- [ ] T026 [US2] Write tests for hold_delay fallback to 5s
  default in tests/test_lock.py — when relay_configs is
  empty or missing relay letter, verify trigger_relay uses
  DEFAULT_HOLD_DELAY_SECONDS (5); verify refresh timer
  uses 5 + 1 = 6s
- [ ] T026b [US2] Write test for hold_delay update after
  reconnection in tests/test_lock.py — simulate device
  unavailable→available with changed HoldDelay value,
  verify next unlock uses updated hold_delay (spec
  US2-AS5)

### Implementation for User Story 2

- [ ] T027 [US2] Update async_unlock to use hold_delay from
  RelayConfig in custom_components/akuvox/lock.py —
  read relay letter's RelayConfig from
  coordinator.data.relay_configs, pass
  `delay=relay_config.hold_delay` to trigger_relay;
  replace `_RELAY_UNLOCK_DELAY_SECONDS` constant usage;
  remove `_RELAY_UNLOCK_DELAY_SECONDS` constant if all
  usages are replaced
- [ ] T028 [US2] Update _schedule_delayed_refresh to use
  config hold_delay + buffer in
  custom_components/akuvox/lock.py — replace
  `_RELAY_UNLOCK_DELAY_SECONDS + _RELAY_REFRESH_BUFFER_SECONDS`
  with `relay_config.hold_delay + _RELAY_REFRESH_BUFFER_SECONDS`;
  store hold_delay or pass as parameter

**Checkpoint**: Unlock uses device-configured delay. Refresh timer
aligns with actual delay. Falls back to 5s when config missing.

---

## Phase 5: User Story 3 — Relay Type Awareness (P3)

**Goal**: Correctly interpret lock state for NO/NC relay wiring.

**Independent Test**: Configure a relay as NC and verify that
state value 0 shows "unlocked" instead of "locked".

### Tests for User Story 3

> **NOTE: Write these tests FIRST, ensure they FAIL before
> implementation**

- [ ] T029 [P] [US3] Write tests for NO relay state
  interpretation in tests/test_lock.py — NO relay (type=0):
  state 0 → locked, state 1 → unlocked (current behavior,
  regression test)
- [ ] T030 [P] [US3] Write tests for NC relay state
  interpretation in tests/test_lock.py — NC relay (type=1):
  state 0 → unlocked, state 1 → locked (inverted)
- [ ] T031 [P] [US3] Write tests for trigger_relay level and
  mode parameters in tests/test_lock.py — NO relay:
  verify trigger_relay called with level=0, mode=0;
  NC relay: verify trigger_relay called with level=1;
  auto-close mode: mode=0; manual mode: mode=1
- [ ] T032 [US3] Write tests for fallback to NO interpretation
  when relay_type missing in tests/test_lock.py — when
  relay_configs has no entry for relay letter, verify NO
  interpretation (0=locked, 1=unlocked) and level=0

### Implementation for User Story 3

- [ ] T033 [US3] Update state parsing to accept relay_type for
  NO/NC inversion in custom_components/akuvox/lock.py —
  add relay_type parameter to `_parse_relay_state` and
  `_parse_int_state`; when relay_type=1 (NC), invert the
  int state mapping (0=unlocked, 1=locked); leave string
  state parsing unchanged
- [ ] T034 [US3] Update is_locked to pass relay_type from
  RelayConfig to state parser in
  custom_components/akuvox/lock.py — read relay_type from
  coordinator.data.relay_configs for this relay's letter,
  pass to `_parse_relay_state`
- [ ] T035 [US3] Update async_unlock to pass level and mode
  to trigger_relay in custom_components/akuvox/lock.py —
  add `level=relay_config.relay_type` and
  `mode=relay_config.relay_mode` to the trigger_relay call

**Checkpoint**: Lock state correctly reported for both NO and NC
relay types. Trigger command sends correct level/mode. Falls back
to NO when config missing.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Edge cases, cleanup, and documentation.

- [ ] T036 [P] Add edge case tests for non-numeric and
  out-of-range config values in tests/test_coordinator.py
  — HoldDelay="abc", RelayType="99", RelayMode="-1";
  verify all fall back to defaults with warnings logged
- [ ] T037 [P] Add tests for relay without matching config
  entry in tests/test_lock.py — relay exists in
  relay_status but has no matching config key; verify
  default RelayConfig used for naming, delay, and state
- [ ] T038 [P] Add tests for config fetch during integration
  reload in tests/test_init.py — unload and reload
  integration, verify get_device_config called on reload
- [ ] T039 Update agent context with F002 implementation
  details in .github/agents/copilot-instructions.md —
  run `.specify/scripts/bash/update-agent-context.sh
  copilot`
- [ ] T040 Run full test suite and verify all tests pass
- [ ] T041 Run quickstart.md validation scenarios end-to-end

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion —
  BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Foundational (Phase 2)
- **US2 (Phase 4)**: Depends on Foundational (Phase 2); may
  depend on US1 for entity name stability in tests
- **US3 (Phase 5)**: Depends on Foundational (Phase 2);
  independent of US1/US2
- **Polish (Phase 6)**: Depends on all user stories complete

### User Story Dependencies

- **US1 (P1)**: Can start after Phase 2 — no other story deps
- **US2 (P2)**: Can start after Phase 2 — uses RelayConfig from
  Phase 2; recommend after US1 for stable entity setup
- **US3 (P3)**: Can start after Phase 2 — independent of
  US1/US2; only modifies state parsing and trigger params

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Implementation follows red-green-refactor cycle
- Story complete before moving to next priority
- Commit after each logical TDD cycle

### Parallel Opportunities

- **Phase 1**: T002 and T003 can run in parallel
- **Phase 2**: T004, T005, T006 can run in parallel (all tests)
- **Phase 3**: T018, T019, T020 can run in parallel (US1 tests)
- **Phase 4**: T024, T025 can run in parallel (US2 tests)
- **Phase 5**: T029, T030, T031 can run in parallel (US3 tests)
- **Phase 6**: T036, T037, T038 can run in parallel

---

## Parallel Example: User Story 1

```text
# Launch all US1 tests together (different test files):
T018: Device name from config in tests/test_init.py
T019: Relay entity naming from config in tests/test_lock.py
T020: Name update on reconnection in tests/test_coordinator.py

# Then implement sequentially:
T021: entity.py device_info update
T022: lock.py relay naming
T023: Existing test stability
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Test US1 independently
5. All entities show config-sourced names with fallbacks

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1 → Names from config → Validate (MVP!)
3. Add US2 → Per-relay delay → Validate
4. Add US3 → NO/NC state awareness → Validate
5. Polish → Edge cases, docs, cleanup

### Sequential Strategy (Recommended for Solo Dev)

1. Complete Phases 1-2 together (Setup + Foundation)
2. US1 (P1) → most visible user improvement
3. US2 (P2) → correct unlock timing
4. US3 (P3) → correct state for NC wiring
5. Polish → edge cases and documentation

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story
- TDD is NON-NEGOTIABLE per constitution (Principle II)
- Commit after each TDD cycle (test + implementation)
- Existing tests may need updates when AkuvoxCoordinatorData
  gains new fields — handle in T017 and T023
- Entity IDs in HA are derived from device name; changing
  device name from config may affect entity ID patterns in
  existing tests
- The `_RELAY_UNLOCK_DELAY_SECONDS` constant can be removed
  after US2 replaces all usages with config-driven values
