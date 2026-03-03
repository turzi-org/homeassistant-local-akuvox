<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Tasks: Webhook Endpoint

**Input**: Design documents from `/specs/004-webhook-endpoint/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md,
contracts/

**Tests**: Included per constitution principle II (TDD). Tests
are written first and must fail before implementation.

**Organization**: Tasks grouped by user story to enable
independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no deps)
- **[Story]**: US1, US2, US3 (maps to spec.md user stories)
- Exact file paths included in all descriptions

## Path Conventions

- **Integration code**: `custom_components/akuvox/`
- **Tests**: `tests/`

---

## Phase 1: Setup

**Purpose**: Verify baseline and prepare for feature work

- [ ] T001 Verify all existing tests pass with
  `uv run pytest tests/ -x -q`
- [ ] T002 Verify linting passes with
  `uv run ruff check custom_components/ tests/`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared constants, coordinator extension, and test
fixtures that ALL user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this
phase is complete

### Tests for Foundational

- [ ] T003 [P] Extend tests for coordinator user cache in
  `tests/test_coordinator.py` — add tests that
  `AkuvoxCoordinatorData` includes a `users` field populated
  from `device.list_users(page=None)` during
  `_async_update_data()`, and that PIN→user lookup works
  against the cached data

### Implementation for Foundational

- [ ] T004 [P] Add webhook constants to
  `custom_components/akuvox/const.py` — add
  `CONF_WEBHOOK_ID`, `CONF_WEBHOOK_ENABLED`,
  `EVENT_WEBHOOK_RECEIVED` (`akuvox_webhook_received`),
  `ACTIONURL_KEYS` dict mapping all 10 action URL config
  key names, `KNOWN_EVENT_TYPES` frozenset, and
  `REFRESH_EVENT_TYPES` frozenset (relay + valid_code events)
- [ ] T005 [P] Extend coordinator user cache in
  `custom_components/akuvox/coordinator.py` — add a `users`
  field (or PIN→user map keyed by `private_pin`) to
  `AkuvoxCoordinatorData`, populate it from
  `device.list_users(page=None)` in `_async_update_data()`
- [ ] T006 [P] Add webhook test fixtures to
  `tests/conftest.py` — add fixtures for mock webhook
  requests (aiohttp test requests with query params),
  mock coordinator with user cache, sample webhook_id,
  and sample config entry with webhook fields

**Checkpoint**: Constants, coordinator cache, and test
fixtures ready — user story implementation can begin

---

## Phase 3: User Story 1 — Receive Device Events (P1) 🎯 MVP

**Goal**: Integration receives HTTP GET webhooks from the
Akuvox device, parses query parameters, resolves user
identity for code events, fires HA events on the bus, and
triggers coordinator refresh for relay/code events

**Independent Test**: Send simulated GET requests to
`/api/webhook/{id}` and verify HA events fire with correct
`device_id`, `config_entry_id`, `event_type`, and `payload`

### Tests for User Story 1

> **NOTE**: Write these tests FIRST, ensure they FAIL
> before implementation

- [ ] T007 [P] [US1] Write sanitization unit tests in
  `tests/test_sanitize.py` — test `sanitize_payload()`:
  sensitive key masking (contains-match for token, secret,
  password, authorization, auth, key, cookie, code),
  webhook ID substring replacement (64-char and ≤8-char
  cases), field truncation at 1024 chars, original dict
  not mutated; test `mask_webhook_id()` output format
- [ ] T008 [P] [US1] Write webhook handler tests in
  `tests/test_webhook.py` — test `async_handle_webhook()`:
  valid known event (relay_a_triggered with status), valid
  code event (user lookup from cache hit, cache miss with
  fallback, no match → None fields), invalid code event
  (no code param, None identity), unknown event (sanitized
  payload only), missing event param → 400, webhook_id not
  in registry → 200 empty, coordinator missing → 200 empty,
  coordinator refresh scheduled for relay/code events but
  NOT for input/invalid events; verify raw PIN never in
  event payload; test rapid-fire concurrent deliveries
  (FR-014) — multiple simultaneous requests processed
  independently without event loss
- [ ] T009 [P] [US1] Write webhook lifecycle tests in
  `tests/test_init.py` — test `async_setup_entry()`:
  webhook registered when `webhook_enabled=True`, not
  registered when `False`; test `async_unload_entry()`:
  webhook unregistered when in registry (gated on
  `unload_ok`), registry entry removed, `hass.data`
  cleanup when empty; test registry race condition
  (webhook_id present but not in registry → safe no-op)

### Implementation for User Story 1

- [ ] T010 [P] [US1] Create `sanitize.py` module at
  `custom_components/akuvox/sanitize.py` — implement
  `sanitize_payload(payload, webhook_id=None)` per
  contracts/payload-sanitization.md: sensitive field
  masking with contains-match, webhook ID substring
  replacement, field truncation at 1024 chars, returns
  new dict; implement `mask_webhook_id(webhook_id)` helper
- [ ] T011 [US1] Create `webhook.py` module at
  `custom_components/akuvox/webhook.py` — implement:
  (a) `async_handle_webhook(hass, webhook_id, request)`
  per contracts/webhook-handler.md 8-step processing;
  (b) `async_register_webhook(hass, entry)` using
  `async_register()` with `allowed_methods=["GET"]`,
  adds to webhook_registry after success;
  (c) `async_unregister_webhook(hass, entry)` using
  `async_unregister()`, removes from registry;
  (d) `build_action_urls(hass, webhook_id)` returning
  enable and disable payload dicts per
  contracts/config-flow-webhook.md;
  (e) unknown event normalization (lowercase, replace
  non-alnum with `_`, collapse, trim, truncate 32 chars)
- [ ] T012 [US1] Wire webhook lifecycle into
  `custom_components/akuvox/__init__.py` — in
  `async_setup_entry()`: init webhook_registry via
  `hass.data.setdefault()`, call
  `async_register_webhook()` when `webhook_enabled=True`;
  in `async_unload_entry()`: call
  `async_unregister_webhook()` gated on `unload_ok` and
  registry presence (not `webhook_enabled` flag), pop
  registry entry, clean up empty registry/DOMAIN dicts

**Checkpoint**: Webhook endpoint receives events, fires
on HA bus, resolves user identity, triggers coordinator
refresh. Fully testable with simulated GET requests.

---

## Phase 4: User Story 2 — Configure Webhook During Setup (P2)

**Goal**: Config flow presents a webhook toggle after
connection test; if enabled, pushes action URLs to device
and stores webhook_id in config entry

**Independent Test**: Walk through config flow with webhook
enabled, verify device receives action URL config push and
config entry contains `webhook_id` + `webhook_enabled=True`

**Depends on**: US1 (webhook registration in setup_entry)

### Tests for User Story 2

> **NOTE**: Write these tests FIRST, ensure they FAIL
> before implementation

- [ ] T013 [P] [US2] Write config flow webhook step tests in
  `tests/test_config_flow.py` — test new webhook step:
  enable path (generates webhook_id, pushes 10 URLs +
  Enable + Method to device, stores in entry data), skip
  path (webhook_id=None, webhook_enabled=False, no device
  push), push failure path (error shown, retry/skip
  options); verify HTTPS warning logged when URL scheme
  is HTTP

### Implementation for User Story 2

- [ ] T014 [US2] Add webhook step to config flow in
  `custom_components/akuvox/config_flow.py` — add
  `async_step_webhook()` after connection test step: show
  `CONF_WEBHOOK_ENABLED` toggle (default False), if
  enabled: generate `webhook_id=secrets.token_hex(32)`,
  build action URLs via `build_action_urls()`, open new
  `AkuvoxDevice` connection, push enable payload via
  `device.set_device_config()`, store webhook_id and
  webhook_enabled in entry data; if skipped: store
  None/False; handle `webhook_push_failed` error with
  retry/skip; log HTTPS warning per
  contracts/config-flow-webhook.md
- [ ] T015 [P] [US2] Add webhook UI strings to
  `custom_components/akuvox/strings.json` — add
  `step.webhook.title`, `step.webhook.description`,
  `step.webhook.data.webhook_enabled` label, and
  `error.webhook_push_failed` message
- [ ] T016 [P] [US2] Add webhook translations to
  `custom_components/akuvox/translations/en.json` —
  mirror all webhook strings from `strings.json`

**Checkpoint**: New integrations can enable webhooks during
setup; device receives action URL configuration
automatically

---

## Phase 5: User Story 3 — Manage Webhook via Reconfiguration (P3)

**Goal**: Options flow lets users toggle webhook on/off;
enable pushes action URLs, disable pushes empty URLs;
integration removal sends disable payload to device

**Independent Test**: Reconfigure existing entry to toggle
webhook on and off, verify device config updated each time
and webhook endpoint registered/unregistered on reload

**Depends on**: US1 (webhook lifecycle), US2 (initial
webhook config entry data)

### Tests for User Story 3

> **NOTE**: Write these tests FIRST, ensure they FAIL
> before implementation

- [ ] T017 [P] [US3] Write options flow webhook toggle tests
  in `tests/test_config_flow.py` — test enable path: reuse
  existing webhook_id if present, generate new if None,
  push 10 URLs + Enable=1 + Method='', update entry
  options; test disable path: push empty URLs +
  Enable=0 + Method='', preserve webhook_id; test no-change
  path: no device push; test push failure: error shown,
  cancel preserves previous state; verify options flow does
  NOT inline-register/unregister webhook
- [ ] T018 [P] [US3] Write async_remove_entry tests in
  `tests/test_init.py` — test removal with webhooks enabled:
  pushes disable payload to device (best-effort); test
  removal with webhooks disabled: no device push; test
  device unreachable during removal: warning logged, removal
  not blocked

### Implementation for User Story 3

- [ ] T019 [US3] Add webhook toggle to options flow in
  `custom_components/akuvox/config_flow.py` — add
  `CONF_WEBHOOK_ENABLED` to options schema with current
  value as default; on enable: reuse webhook_id via
  `_get_config_value()` or generate new, build and push
  enable payload, update entry options; on disable: push
  disable payload, update entry with
  `webhook_enabled=False` (preserve webhook_id); handle
  `webhook_push_failed` per
  contracts/config-flow-webhook.md error semantics
- [ ] T020 [US3] Add `async_remove_entry()` hook to
  `custom_components/akuvox/__init__.py` — if
  `webhook_enabled=True` and `webhook_id` not None:
  open `AkuvoxDevice` connection, push disable payload
  via `device.set_device_config()`, log warning on
  failure; this is best-effort only (HA calls unload
  before remove, so webhook is already unregistered)

**Checkpoint**: Users can toggle webhooks on/off via
options; integration removal cleans up device config

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final validation, edge cases, documentation

- [ ] T021 [P] Verify `custom_components/akuvox/manifest.json`
  — confirm no `iot_class` change needed (polling remains
  active alongside optional webhooks); no new dependencies
  or manifest keys expected unless HA requires explicit
  webhook declaration in a future version
- [ ] T022 Run full test suite with
  `uv run pytest tests/ -x -q` and verify all tests pass
- [ ] T023 Run full lint suite with
  `uv run ruff check custom_components/ tests/` and
  `uv run mypy custom_components/` and verify clean
- [ ] T024 Run quickstart.md validation: verify all files
  listed in New Files and Modified Existing Files exist
  and match the documented purpose

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS
  all user stories
- **US1 (Phase 3)**: Depends on Foundational
- **US2 (Phase 4)**: Depends on US1 (webhook registration
  must exist in setup_entry)
- **US3 (Phase 5)**: Depends on US1 and US2 (options flow
  modifies config that US1 uses; US2 creates initial
  webhook config entry fields)
- **Polish (Phase 6)**: Depends on all user stories

### User Story Dependencies

- **US1 (P1)**: Start after Foundational — no story deps
- **US2 (P2)**: Start after US1 — config flow webhook step
  stores data that setup_entry reads to register webhook
- **US3 (P3)**: Start after US2 — options flow modifies
  the same config fields US2 creates

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Sanitize module before webhook module (US1)
- Webhook module before `__init__.py` lifecycle (US1)
- Config flow step before UI strings (US2, but strings
  can be parallel with step implementation)

### Parallel Opportunities

- T003, T004, T005, T006 (Phase 2) can all run in parallel
- T007, T008, T009 (US1 tests) can all run in parallel
- T010 starts after T007 (its test) is written and failing;
  T011 depends on T010 (webhook.py imports sanitize.py)
- T013 (US2 tests) can run alone (single file)
- T015, T016 (US2 strings) can run in parallel with each
  other and with T014
- T017, T018 (US3 tests) can run in parallel

---

## Parallel Example: User Story 1

```text
# Launch all US1 tests together (must fail initially):
Task T007: "Write sanitization tests in tests/test_sanitize.py"
Task T008: "Write webhook handler tests in tests/test_webhook.py"
Task T009: "Write webhook lifecycle tests in tests/test_init.py"

