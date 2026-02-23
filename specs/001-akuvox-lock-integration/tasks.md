<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Tasks: Akuvox Lock Integration

**Input**: Design documents from
`/specs/001-akuvox-lock-integration/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md,
contracts/

**Tests**: Included per constitution Principle II (TDD is
NON-NEGOTIABLE). Tests MUST be written and fail before
implementation.

**Organization**: Tasks grouped by user story for independent
implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: User story this task belongs to (US1–US4)
- Paths use `custom_components/akuvox/` and `tests/` per HACS
  layout

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, dependencies, directory
structure, and tooling configuration

- [ ] T001 Initialize uv project with
  `uv init --no-package --name local-akuvox`,
  then use `uv add` to add the production dep
  `pylocal-akuvox`, and `uv add --dev` to add
  pytest, pytest-asyncio, pytest-cov,
  pytest-homeassistant-custom-component, ruff,
  mypy, and interrogate; run `uv lock` and
  commit `uv.lock` (see quickstart.md for
  exact commands)
- [ ] T002 Create directory structure:
  `custom_components/akuvox/`,
  `custom_components/akuvox/translations/`,
  and `tests/`
- [ ] T003 [P] Configure ruff (C901 max
  complexity 10), mypy (strict), and
  interrogate in pyproject.toml per
  constitution Principle I
- [ ] T004 [P] Create HACS metadata file at
  hacs.json with name "Akuvox",
  render_readme true

**Checkpoint**: Project builds, linters run, directory structure
matches plan.md

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared constants, manifest, UI strings, and test
fixtures that ALL user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase
is complete

- [ ] T005 Create constants module in
  `custom_components/akuvox/const.py` defining
  DOMAIN ("akuvox"), PLATFORMS (["lock"]),
  config keys (CONF_HOST, CONF_USE_SSL,
  CONF_VERIFY_SSL, CONF_AUTH_METHOD,
  CONF_USERNAME, CONF_PASSWORD), auth mode
  constants (AUTH_NONE, AUTH_BASIC,
  AUTH_DIGEST), and
  DEFAULT_SCAN_INTERVAL (30)
- [ ] T006 [P] Create integration manifest in
  `custom_components/akuvox/manifest.json`
  with domain "akuvox", name "Akuvox",
  version "0.1.0", requirements
  ["pylocal-akuvox"], config_flow true,
  iot_class "local_polling"
- [ ] T007 [P] Create UI strings in
  `custom_components/akuvox/strings.json`
  with config flow step titles, field labels,
  and error messages for all 4 steps (user,
  ssl, auth, credentials). The auth step MUST
  label AUTH_NONE as "None / AllowList" in the
  UI. Include error keys
  (cannot_connect, invalid_auth, invalid_host,
  already_configured, unknown)
- [ ] T008 [P] Create English translations in
  `custom_components/akuvox/translations/en.json`
  mirroring strings.json content
- [ ] T009 Create shared test fixtures in
  `tests/conftest.py` with mock
  AkuvoxDevice, mock DeviceInfo, mock
  relay_status responses, mock config entry
  data for all auth modes, and
  pytest-homeassistant-custom-component
  setup

**Checkpoint**: Foundation ready — `uv run pytest tests/` runs
(no tests yet but conftest loads), linters pass on all files

---

## Phase 3: User Story 1 — Add Akuvox Device (P1) 🎯 MVP

**Goal**: User adds an Akuvox device via the config flow UI and
a lock entity appears in Home Assistant with a valid state

**Independent Test**: Add a device through the HA UI, confirm
lock entity appears in entity list with locked/unlocked state

### Tests for User Story 1

> **Write these tests FIRST — they MUST FAIL before
> implementation**

- [ ] T010 [P] [US1] Write config flow tests in
  `tests/test_config_flow.py`: test user step
  shows form, test SSL step appears when
  use_ssl=True, test SSL step skipped when
  use_ssl=False, test auth step shows 3
  user-facing auth options (None/AllowList,
  Basic, Digest), test credentials step
  appears for basic/digest, test credentials
  step skipped for none/allowlist, test
  successful connection creates entry, test
  cannot_connect error on
  AkuvoxConnectionError, test invalid_auth
  error on AkuvoxAuthenticationError, test
  already_configured aborts on duplicate MAC,
  test unknown error on generic AkuvoxError
- [ ] T011 [P] [US1] Write coordinator tests in
  `tests/test_coordinator.py`: test
  coordinator fetches device info and relay
  status, test coordinator raises
  UpdateFailed on AkuvoxConnectionError, test
  coordinator raises UpdateFailed on
  AkuvoxDeviceError, test coordinator raises
  UpdateFailed on AkuvoxParseError, test
  coordinator raises ConfigEntryAuthFailed on
  AkuvoxAuthenticationError, test coordinator
  caches device_info after first call
- [ ] T012 [P] [US1] Write integration setup
  tests in `tests/test_init.py`: test
  async_setup_entry creates coordinator and
  stores in hass.data, test async_setup_entry
  forwards to lock platform, test
  async_unload_entry cleans up hass.data and
  closes device, test setup fails gracefully
  on initial connection error
- [ ] T013 [P] [US1] Write lock entity tests in
  `tests/test_lock.py`: test entity created
  with correct unique_id
  ({mac}_relay_{num}), test entity name is
  "Relay {num}", test entity device_info maps
  library DeviceInfo to HA DeviceInfo, test
  is_locked returns True when relay inactive,
  test is_locked returns False when relay
  active, test entity becomes unavailable
  when coordinator fails

### Implementation for User Story 1

- [ ] T014 [US1] Implement
  AkuvoxDataUpdateCoordinator in
  `custom_components/akuvox/coordinator.py`
  with \_async_update_data calling
  `await device.get_relay_status()` and
  `await device.get_info()`, error handling
  per coordinator contract,
  AkuvoxCoordinatorData dataclass, and 30s
  update_interval
- [ ] T015 [US1] Implement AkuvoxEntity base
  class in
  `custom_components/akuvox/entity.py`
  inheriting CoordinatorEntity with
  device_info property converting library
  DeviceInfo to HA DeviceInfo (identifiers,
  name, manufacturer, model, sw_version,
  hw_version)
- [ ] T016 [US1] Implement AkuvoxLockEntity in
  `custom_components/akuvox/lock.py`
  inheriting AkuvoxEntity and LockEntity with
  unique_id, name, is_locked property parsing
  relay_status, and async_setup_entry
  creating one entity per relay
- [ ] T017 [US1] Implement config flow in
  `custom_components/akuvox/config_flow.py`
  with 4 steps (async_step_user,
  async_step_ssl, async_step_auth,
  async_step_credentials), connection test
  using AkuvoxDevice.get_info(), duplicate
  detection via MAC address, and all error
  handling per config-flow contract
- [ ] T018 [US1] Implement async_setup_entry and
  async_unload_entry in
  `custom_components/akuvox/__init__.py`
  creating AkuvoxDevice from entry data
  (reading entry.options first, falling back
  to entry.data), creating coordinator,
  calling first refresh, storing in
  hass.data, forwarding to lock platform,
  and cleanup on unload

**Checkpoint**: User Story 1 fully functional — device can be
added via config flow, lock entity appears with correct state.
`uv run pytest tests/ -x -q` passes all US1 tests

---

## Phase 4: User Story 2 — Control Door Lock (P1)

**Goal**: User triggers unlock action and the device responds,
entity state updates. Lock action raises error (hardware
auto-locks).

**Independent Test**: Trigger unlock from HA UI or service call,
verify device unlocks and entity state changes

### Tests for User Story 2

- [ ] T019 [P] [US2] Write unlock action tests
  in `tests/test_lock.py`: test async_unlock
  calls trigger_relay with correct relay
  number, test async_unlock requests
  coordinator refresh after trigger, test
  async_unlock raises HomeAssistantError on
  AkuvoxConnectionError, test async_unlock
  raises HomeAssistantError on
  AkuvoxAuthenticationError, test
  async_unlock raises HomeAssistantError on
  generic AkuvoxError
- [ ] T020 [P] [US2] Write lock action tests in
  `tests/test_lock.py`: test async_lock
  raises HomeAssistantError with message
  "Lock operation not supported; door
  auto-locks via hardware."

### Implementation for User Story 2

- [ ] T021 [US2] Implement async_unlock in
  `custom_components/akuvox/lock.py` calling
  `await coordinator.device.trigger_relay(num=relay_number)`,
  then `await coordinator.async_request_refresh()`,
  with try/except mapping all AkuvoxError
  subclasses to HomeAssistantError
- [ ] T022 [US2] Implement async_lock in
  `custom_components/akuvox/lock.py` raising
  HomeAssistantError with the specified
  message per lock-entity contract

**Checkpoint**: Unlock works end-to-end, lock raises appropriate
error. `uv run pytest tests/ -x -q` passes all US1+US2 tests

---

## Phase 5: User Story 3 — Monitor Lock State (P2)

**Goal**: Lock entity state updates automatically via polling.
Entity becomes unavailable when device is unreachable and
recovers when device comes back online.

**Independent Test**: Observe entity state in HA while changing
lock state on device; verify update within 30s polling interval

### Tests for User Story 3

- [ ] T023 [P] [US3] Write polling state tests in
  `tests/test_coordinator.py`: test state
  reflects relay change after coordinator
  update, test entity marked unavailable when
  coordinator raises UpdateFailed, test
  entity recovers to correct state within
  2 coordinator update cycles after device
  comes back online (SC-004), test polling
  interval is 30s
- [ ] T024 [P] [US3] Write state mapping tests
  in `tests/test_lock.py`: test is_locked
  returns True for relay closed/inactive
  state, test is_locked returns False for
  relay open/active state, test is_locked
  returns None when relay status is unknown

### Implementation for User Story 3

- [ ] T025 [US3] Refine relay state parsing in
  `custom_components/akuvox/lock.py` to
  handle all relay state values from
  `get_relay_status()` response, mapping to
  locked/unlocked/unknown per data-model
  state mapping table
- [ ] T026 [US3] Ensure coordinator in
  `custom_components/akuvox/coordinator.py`
  correctly raises UpdateFailed for
  connection and device errors so HA marks
  entities unavailable, and verify recovery
  behavior on successful update after
  failures

**Checkpoint**: Polling works, state updates automatically,
unavailable/recovery works. `uv run pytest tests/ -x -q` passes
all US1+US2+US3 tests

---

## Phase 6: User Story 4 — Multiple Relay Support (P3)

**Goal**: Devices with multiple relays create one lock entity per
relay. Each relay can be controlled independently.

**Independent Test**: Configure device with multiple relays,
verify separate lock entities appear, unlock one relay and
confirm only that entity changes state

### Tests for User Story 4

- [ ] T027 [P] [US4] Write multi-relay tests in
  `tests/test_lock.py`: test
  async_setup_entry creates two entities for
  device with two relays, test each entity
  has unique unique_id ({mac}_relay_1,
  {mac}_relay_2), test each entity has
  distinct name (Relay 1, Relay 2), test
  unlocking relay 1 only changes relay 1
  entity state, test relay 2 state unchanged
  when relay 1 is unlocked
- [ ] T028 [P] [US4] Write multi-relay
  coordinator tests in
  `tests/test_coordinator.py`: test
  coordinator data includes status for all
  relays, test relay status parsing handles
  multiple relay entries

### Implementation for User Story 4

- [ ] T029 [US4] Update async_setup_entry in
  `custom_components/akuvox/lock.py` to parse
  relay count from coordinator data and
  create one AkuvoxLockEntity per relay with
  correct relay_number
- [ ] T030 [US4] Ensure is_locked in
  `custom_components/akuvox/lock.py` reads
  the correct relay's state from the
  relay_status dict using self._relay_number

**Checkpoint**: Multiple relays work independently.
`uv run pytest tests/ -x -q` passes all US1–US4 tests

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Options flow (FR-010), documentation, and final
validation

- [ ] T031 [P] Write options flow tests in
  `tests/test_config_flow.py`: test options
  flow shows current values pre-filled, test
  options flow updates entry.options, test
  integration reloads after options change
- [ ] T032 Implement options flow in
  `custom_components/akuvox/config_flow.py`
  with OptionsFlow class presenting all
  connection parameters pre-filled from
  current config, saving to entry.options,
  and triggering integration reload
- [ ] T033 [P] Update `__init__.py` to read
  connection params from entry.options with
  fallback to entry.data when creating
  AkuvoxDevice in
  `custom_components/akuvox/__init__.py`
- [ ] T034 [P] Run full test suite with
  coverage:
  `uv run pytest tests/ --cov=custom_components/akuvox`
  `--cov-report=term-missing`
  and ensure no coverage regressions
- [ ] T035 Run quickstart.md validation: verify
  all commands in
  `specs/001-akuvox-lock-integration/quickstart.md`
  execute successfully
- [ ] T036 [P] Add performance acceptance tests
  in `tests/test_lock.py`: test async_unlock
  completes within 5 seconds (SC-002) using
  mock device; test coordinator
  update_interval is timedelta(seconds=30)
  (SC-003); test entity recovery within 2
  coordinator update cycles after device
  comes back online (SC-004)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup completion —
  BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Foundational — MVP target
- **US2 (Phase 4)**: Depends on US1 (needs lock entity to exist)
- **US3 (Phase 5)**: Depends on US1 (needs coordinator running)
- **US4 (Phase 6)**: Depends on US1 (needs entity creation logic)
- **Polish (Phase 7)**: Depends on US1 minimum; ideally all
  stories complete

### User Story Dependencies

- **US1 (P1)**: After Phase 2 — no other story dependencies
- **US2 (P1)**: After US1 — needs lock entity for unlock action
- **US3 (P2)**: After US1 — needs coordinator for polling
- **US4 (P3)**: After US1 — needs entity creation logic

### Within Each User Story

- Tests MUST be written and FAIL before implementation (TDD)
- Coordinator before entity before lock before config flow
- Core implementation before integration wiring
- Story complete and tested before moving to next priority

### Parallel Opportunities

- T003, T004 can run in parallel (different files)
- T006, T007, T008 can run in parallel (different files)
- T010, T011, T012, T013 can all run in parallel (different
  test files)
- T019, T020 can run in parallel (same file but different test
  classes)
- T023, T024 can run in parallel (different test files)
- T027, T028 can run in parallel (different test files)
- T031, T033, T034 can run in parallel (different files)
- US3 and US4 can run in parallel after US1 completes

---

## Parallel Example: User Story 1

```text
# Launch all US1 tests in parallel (must fail initially):
Task T010: Config flow tests in tests/test_config_flow.py
Task T011: Coordinator tests in tests/test_coordinator.py
Task T012: Init tests in tests/test_init.py
Task T013: Lock entity tests in tests/test_lock.py

# Then implement sequentially:
Task T014: Coordinator (no deps within US1)
Task T015: Base entity (needs coordinator)
Task T016: Lock entity (needs entity + coordinator)
Task T017: Config flow (needs all above for connection test)
Task T018: Init wiring (ties everything together)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Test US1 independently
5. Deploy/demo if ready — device can be added and entity appears

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1 → Test → Deploy (MVP: device discovery)
3. Add US2 → Test → Deploy (unlock works)
4. Add US3 → Test → Deploy (polling/state monitoring)
5. Add US4 → Test → Deploy (multi-relay support)
6. Polish → Options flow, coverage, docs

### Suggested MVP Scope

User Story 1 alone provides a functional integration: users can
add a device and see lock entities. Combined with US2, users get
the core lock/unlock functionality. US1+US2 together form the
recommended MVP.

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks
- [Story] label maps task to specific user story
- Constitution Principle II (TDD): tests MUST fail before
  implementation — red-green-refactor enforced
- Constitution Principle V: commit after each task with SPDX
  headers and DCO sign-off
- All Python files MUST have SPDX headers per constitution
- Stop at any checkpoint to validate story independently
