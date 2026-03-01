<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Tasks: Schedule & User Management Services

**Input**: Design documents from
`/specs/003-schedule-user-services/`
**Prerequisites**: plan.md, spec.md, research.md,
data-model.md, contracts/

**Tests**: TDD is mandatory per project constitution. Every
implementation task is preceded by a failing test task
(Red-Green-Refactor).

**Organization**: Tasks grouped by user story for independent
implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no deps)
- **[Story]**: User story label (US1, US2, etc.)

## Path Conventions

- **Integration**: `custom_components/akuvox/`
- **Tests**: `tests/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add constants, service YAML definitions, and UI
strings needed by all 10 services.

- [x] T001 Add service name constants (SERVICE_LIST_SCHEDULES,
  SERVICE_ADD_SCHEDULE, SERVICE_MODIFY_SCHEDULE,
  SERVICE_DELETE_SCHEDULE, SERVICE_LIST_USERS,
  SERVICE_ADD_USER, SERVICE_MODIFY_USER,
  SERVICE_DELETE_USER, SERVICE_ADD_USER_SCHEDULE_RELAY,
  SERVICE_REMOVE_USER_SCHEDULE_RELAY) and event name
  constants (EVENT_SCHEDULE_CHANGED, EVENT_USER_CHANGED)
  to custom_components/akuvox/const.py
- [x] T002 [P] Create custom_components/akuvox/services.yaml
  (with SPDX header) with all 10 service definitions
  including entity target selectors (domain: lock,
  integration: akuvox), field schemas matching contracts,
  and `supports_response: only` for list services.
  Reference contracts/schedule-services.md and
  contracts/user-services.md for field definitions.
- [x] T003 [P] Add service name/description/field strings
  and exception strings to the `"services"` and
  `"exceptions"` sections of
  custom_components/akuvox/strings.json
- [x] T004 [P] Add matching service and exception translation
  strings to
  custom_components/akuvox/translations/en.json

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Service registration in `async_setup()` and test
scaffolding. MUST complete before any user story.

**⚠️ CRITICAL**: No user story work can begin until this
phase is complete.

- [x] T005 Add `async_setup(hass, config)` function to
  `custom_components/akuvox/__init__.py` that registers
  all 10 services via
  `service.async_register_platform_entity_service()` from
  `homeassistant.helpers.service`. Each call passes: hass,
  DOMAIN, service constant, entity_domain=LOCK_DOMAIN,
  schema dict (from contracts), func=service constant
  string. List services set
  `supports_response=SupportsResponse.ONLY`. Import
  voluptuous, cv, SupportsResponse, LOCK_DOMAIN. Function
  returns True. Follow Schlage pattern from research.md.
- [x] T006 [P] Add mock fixtures to tests/conftest.py:
  `mock_schedule_list` (list of AccessSchedule-like
  objects with id, schedule_type, name, week, daily,
  date_start, date_end, time_start, time_end, display_id,
  source_type (`"1"` = local, `"2"` = cloud), mode, sun-sat
  fields; include one local (source_type `"1"`) and
  one cloud-provisioned (source_type `"2"`) schedule),
  `mock_user_list` (list of User-like objects with id,
  name, user_id, schedule_relay, web_relay, private_pin,
  card_code, lift_floor_num, user_type, source,
  source_type (`"1"` = local, `"2"` = cloud); include one
  local and one cloud-provisioned
  user), and `mock_empty_list` (empty list). Add all
  device method mocks to the existing
  `mock_akuvox_device` fixture: `list_schedules`,
  `list_users`, `add_schedule`, `modify_schedule`,
  `delete_schedule`, `add_user`, `modify_user`, and
  `delete_user` as AsyncMock methods.
- [x] T007 [P] Create tests/test_services.py (with SPDX
  header) with base test infrastructure: imports for
  pytest, HomeAssistantError, ServiceValidationError,
  helper to set up a loaded config entry with lock entity
  for service testing, and helper to assert library
  exceptions map to correct HA errors per research.md
  exception mapping table.

**Checkpoint**: Foundation ready — `async_setup()` registers
services, test fixtures exist, user stories can begin.

---

## Phase 3: User Story 1 — List Schedules (P1) 🎯 MVP

**Goal**: Retrieve all device access schedules including
cloud-provisioned ones (identifiable by `source_type` `"2"`).

**Independent Test**: Call `akuvox.list_schedules` via
Developer Tools, verify returned schedule dicts match device.

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL**

- [x] T008 [US1] Write failing tests for `list_schedules`
  in tests/test_services.py: (a) success returns
  `{"schedules": [...]}` with all AccessSchedule fields
  converted to dict, (b) empty schedule list returns
  `{"schedules": []}`, (c) page parameter passed through
  to `device.list_schedules(page=N)`, (d) page number
  exceeding total pages returns empty list,
  (e) device offline raises HomeAssistantError,
  (f) auth failure raises HomeAssistantError,
  (g) parse error raises HomeAssistantError. Verify
  cloud schedules appear in results with `source_type`
  of `"2"`.

### Implementation for User Story 1

- [x] T009 [US1] Implement `async list_schedules(self)` on
  `AkuvoxLockEntity` in custom_components/akuvox/lock.py:
  accept optional `page` kwarg, call
  `await self.coordinator.device.list_schedules(page=)`,
  convert each AccessSchedule to dict via `vars()` or
  explicit field mapping, return
  `{"schedules": [list of dicts]}` as ServiceResponse.
  Wrap library exceptions per research.md mapping table
  (AkuvoxValidationError → ServiceValidationError, all
  others → HomeAssistantError). Import ServiceResponse
  type from homeassistant.core.

**Checkpoint**: `list_schedules` returns device schedule data.

---

## Phase 4: User Story 2 — List Users (P1)

**Goal**: Retrieve all device users with PINs/card codes in
plain text for automation consumption, masked in log output.

**Independent Test**: Call `akuvox.list_users`, verify
`private_pin` and `card_code` values are plain text in the
response dict.

### Tests for User Story 2

> **NOTE: Write these tests FIRST, ensure they FAIL**

- [x] T010 [US2] Write failing tests for `list_users` in
  tests/test_services.py: (a) success returns
  `{"users": [...]}` with all User fields including
  plain-text `private_pin` and `card_code`, (b) empty
  user list returns `{"users": []}`, (c) page parameter
  passed through, (d) page number exceeding total pages
  returns empty list, (e) device offline raises
  HomeAssistantError, (f) verify `private_pin` and
  `card_code` are masked as `"****"` in debug log output
  (use caplog fixture). Verify cloud users appear with
  `source_type` of `"2"`.

### Implementation for User Story 2

- [x] T011 [US2] Implement `async list_users(self)` on
  `AkuvoxLockEntity` in custom_components/akuvox/lock.py:
  accept optional `page` kwarg, call
  `await self.coordinator.device.list_users(page=)`,
  convert each User to dict with all fields in plain
  text, log user data at debug level with `private_pin`
  and `card_code` replaced by `"****"`, return
  `{"users": [list of dicts]}`. Wrap exceptions per
  mapping table.

**Checkpoint**: Both P1 list services work — full read-only
device visibility.

---

## Phase 5: User Story 3 — Create Schedule (P2)

**Goal**: Create new access schedules with input validation
and `akuvox_schedule_changed` event firing.

**Independent Test**: Call `akuvox.add_schedule` with valid
params, then `list_schedules` to confirm creation.

### Tests for User Story 3

> **NOTE: Write these tests FIRST, ensure they FAIL**

- [x] T012 [US3] Write failing tests for `add_schedule` in
  tests/test_services.py: (a) success calls
  `device.add_schedule(...)` with correct params,
  (b) invalid `schedule_type` (not "0"/"1"/"2") raises
  ServiceValidationError before device call,
  (c) malformed `time_start`/`time_end` raises
  ServiceValidationError, (d) malformed `date_start`/
  `date_end` raises ServiceValidationError,
  (e) event `akuvox_schedule_changed` fired with
  `{"action": "add", "config_entry_id": entry_id}`,
  (f) device error mapped to HomeAssistantError.

### Implementation for User Story 3

- [x] T013 [US3] Implement `async add_schedule(self, **kwargs)`
  on `AkuvoxLockEntity` in
  custom_components/akuvox/lock.py: validate
  `schedule_type` is in ("0","1","2"), validate
  time/date/week/daily formats per data-model.md rules,
  call `await self.coordinator.device.add_schedule(...)`,
  fire `hass.bus.async_fire(EVENT_SCHEDULE_CHANGED,
  {"action": "add", "config_entry_id": ...})`. Raise
  ServiceValidationError for input errors. Import
  EVENT_SCHEDULE_CHANGED from const.

**Checkpoint**: Can create schedules on device via HA.

---

## Phase 6: User Story 4 — Modify Schedule (P2)

**Goal**: Modify existing schedules with partial updates,
cloud entity protection, and event firing.

**Independent Test**: Modify a schedule field, list to confirm
change persists.

### Tests for User Story 4

> **NOTE: Write these tests FIRST, ensure they FAIL**

- [x] T014 [US4] Write failing tests for `modify_schedule`
  in tests/test_services.py: (a) success passes `id`
  and updated fields to `device.modify_schedule()`,
  (b) cloud-provisioned schedule (source_type `"2"`)
  raises ServiceValidationError "Cannot modify
  cloud-provisioned schedule", (c) non-existent schedule
  ID raises HomeAssistantError, (d) invalid field values
  raise ServiceValidationError, (e) event
  `akuvox_schedule_changed` fired with
  `{"action": "modify", "schedule_id": id,
  "config_entry_id": ...}`.

### Implementation for User Story 4

- [x] T015 [US4] Implement `async modify_schedule(self,
  **kwargs)` on `AkuvoxLockEntity` in
  custom_components/akuvox/lock.py: extract `id` from
  kwargs, fetch schedule list via
  `device.list_schedules()`, find schedule by `id`,
  check `source_type` — reject if `"2"` (cloud),
  validate provided fields, call
  `device.modify_schedule(id=id, ...)`, fire
  `akuvox_schedule_changed` event with action "modify".

**Checkpoint**: Schedule list + add + modify working.

---

## Phase 7: User Story 5 — Delete Schedule (P2)

**Goal**: Delete schedules by ID with cloud entity protection
and event firing.

**Independent Test**: Delete a schedule, list to confirm
removal.

### Tests for User Story 5

> **NOTE: Write these tests FIRST, ensure they FAIL**

- [x] T016 [US5] Write failing tests for `delete_schedule`
  in tests/test_services.py: (a) success calls
  `device.delete_schedule(id=)`, (b) cloud schedule
  raises ServiceValidationError, (c) non-existent
  schedule raises HomeAssistantError, (d) event
  `akuvox_schedule_changed` fired with
  `{"action": "delete", "schedule_id": id, ...}`,
  (e) device error mapped to HomeAssistantError,
  (f) after successful deletion of a schedule referenced
  in existing user schedule_relay assignments, a warning
  about orphaned assignments is logged (use caplog
  fixture); verify no warning is logged when deletion
  fails.

### Implementation for User Story 5

- [x] T017 [US5] Implement `async delete_schedule(self,
  **kwargs)` on `AkuvoxLockEntity` in
  custom_components/akuvox/lock.py: extract `id`, fetch
  schedule list for cloud check, reject if
  cloud-provisioned, call `device.delete_schedule(id=)`,
  then on success fetch user list and log a warning for
  any users whose schedule_relay references the deleted
  schedule ID (orphaned assignment check per EC-5), fire
  `akuvox_schedule_changed` with action "delete".

**Checkpoint**: Complete schedule CRUD lifecycle (P2 done).

---

## Phase 8: User Story 6 — Create User (P3)

**Goal**: Create users with schedule-relay assignment,
optional PIN/card, cloud schedule validation preventing
use of cloud-provisioned schedules.

**Independent Test**: Call `akuvox.add_user` with name,
user_id, schedule_relay, lift_floor_num; list to confirm.

### Tests for User Story 6

> **NOTE: Write these tests FIRST, ensure they FAIL**

- [x] T018 [US6] Write failing tests for `add_user` in
  tests/test_services.py: (a) success with required
  fields (name, user_id, schedule_relay, lift_floor_num)
  calls `device.add_user(...)`, (b) optional
  `private_pin` passed through, (c) optional `card_code`
  passed through, (d) optional `web_relay` passed
  through, (e) PIN shorter than 4 or longer than
  8 digits raises ServiceValidationError, (f) invalid
  `schedule_relay` format raises ServiceValidationError,
  (g) `schedule_relay` referencing cloud schedule raises
  ServiceValidationError "Cannot assign cloud schedule",
  (h) event `akuvox_user_changed` fired with
  `{"action": "add", "config_entry_id": ...,
  "device_user_id": id}` if device returns ID.

### Implementation for User Story 6

- [x] T019 [US6] Implement `async add_user(self, **kwargs)`
  on `AkuvoxLockEntity` in
  custom_components/akuvox/lock.py: validate required
  fields (name, user_id, schedule_relay, lift_floor_num)
  are non-empty, validate `schedule_relay` matches regex
  `^[0-9]+-[0-9]+(,[0-9]+-[0-9]+)*$`, validate `private_pin` is 4-8
  digits if provided, parse schedule IDs from
  `schedule_relay` and fetch schedule list to verify
  none are cloud-provisioned, call
  `device.add_user(...)`, fire `akuvox_user_changed`
  with action "add". Import EVENT_USER_CHANGED from
  const.

**Checkpoint**: Can create users with access assignments.

---

## Phase 9: User Story 7 — Modify User (P3)

**Goal**: Modify existing users with partial updates, cloud
user protection, cloud schedule validation on schedule_relay
changes, and event firing.

**Independent Test**: Modify a user field, list to confirm.

### Tests for User Story 7

> **NOTE: Write these tests FIRST, ensure they FAIL**

- [x] T020 [US7] Write failing tests for `modify_user` in
  tests/test_services.py: (a) success with partial
  update passes `id` and fields to
  `device.modify_user()`, (b) cloud user (source_type
  `"2"`) raises ServiceValidationError "Cannot
  modify cloud-provisioned user", (c) non-existent user
  raises HomeAssistantError, (d) `schedule_relay` update
  with cloud schedule reference raises
  ServiceValidationError, (e) invalid PIN raises
  ServiceValidationError, (f) event
  `akuvox_user_changed` fired with action "modify".

### Implementation for User Story 7

- [x] T021 [US7] Implement `async modify_user(self,
  **kwargs)` on `AkuvoxLockEntity` in
  custom_components/akuvox/lock.py: extract `id`, fetch
  user list, find user, check `source_type` for `"2"`
  (cloud) protection, validate fields, if `schedule_relay`
  provided check referenced schedules against cloud,
  call `device.modify_user(id=id, ...)`, fire
  `akuvox_user_changed` with action "modify".

**Checkpoint**: User list + add + modify working.

---

## Phase 10: User Story 8 — Delete User (P3)

**Goal**: Delete users by device ID with cloud protection and
event firing, regardless of schedule-relay pair count.

**Independent Test**: Delete a user, list to confirm removal.

### Tests for User Story 8

> **NOTE: Write these tests FIRST, ensure they FAIL**

- [x] T022 [US8] Write failing tests for `delete_user` in
  tests/test_services.py: (a) success calls
  `device.delete_user(id=)`, (b) cloud user raises
  ServiceValidationError, (c) non-existent user raises
  HomeAssistantError, (d) event `akuvox_user_changed`
  fired with `{"action": "delete",
  "device_user_id": id, ...}`, (e) device error mapped
  to HomeAssistantError.

### Implementation for User Story 8

- [x] T023 [US8] Implement `async delete_user(self,
  **kwargs)` on `AkuvoxLockEntity` in
  custom_components/akuvox/lock.py: extract `id`, fetch
  user list for cloud check, reject if cloud, call
  `device.delete_user(id=)`, fire `akuvox_user_changed`
  with action "delete".

**Checkpoint**: Complete user CRUD lifecycle (P3 done).

---

## Phase 11: Convenience Services (Schedule-Relay Pairs)

**Purpose**: Add/remove individual schedule-relay pairs on
users via fetch-then-modify on the `schedule_relay` string.
Best-effort; concurrent calls may race.

### Tests for Convenience Services

> **NOTE: Write these tests FIRST, ensure they FAIL**

- [ ] T024 [P] Write failing tests for
  `add_user_schedule_relay` in tests/test_services.py:
  (a) success adds the `"<sid>-<rid>"` pair to the user's
  comma-separated `schedule_relay` string (appending
  `",<sid>-<rid>"` when there is at least one existing pair)
  and calls `device.modify_user()`,
  (b) duplicate pair raises ServiceValidationError
  "Pair already assigned", (c) cloud user raises
  ServiceValidationError, (d) cloud schedule reference
  raises ServiceValidationError, (e) user not found
  raises HomeAssistantError, (f) event fired with
  action "add_schedule_relay".
- [ ] T025 [P] Write failing tests for
  `remove_user_schedule_relay` in tests/test_services.py:
  (a) success removes pair from schedule_relay string
  and calls `device.modify_user()`, (b) pair not found
  raises ServiceValidationError "Pair not assigned",
  (c) removing last pair raises ServiceValidationError
  "Cannot remove last pair", (d) cloud user raises
  ServiceValidationError, (e) user not found raises
  HomeAssistantError, (f) event fired with action
  "remove_schedule_relay".

### Implementation for Convenience Services

- [ ] T026 Implement `async add_user_schedule_relay(self,
  **kwargs)` on `AkuvoxLockEntity` in
  custom_components/akuvox/lock.py: extract `id`,
  `schedule_id`, `relay_id`; fetch user by `id` via
  `device.list_users()`; check cloud user; fetch
  schedule list to check cloud schedule; parse current
  `schedule_relay` string; check for duplicate pair;
  append `"<schedule_id>-<relay_id>"` to pair list and
  rebuild comma-separated string; call
  `device.modify_user(id=id, schedule_relay=updated)`;
  fire `akuvox_user_changed` with action
  "add_schedule_relay" including schedule_id and
  relay_id in event data.
- [ ] T027 Implement `async remove_user_schedule_relay(self,
  **kwargs)` on `AkuvoxLockEntity` in
  custom_components/akuvox/lock.py: extract `id`,
  `schedule_id`, `relay_id`; fetch user; check cloud
  user; parse `schedule_relay` string into pairs; find
  and remove `"<schedule_id>-<relay_id>"` (error if
  not found); error if removal leaves zero pairs; rebuild
  string; call `device.modify_user(id=id,
  schedule_relay=updated)`; fire event with action
  "remove_schedule_relay".

**Checkpoint**: All 10 services implemented and tested.

---

## Phase 12: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and documentation updates.

- [ ] T028 [P] Update .github/agents/copilot-instructions.md
  with implementation completion status for feature 003
- [ ] T029 Run full test suite (`uv run pytest tests/ -x -q`)
  and linters (`uv run ruff check`, `uv run mypy`) to
  verify all checks pass. Note: SC-001 (5s response time)
  and SC-006 (10s error timeout) are deferred to
  integration testing with real hardware; unit tests
  verify error propagation but not timing constraints.
- [ ] T030 Validate quickstart.md service call examples
  against implemented services for accuracy

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 completion
  — BLOCKS all user stories
- **US1-US2 (Phases 3-4)**: Depend on Phase 2; sequential
  recommended (both modify lock.py + test_services.py)
- **US3-US5 (Phases 5-7)**: Depend on Phase 2; sequential
  (modify/delete reuse cloud check pattern from US4)
- **US6-US8 (Phases 8-10)**: Depend on Phase 2; sequential
  (modify/delete reuse cloud check from US7)
- **Convenience (Phase 11)**: Depends on Phase 10 (reuses
  modify_user pattern and cloud check helpers)
- **Polish (Phase 12)**: Depends on all previous phases

### User Story Dependencies

- **US1 (P1)**: Foundation only — independent
- **US2 (P1)**: Foundation only — independent
- **US3 (P2)**: Foundation only — independent
- **US4 (P2)**: Foundation; introduces cloud check pattern
- **US5 (P2)**: Reuses cloud check from US4
- **US6 (P3)**: Foundation; adds cloud schedule check
- **US7 (P3)**: Reuses cloud checks from US4 + US6
- **US8 (P3)**: Reuses cloud check from US7

### Within Each User Story

1. Tests MUST be written and FAIL before implementation
2. Implementation makes tests pass (minimum code)
3. Refactor while keeping tests green
4. Commit atomically after each completed story. A story
   commit includes its tests and implementation together
   as one logical change (the story is the atomic unit).

### Parallel Opportunities

- T002, T003, T004 in parallel (different files)
- T006, T007 in parallel (different files)
- T024, T025 in parallel (independent test suites)
- T028 in parallel with T029, T030

---

## Parallel Example: Phase 1 Setup

```bash
# T001 first (constants needed by everything):
Task T001: "Add constants to const.py"

