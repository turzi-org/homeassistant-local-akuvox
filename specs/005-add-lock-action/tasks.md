<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Tasks: Add Lock Action

**Input**: Design documents from `/specs/005-add-lock-action/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md,
contracts/, quickstart.md

**Tests**: Required (constitution mandates TDD).

**Organization**: Tasks are grouped by user story to enable
independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to

## Path Conventions

- **Source**: `custom_components/akuvox/`
- **Tests**: `tests/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Refactor existing code to support both lock and unlock
actions without changing any behavior (SC-005).

- [x] T001 Refactor `_schedule_delayed_refresh` to accept a
  `finish_callback` parameter in
  `custom_components/akuvox/lock.py` (R-004, data-model.md
  §Refactored Method). Default the callback to
  `self._async_finish_optimistic_unlock` for backward
  compatibility. Update docstring accordingly.
- [x] T002 Add `_async_finish_optimistic_lock` method to
  `AkuvoxLockEntity` in `custom_components/akuvox/lock.py`
  (data-model.md §_async_finish_optimistic_lock). Mirrors
  `_async_finish_optimistic_unlock` but with lock-specific log
  message.

**Checkpoint**: Existing unlock behavior unchanged; new callback
infrastructure ready. All existing tests still pass.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Write failing tests that define the expected lock
behavior before any implementation (TDD red phase).

**⚠️ CRITICAL**: No lock implementation can begin until tests are
written and confirmed failing.

### Tests for Refactored Infrastructure

- [ ] T003 [P] Add test for `_schedule_delayed_refresh` backward
  compatibility (default callback calls
  `_async_finish_optimistic_unlock`) in `tests/test_lock.py`.
  Verify existing unlock + delayed refresh behavior is unchanged
  after T001 refactor.
- [ ] T004 [P] Add test for `_schedule_delayed_refresh` with
  explicit `finish_callback` parameter in `tests/test_lock.py`.
  Verify the provided callback is invoked instead of the default.

**Checkpoint**: Infrastructure tests pass; refactored method works
for both lock and unlock callbacks. Existing tests still pass.

---

## Phase 3: User Story 1 — Lock a Bistable Relay (P1) 🎯 MVP

**Goal**: A user can lock a bistable relay that is currently
unlocked. The integration sends a relay command, updates state
optimistically, and schedules a delayed refresh.

**Independent Test**: Unlock a bistable relay, call `lock.lock`,
verify entity returns to locked state and relay command was sent.

### Tests for User Story 1 (TDD red phase)

- [ ] T005 [P] [US1] Add test: bistable relay lock sends
  `trigger_relay` when confirmed unlocked in
  `tests/test_lock.py` (AS-1.1, FR-001, FR-002). Mock
  coordinator refresh to return unlocked state, call
  `lock.lock`, assert `trigger_relay` called with correct
  relay config params.
- [ ] T006 [P] [US1] Add test: bistable relay lock sets
  `_optimistic_locked = True` and calls
  `async_write_ha_state` in `tests/test_lock.py` (FR-003,
  R-002). After successful `trigger_relay`, verify optimistic
  state and HA state write.
- [ ] T007 [P] [US1] Add test: bistable relay lock schedules
  delayed refresh with `hold_delay=0` and
  `_async_finish_optimistic_lock` callback in
  `tests/test_lock.py` (FR-004, R-004). Verify
  `_schedule_delayed_refresh` called with `(0, callback)`.
- [ ] T008 [P] [US1] Add test: bistable relay lock is no-op when
  already locked in `tests/test_lock.py` (AS-1.2, FR-008).
  Mock coordinator refresh to return locked state, call
  `lock.lock`, assert `trigger_relay` NOT called, state
  unchanged.
- [ ] T009 [P] [US1] Add test: bistable relay lock raises
  `HomeAssistantError` on device error in
  `tests/test_lock.py` (AS-1.3, FR-006). Mock `trigger_relay`
  to raise `AkuvoxError`, verify `HomeAssistantError` raised,
  state unchanged.
- [ ] T010 [P] [US1] Add test: bistable relay lock refreshes
  coordinator before state check in `tests/test_lock.py`
  (AS-1.4, FR-009, R-001). Verify
  `coordinator.async_refresh()` called before `is_locked`
  evaluation.