# Then implement sequentially (T011 after T010):
Task T010: "Create sanitize.py module"
Task T011: "Create webhook.py module" (after T010)

# Then wire lifecycle (depends on T011):
Task T012: "Wire webhook into __init__.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (verify baseline)
2. Complete Phase 2: Foundational (constants, coordinator
   cache, fixtures)
3. Complete Phase 3: User Story 1 (sanitize, webhook,
   lifecycle)
4. **STOP and VALIDATE**: Send simulated webhooks, verify
   HA events fire correctly
5. Integration can receive webhooks if user manually
   configures action URLs on the device

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. US1 → Test → Validate (MVP: webhook receiving works)
3. US2 → Test → Validate (config flow pushes URLs)
4. US3 → Test → Validate (options flow toggle + removal)
5. Polish → Full validation → Release

### Single Developer Strategy

Complete phases sequentially: 1 → 2 → 3 → 4 → 5 → 6.
Within each phase, use [P] markers to identify tasks
that can be done in any order. Write all tests for a
story first, then implement until tests pass.

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to user story for traceability
- Each user story independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group per constitution
- Stop at any checkpoint to validate story independently
- Raw PINs MUST NEVER appear in event payloads or logs
  (FR-013 sanitization applies everywhere)
- All webhook handler code MUST be async and non-blocking
- `_get_config_value()` helper MUST be used for reading
  webhook_id and webhook_enabled (checks options first,
  then data)