# Then launch in parallel (different files):
Task T002: "Create services.yaml"
Task T003: "Add strings to strings.json"
Task T004: "Add translations to en.json"
```

## Parallel Example: Phase 2 Foundational

```bash
# After T005 (service registration):
Task T005: "Add async_setup() to __init__.py"

# Then launch in parallel (different files):
Task T006: "Add mock fixtures to conftest.py"
Task T007: "Create test infrastructure in test_services.py"
```

---

## Implementation Strategy

### MVP First (US1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (BLOCKS all stories)
3. Complete Phase 3: US1 — List Schedules
4. **STOP and VALIDATE**: Test independently
5. Deploy/demo read-only schedule visibility

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. US1 + US2 → Read visibility (MVP!)
3. US3 + US4 + US5 → Schedule CRUD
4. US6 + US7 + US8 → User CRUD
5. Convenience → Schedule-relay pair management
6. Each increment adds value without breaking previous

### Single Developer Strategy

Follow phases sequentially in priority order:
P1 (list ops) → P2 (schedule writes) → P3 (user writes)
→ convenience → polish

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to user story for traceability
- TDD mandatory: failing test → implement → refactor
- Each story independently completable and testable
- Commit atomically after each task or logical group.
  A story commit includes tests + implementation together.
- Stop at any checkpoint to validate independently
- Cloud checks: fetch list → find by ID → check
  source_type → reject if `"2"` (cloud)
- PIN/card: plain text in responses, masked in logs
- Events: `akuvox_schedule_changed` /
  `akuvox_user_changed` after write operations
- Convenience services use fetch-then-modify pattern;
  document serial access for concurrent safety