- [ ] T011 [P] [US1] Add test: bistable relay lock cancels
  pending unlock refresh and clears optimistic override in
  `tests/test_lock.py` (FR-005, R-003). Set up pending unlock
  timer, call `lock.lock`, verify timer cancelled and
  `_optimistic_locked` set to `None` before coordinator
  refresh.
- [ ] T012 [P] [US1] Replace `test_async_lock_raises_error` with
  test verifying `lock.lock` no longer raises
  `HomeAssistantError` unconditionally in `tests/test_lock.py`.
  The old stub test must be removed since the lock action now
  works.

### Implementation for User Story 1

- [ ] T013 [US1] Implement `async_lock` for bistable relays in
  `custom_components/akuvox/lock.py` (FR-001, FR-002, FR-003,
  FR-004, FR-005, FR-006, FR-008, FR-009). Replace the stub
  with mode-aware logic per data-model.md §Bistable Relay Lock
  Flow. For bistable path: cancel pending unlock refresh +
  clear optimistic override → coordinator refresh → check
  `is_locked` → if unlocked: `trigger_relay`, set
  `_optimistic_locked = True`, `async_write_ha_state`,
  `_schedule_delayed_refresh(0, _async_finish_optimistic_lock)`.
  If already locked after refresh: return (no-op, FR-008).

**Checkpoint**: Bistable lock fully functional and independently
testable. All US1 tests pass. Existing unlock tests still pass.

---

## Phase 4: User Story 2 — Lock on Auto-Close Relay (P2)

**Goal**: A user calls lock on an auto-close relay. No command is
sent; only a state refresh occurs. Pending unlock timers are
preserved.

**Independent Test**: Unlock an auto-close relay, call `lock.lock`,
verify no command sent and entity state reflects device state from
refresh.

### Tests for User Story 2 (TDD red phase)

- [ ] T014 [P] [US2] Add test: auto-close relay lock does NOT
  send `trigger_relay` in `tests/test_lock.py` (AS-2.1,
  FR-008, R-005). Mock coordinator refresh, call `lock.lock`,
  assert `trigger_relay` NOT called.
- [ ] T015 [P] [US2] Add test: auto-close relay lock performs
  coordinator refresh in `tests/test_lock.py` (FR-004,
  FR-009). Verify `coordinator.async_refresh()` called.
- [ ] T016 [P] [US2] Add test: auto-close relay lock does NOT
  cancel pending unlock refresh in `tests/test_lock.py`
  (FR-005). Set up pending unlock timer, call `lock.lock`,
  verify timer NOT cancelled.
- [ ] T017 [P] [US2] Add test: auto-close relay lock when already
  locked is a no-op in `tests/test_lock.py` (AS-2.2). Mock
  coordinator refresh returning locked state, assert no command,
  no state change.
- [ ] T018 [P] [US2] Add test: auto-close relay lock does NOT
  set optimistic state in `tests/test_lock.py` (R-002). Verify
  `_optimistic_locked` remains unchanged after lock call.

### Implementation for User Story 2

- [ ] T019 [US2] Add auto-close early-return branch to
  `async_lock` in `custom_components/akuvox/lock.py` (FR-007,
  FR-008, R-005, R-006). Per data-model.md §Auto-Close Relay
  Lock Flow: skip timer cancellation → coordinator refresh →
  `async_write_ha_state` → return. No command, no optimistic
  state.

**Checkpoint**: Both bistable and auto-close lock work correctly.
All US1 and US2 tests pass. Existing unlock tests still pass.

---

## Phase 5: User Story 3 — Lock in Automations (P2)

**Goal**: The `lock.lock` service works identically from UI,
service calls, and automations.

**Independent Test**: Call `lock.lock` via the HA service API and
verify it completes successfully.

### Tests for User Story 3 (TDD red phase)

- [ ] T020 [P] [US3] Add test: `lock.lock` service call succeeds
  on bistable relay in `tests/test_lock.py` (AS-3.1). Use
  `hass.services.async_call("lock", "lock", ...)` with
  `blocking=True`, verify no exception and state updated.
- [ ] T021 [P] [US3] Add test: `lock.lock` service call succeeds
  on auto-close relay in `tests/test_lock.py` (AS-3.1). Use
  `hass.services.async_call("lock", "lock", ...)` with
  `blocking=True`, verify no exception.

### Implementation for User Story 3

No additional implementation needed. US3 is satisfied by the
`async_lock` method implemented in US1/US2, which the HA service
dispatcher already calls. The tests validate this integration
point.

