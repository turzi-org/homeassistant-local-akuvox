<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Research: Add Lock Action

## R-001: State Refresh Before Lock Command (FR-009)

**Question**: How should the lock action validate device state before
deciding whether to send a command?

**Decision**: Call `self.coordinator.async_refresh()` before evaluating
the relay state. This reuses the existing coordinator refresh mechanism
and ensures the `is_locked` property reflects actual device state, not
a stale cached value.

**Rationale**: The coordinator already fetches device state via the
pylocal-akuvox library. A refresh before the lock action ensures the
no-op decision (FR-008) is based on confirmed device state. This is
the same approach used implicitly by `_async_finish_optimistic_unlock`.

**Alternatives considered**:

- **Direct device query** (bypass coordinator): Rejected because it
  would duplicate state management and could cause the coordinator
  cache and entity state to diverge.
- **Trust local state** (skip refresh): Rejected because FR-009
  explicitly requires stale-state validation. A bistable relay toggled
  externally could have stale local state, and acting on it would
  toggle the relay to the wrong state.

---

## R-002: Optimistic State for Lock Action (FR-003)

**Question**: Should the lock action use the same optimistic state
pattern as the unlock action?

**Decision**: Yes, for bistable relays only. Set
`_optimistic_locked = True` after a successful `trigger_relay` call,
then clear it via a delayed refresh (mirroring the unlock pattern).
For auto-close relays, no optimistic state is set because no command
is sent.

**Rationale**: The unlock action sets `_optimistic_locked = False`
after a successful relay trigger, then clears the override via
`_async_finish_optimistic_unlock()`. The lock action mirrors this
by setting `_optimistic_locked = True`, providing immediate UI
feedback. The delayed refresh reconciles with device truth.

**Alternatives considered**:

- **No optimistic state** (wait for refresh): Rejected because the
  coordinator poll cycle is 30 seconds and SC-002 requires state
  update within 5 seconds.
- **Optimistic state for auto-close too**: Rejected because no
  command is sent for auto-close relays; setting optimistic locked
  state would be incorrect if the device is actually still in its
  unlock window.

---

## R-003: Clearing Optimistic-Unlock Override (FR-005)

**Question**: When the lock action cancels a pending unlock refresh,
how should it handle the `_optimistic_locked = False` override from
the previous unlock?

**Decision**: Cancel the pending delayed refresh timer, then clear
the optimistic override by setting `_optimistic_locked = None`
before proceeding with the lock action's own state management. This
ensures the stale unlock-optimistic state does not persist.

**Rationale**: Per FR-005 and the spec 004 data model, the delayed
refresh from unlock is responsible for clearing `_optimistic_locked`
via `_async_finish_optimistic_unlock()`. If the lock action cancels
that timer, it must also clear the override. Setting to `None` before
the coordinator refresh (FR-009) ensures `is_locked` reads from
device state during the pre-action validation.

**Alternatives considered**:

- **Leave override and let lock set it**: Rejected because the
  coordinator refresh in FR-009 needs `_optimistic_locked = None`
  to read actual device state, not the stale unlock override.
- **Call `_async_finish_optimistic_unlock()` directly**: Rejected
  because it would trigger a redundant coordinator refresh (the
  lock action already refreshes per FR-009).

---

## R-004: Delayed Refresh Interval for Lock (FR-004)

**Question**: What delay should be used for the post-lock state
refresh on bistable relays?

**Decision**: Reuse `_RELAY_REFRESH_BUFFER_SECONDS` (currently 1
second) as the delay for the post-lock refresh by calling
`_schedule_delayed_refresh(hold_delay=0,
finish_callback=self._async_finish_optimistic_lock)`.
The existing method computes `hold_delay + _RELAY_REFRESH_BUFFER_SECONDS`,
so passing 0 yields a 1-second delay. The method must be refactored
to accept a `finish_callback` parameter because it is currently
hardcoded to call `_async_finish_optimistic_unlock`; the lock action
needs to call `_async_finish_optimistic_lock` instead. Unlike unlock,
where the delay is `hold_delay + buffer` to wait for auto-close,
the lock action on bistable relays takes effect immediately — a
short buffer is sufficient.

**Rationale**: The bistable relay toggles instantly on command; the
refresh only needs enough delay for the device to report the new
state. The existing 1-second buffer constant is appropriate. The
unlock pattern uses `hold_delay + buffer` because it waits for
auto-close expiry, but that logic does not apply to a bistable lock
(the relay state changes immediately).

**Alternatives considered**:

- **Same `hold_delay + buffer` as unlock**: Rejected because bistable
  lock takes effect immediately; waiting `hold_delay` seconds would
  unnecessarily delay state reconciliation.
- **Zero delay (synchronous refresh)**: Rejected because a brief
  buffer avoids a race condition where the device has not yet
  committed the state change when the refresh fires.
- **Configurable delay**: Rejected for initial implementation; the
  spec says "implementation should define a sensible default" and
  1 second is sensible. Can be made configurable later if needed.

---

## R-005: Auto-Close Relay Lock Behavior (FR-008)

**Question**: How should the lock action behave on auto-close relays?

**Decision**: Perform a synchronous coordinator refresh and return
without sending any relay command or setting optimistic state. Do not
cancel any pending unlock refresh timers (FR-005).

**Rationale**: Per the spec, sending a command to an auto-close relay
always initiates or extends an unlock window — it never forces a lock.
The lock action on auto-close relays serves only as a state refresh
to let users/automations confirm current device state. Pending unlock
refresh timers must be preserved because they are responsible for
clearing the unlock-optimistic override and detecting when the device
auto-closes.

**Alternatives considered**:

- **Send command anyway**: Rejected; violates FR-008 and could extend
  the unlock window (security risk).
- **No-op without refresh**: Rejected because a state refresh is
  useful for confirming the device has auto-closed, especially when
  the hold delay has expired but no refresh has run yet.

---

## R-006: Method Structure

**Question**: Should the lock action be a single method or split into
helper methods?

**Decision**: Implement as a single `async_lock` method with an early
return branch for auto-close relays. The method is small enough that
splitting would add indirection without reducing complexity.

**Rationale**: The method has two code paths (bistable vs auto-close)
but each path is short (5-10 lines). The cyclomatic complexity stays
well under the constitution's limit of 10. If the method grows during
implementation, it can be refactored.

**Alternatives considered**:

- **Separate `_async_lock_bistable` and `_async_lock_autoclose`
  helpers**: Rejected for now; premature extraction. The two paths
  share the initial relay config lookup and FR-009 refresh.
