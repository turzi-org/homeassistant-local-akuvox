<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Feature Specification: Add Lock Action

**Feature Branch**: `005-add-lock-action`
**Created**: 2026-03-04
**Status**: Draft
**Input**: User description: "Create a lock action similar to the unlock
action that already exists on the lock / relay entities. This is needed
as a relay may be configured in a bistable manner which means that for
us to force the lock to relock, we need a lock action."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Lock a Bistable Relay (Priority: P1)

A Home Assistant user has an Akuvox relay configured in bistable
(manual) mode. After unlocking the relay, the door remains unlocked
indefinitely because the relay does not auto-close. The user triggers
the lock action (via the UI "Lock" button, the `lock.lock` service,
or an automation) and the integration sends a lock command to the
relay, causing it to return to the locked state. The lock entity
state updates to reflect the change.

**Why this priority**: This is the core use case. Without a lock
action, bistable relays cannot be re-locked through Home Assistant,
leaving the door permanently unlocked after an unlock command.

**Independent Test**: Can be fully tested by unlocking a bistable
relay, then calling the lock action and verifying the entity returns
to the locked state and the physical relay toggles.

**Acceptance Scenarios**:

1. **Given** a relay is configured in bistable (manual) mode and is
   currently unlocked, **When** the user triggers the lock action,
   **Then** the integration sends a lock command to the device and
   the lock entity state updates to locked.
2. **Given** a relay is configured in bistable mode and is currently
   locked, **When** the user triggers the lock action, **Then** the
   integration MUST NOT send a command and the lock entity state
   remains locked.
3. **Given** a relay is configured in bistable mode, **When** the
   lock action fails due to a device communication error, **Then**
   the integration raises an error and the entity state remains
   unchanged.
4. **Given** a bistable relay's state has been changed externally
   (for example, toggled by another system), **When** the user
   triggers the lock action, **Then** the integration refreshes
   the device state before deciding whether to send a command.

---

### User Story 2 - Lock Action on Auto-Close Relay (Priority: P2)

A Home Assistant user has an Akuvox relay configured in auto-close
(monostable) mode. The relay hardware automatically returns to the
locked state after the hold delay expires. The user triggers the lock
action. Since the relay will auto-close on its own, the lock action
sends a command to the relay to initiate re-locking rather than
waiting for the hold delay to expire.

**Why this priority**: While auto-close relays eventually re-lock on
their own, supporting the lock action on them provides a consistent
user experience across all relay modes and allows users to force an
immediate re-lock if needed.

**Independent Test**: Can be tested by unlocking an auto-close relay,
immediately calling the lock action, and verifying the lock command is
sent and the entity state updates to locked without waiting for the
hold delay.

**Acceptance Scenarios**:

1. **Given** a relay is configured in auto-close (monostable) mode
   and is currently unlocked, **When** the user triggers the lock
   action, **Then** the integration sends a lock command and the
   lock entity state updates to locked.
2. **Given** a relay is configured in auto-close mode and is
   currently locked (hold delay already expired), **When** the user
   triggers the lock action, **Then** the action succeeds as a no-op
   without sending a new command, and the entity state remains
   locked.

---

### User Story 3 - Lock Action in Automations (Priority: P2)

A Home Assistant user creates an automation that automatically
re-locks a bistable relay after a set period. For example, an
automation triggers the lock action 60 seconds after an unlock
event. The lock action works identically whether called from the
UI, a service call, or an automation.

**Why this priority**: Automations are essential for hands-free
security. Without a working lock action, users cannot automate
re-locking of bistable relays.

**Independent Test**: Can be tested by creating an automation that
calls `lock.lock` on the entity and verifying it completes
successfully.

**Acceptance Scenarios**:

1. **Given** an automation calls the `lock.lock` service on an
   Akuvox lock entity, **When** the automation fires, **Then** the
   lock action executes successfully and the entity state updates.

---

### Edge Cases

- What happens when the lock action is called while an unlock
  operation is still in progress (unlock hold window active)?
  The lock action should cancel any pending state refresh and
  proceed with the lock command.
- What happens when the lock action is called on a relay that is
  already locked?
  - For **bistable** relays (where the relay toggles on each
    command), the lock action MUST NOT send a command when the
    current state is already locked, to avoid unintentionally
    unlocking the door. The action is a no-op.
  - For **auto-close** relays, the lock action MUST also be a
    no-op when already locked, to avoid momentarily unlocking the
    door for the hold window duration.
- What happens when rapid lock/unlock commands are issued? Only
  state-changing commands should be sent to the device; idempotent
  calls that would not change the current state (for example,
  locking when already locked) MUST be treated as no-ops. The
  most recent intended state should be reflected in the entity.
- What happens when the device is unreachable during a lock action?
  The integration should raise a clear error and leave the entity
  state unchanged.
- What happens when the locally known state is stale or unknown
  (for example, the device was toggled externally)? For bistable
  relays, the integration should refresh the device state before
  sending a lock command, to avoid acting on stale information.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a lock action on all Akuvox
  lock entities that sends a lock command to the device.
- **FR-002**: The lock action MUST use the same relay command and
  existing relay configuration as the unlock action, so that lock
  and unlock behave consistently for each relay.
- **FR-003**: The lock action MUST update the entity state to locked
  immediately after a successful device command, so the UI reflects
  the change without waiting for a poll cycle.
- **FR-004**: The lock action MUST schedule a delayed state refresh
  after the hold delay expires, matching the pattern used by the
  unlock action, to synchronize the entity state with the actual
  device state.
- **FR-005**: The lock action MUST cancel any pending state refresh
  from a previous unlock before proceeding, to avoid stale state
  updates.
- **FR-006**: The lock action MUST raise a clear error if the device
  communication fails, without modifying the entity's current state.
- **FR-007**: The lock action MUST work on relays in both bistable
  (manual) and auto-close (monostable) modes.
- **FR-008**: The lock action MUST be a no-op when the relay is
  already in the locked state, to prevent unintentionally toggling
  a bistable relay to unlocked or momentarily unlocking an
  auto-close relay.
- **FR-009**: For bistable relays, before sending a lock command,
  the lock action MUST confirm the current device state is not
  stale (for example, by refreshing from the device) to avoid
  acting on outdated local state.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can re-lock any Akuvox relay entity through the
  standard Home Assistant lock interface (UI, service call, or
  automation) without errors.
- **SC-002**: After triggering the lock action, the entity state
  updates to "locked" within 1 second in the Home Assistant UI.
- **SC-003**: The lock action completes successfully on both bistable
  and auto-close relay configurations.
- **SC-004**: When the device is unreachable, the lock action fails
  with a descriptive error message and the entity state remains
  unchanged.
- **SC-005**: Existing unlock functionality continues to work
  identically after the lock action is added (no regressions).

## Assumptions

- The Akuvox device uses the same relay command for both locking and
  unlocking.
  - For **bistable (manual) relays**, the relay toggles its state on
    each command; a second command returns the relay to its previous
    state (locked).
  - For **auto-close (monostable) relays**, a command initiates an
    unlock window for the configured hold delay period rather than
    performing a simple toggle. The behavior of repeated commands
    during this window is device-specific (some devices may reset
    immediately, others may extend or restart the hold window), so
    the implementation must validate actual behavior for the target
    device.
- The existing relay configuration (hold delay, relay type, relay
  mode) is sufficient for the lock action; no additional device
  configuration is needed.
- State management for the lock action mirrors the unlock action
  pattern: update the entity state immediately, then schedule a
  state refresh after the hold delay to reconcile with device truth.