**Checkpoint**: Service-call tests pass. `lock.lock` works from
any HA call site (UI, service, automation).

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Edge cases, regression verification, and cleanup.

- [ ] T022 [P] Add test: lock during active unlock window
  (bistable) in `tests/test_lock.py` (Edge Case 1). Unlock,
  then immediately lock before hold_delay expires. Verify
  pending unlock refresh cancelled, lock command sent, new
  refresh scheduled.
- [ ] T023 [P] Add test: rapid lock-lock is idempotent in
  `tests/test_lock.py` (Edge Case 3). Call lock twice in
  succession on bistable relay, verify only one command sent.
- [ ] T024 [P] Add test: lock completes within 5 seconds
  (bistable) in `tests/test_lock.py` (SC-002). Similar to
  existing `test_async_unlock_completes_within_5s`.
- [ ] T025 [P] Add test: existing unlock behavior unchanged
  (SC-005) in `tests/test_lock.py`. Re-run existing unlock
  test suite; verify no regressions from refactored
  `_schedule_delayed_refresh`.
- [ ] T026 [P] Add test: bistable relay lock proceeds when state
  is unknown (None) after coordinator refresh in
  `tests/test_lock.py` (data-model.md §Bistable Relay Lock
  Flow, unknown state handling). Mock coordinator refresh to
  return state where `is_locked` is None, verify
  `trigger_relay` is called (treats unknown as unlocked per
  design decision).
- [ ] T027 Verify all tests pass and linting is clean:
  `uv run pytest tests/test_lock.py -x -q`,
  `uv run ruff check custom_components/ tests/`, and
  `uv run mypy custom_components/`
- [ ] T028 Run quickstart.md manual verification steps to
  validate end-to-end behavior description is accurate.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 (T001, T002)
- **User Story 1 (Phase 3)**: Depends on Phase 2 (tests written)
- **User Story 2 (Phase 4)**: Depends on Phase 3 (bistable path
  implemented; auto-close branch added to same method)
- **User Story 3 (Phase 5)**: Depends on Phases 3 and 4
- **Polish (Phase 6)**: Depends on all user stories complete

### User Story Dependencies

- **US1 (P1)**: Depends on Phase 2 — core implementation
- **US2 (P2)**: Depends on US1 — adds branch to `async_lock`
- **US3 (P2)**: Depends on US1 + US2 — validates integration

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Implementation makes tests pass (TDD green phase)
- Refactor if needed (TDD refactor phase)

### Parallel Opportunities

- T001 and T002 (Phase 1): Sequential — T002 is independent but
  both touch same file, commit atomically
- T003 and T004 (Phase 2): Parallel — independent test functions
- T005–T012 (US1 tests): All parallel — independent test
  functions in same file
- T014–T018 (US2 tests): All parallel — independent test
  functions in same file
- T020–T021 (US3 tests): Parallel — independent test functions
- T022–T026 (Polish tests): All parallel — independent tests

---

## Parallel Example: User Story 1

```text
# Write all US1 tests in parallel (TDD red phase):
T005: bistable lock sends trigger_relay
T006: bistable lock sets optimistic state
T007: bistable lock schedules delayed refresh
T008: bistable lock no-op when locked
T009: bistable lock raises on device error
T010: bistable lock refreshes coordinator first
T011: bistable lock cancels pending unlock refresh
T012: replace old lock-raises-error test

# Then implement (single task, TDD green phase):
T013: implement async_lock bistable path
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Refactor `_schedule_delayed_refresh`
2. Complete Phase 2: Infrastructure tests
3. Complete Phase 3: Bistable lock tests + implementation
4. **STOP and VALIDATE**: All tests pass, linting clean

### Incremental Delivery

1. Phase 1 + 2 → Infrastructure ready
2. Add US1 (Phase 3) → Bistable lock works → Validate
3. Add US2 (Phase 4) → Auto-close lock works → Validate
4. Add US3 (Phase 5) → Service-call integration → Validate
5. Phase 6 → Edge cases, regression, polish → Final validation

---

## Notes

- All changes are in two files: `lock.py` and `test_lock.py`
- [P] tasks = different test functions, no dependencies
- TDD is mandatory per constitution (Principle II)
- Commit after each phase or logical group
- Stop at any checkpoint to validate independently
- The existing `test_async_lock_raises_error` must be replaced
  (T012) since the lock stub is being replaced with real logic
