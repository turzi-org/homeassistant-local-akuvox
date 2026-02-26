<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Feature Specification: Device Config Discovery

**Feature Branch**: `002-device-config-discovery`
**Created**: 2026-02-25
**Status**: Draft
**Input**: User description: "Update the integration to get details about the
device and relays from the device itself. The default names for relays should
come from the device, the default name of the device should come from the
device. Information about default length of relay delay and the relay
configuration (normally-open, normally-closed, if default configuration should
be high or low for the lock status) should all come from reading the device
configuration."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Device-Sourced Naming (Priority: P1)

As a user, when I add my Akuvox intercom to Home Assistant, I want the device
and its relay entities to be named using the names configured on the device
itself, so that the entities are immediately recognizable without manual
renaming.

The device exposes a location name (e.g., "TestLab Intercom") and per-relay
names (e.g., "Relay1", "RelayB"). The integration should use the location as
the device name and the per-relay names as the default entity names.

**Why this priority**: Naming is the most visible user-facing change and
eliminates the immediate friction of generic "Relay A" / "Relay B" names that
don't match the physical labels on the device's web UI.

**Independent Test**: Can be fully tested by setting up a device whose config
has custom relay names and verifying the entities appear with those names in
Home Assistant.

**Acceptance Scenarios**:

1. **Given** a device with location "Front Door" and relay names "Main Gate"
   and "Side Gate", **When** the integration loads, **Then** the HA device is
   named "Front Door" and lock entities are named "Main Gate" and "Side Gate".
2. **Given** a device whose location field is empty, **When** the integration
   loads, **Then** the device name falls back to "Akuvox {model}" (existing
   behavior).
3. **Given** a device where a relay name field is empty, **When** the
   integration loads, **Then** that relay's entity name falls back to the
   existing "Relay A" / "Relay B" pattern.
4. **Given** a running integration where the device becomes unavailable and the
   user changes the device location on the device, **When** the device becomes
   available again, **Then** the integration refreshes config and uses the
   updated device name.

---

### User Story 2 — Config-Driven Relay Delay (Priority: P2)

As a user, I want the integration to read the relay hold-delay value from the
device configuration and use it when triggering an unlock, so the unlock
duration matches what is configured on the device rather than a fixed default.

The device stores per-relay hold delays (e.g., HoldDelayA = 5 seconds,
HoldDelayB = 10 seconds). The integration should pass the device's configured
delay when triggering each relay.

**Why this priority**: Incorrect unlock duration can cause a door to relock
too soon (user locked out) or stay open too long (security risk). Using the
device's own value ensures correct physical behavior.

**Independent Test**: Can be tested by changing the hold-delay on a device and
verifying the integration's trigger command uses the updated value.

**Acceptance Scenarios**:

1. **Given** a device with Relay A hold delay set to 7 seconds, **When** the
   user unlocks Relay A, **Then** the unlock duration is 7 seconds.
2. **Given** a device with Relay B hold delay set to 3 seconds, **When** the
   user unlocks Relay B, **Then** the unlock duration is 3 seconds.
3. **Given** a device where the hold-delay config value is missing, **When**
   the user unlocks, **Then** the unlock duration falls back to 5 seconds
   (factory default).
4. **Given** a device with Relay A hold delay set to 7 seconds, **When** the
   user unlocks Relay A, **Then** the lock state refreshes after approximately
   8 seconds (delay + buffer) rather than a fixed duration.
5. **Given** a running integration where the device hold delay was 5 seconds
   and the device becomes unavailable, **When** the user changes the hold
   delay to 10 seconds on the device and the device becomes available again,
   **Then** the next unlock uses 10 seconds as the duration.

---

### User Story 3 — Relay Type Awareness (Priority: P3)

As a user, I want the integration to read the relay type (normally-open or
normally-closed) from the device configuration so that the lock state is
interpreted correctly for my wiring.

Relays can be wired as normally-open (NO) or normally-closed (NC). The device
stores this as a per-relay type value (0 = NO, 1 = NC). The state value
returned by the device (0 or 1) must be interpreted differently depending on
the relay type to correctly reflect "locked" vs "unlocked".

**Why this priority**: Users with NC-wired relays currently see inverted lock
state (locked shown as unlocked and vice versa). This is a correctness issue
but affects fewer users since NO is the factory default.

**Independent Test**: Can be tested by configuring a relay as NC and verifying
that a state value of 0 is interpreted as "unlocked" instead of "locked".

**Acceptance Scenarios**:

1. **Given** a relay configured as NO with the relay de-energized, **When**
   the integration reads relay status, **Then** the lock entity shows
   "locked".
2. **Given** a relay configured as NO with the relay energized, **When** the
   integration reads relay status, **Then** the lock entity shows "unlocked".
3. **Given** a relay configured as NC with the relay de-energized, **When**
   the integration reads relay status, **Then** the lock entity shows
   "unlocked".
4. **Given** a relay configured as NC with the relay energized, **When** the
   integration reads relay status, **Then** the lock entity shows "locked".
5. **Given** a device where the relay type config value is missing, **When**
   the integration reads relay status, **Then** the lock entity defaults to
   NO interpretation (current behavior).

---

### Edge Cases

- What happens when the device configuration endpoint is unreachable during
  setup? The integration should log a warning and proceed with safe defaults
  (existing hardcoded values) so the device remains functional.
- What happens when config values are non-numeric or out of expected range
  (e.g., HoldDelay = "abc" or RelayType = "99")? The integration should
  ignore the invalid value, log a warning, and fall back to the default.
- What happens when a relay exists in relay status but has no matching config
  entry (e.g., the device has a third relay but config only has A/B entries)?
  The integration should use defaults for that relay.
- What happens when the device reports relay state as a string ("closed",
  "open") rather than an integer for an NC relay? NC state inversion applies
  only to integer relay states (0/1). String states ("closed"/"open",
  "inactive"/"active") represent logical lock state and are NOT inverted
  based on relay type, since their semantics are already unambiguous.
  event. If the user changes config on the device's web UI and the device
  remains continuously reachable, they can reload the integration to pick up
  the new values.
- What happens if the device becomes unavailable, the user changes config on
  the device, and the device comes back? The integration re-reads config on
  reconnection, so the updated values take effect automatically.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST read device configuration from the device each time
  a connection is established — during initial onboarding, on integration
  reload, and when the device becomes available again after being
  unavailable — and update the cached relay parameters accordingly.
- **FR-002**: System MUST use the device's location name as the default device
  name, falling back to "Akuvox {model}" when the location is empty or
  unavailable.
- **FR-003**: System MUST use the device's per-relay name as the default
  entity name for each lock entity, falling back to "Relay {letter}" when the
  relay name is empty or unavailable.
- **FR-004**: System MUST use the device's per-relay hold-delay value as the
  delay parameter when triggering an unlock, falling back to 5 seconds when
  the value is missing or invalid.
- **FR-005**: System MUST use the device's per-relay type value (NO/NC) to
  correctly interpret relay state when determining locked vs unlocked status.
- **FR-006**: System MUST pass the device's relay type and relay mode to the
  unlock command so the relay activates in the correct mode for its wiring.
- **FR-007**: System MUST gracefully handle missing, empty, or invalid config
  values by falling back to safe defaults and logging a warning.
- **FR-008**: System MUST depend on a device communication library version
  that supports retrieving device configuration.
- **FR-009**: System MUST align the post-unlock state refresh timing with the
  actual hold-delay value from config (plus a small buffer) rather than a
  fixed constant.
- **FR-010**: System MUST re-read device configuration when the device
  transitions from unavailable to available, updating relay parameters
  (names, delays, types) without requiring a manual integration reload.

### Key Entities

- **Device Config**: The full set of device configuration key-value pairs read
  from the device on each connection event. Relevant keys include per-relay
  names, hold delays, relay types, and device location.
- **Relay Config**: Per-relay subset of device config including: name (display
  label), hold delay (unlock duration in seconds), type (NO=0 or NC=1), and
  mode (auto-close=0 or manual=1).

## Assumptions

- The device configuration is read each time a connection to the device is
  established: during initial onboarding, on integration reload, and when the
  device transitions from unavailable to available. If the device remains
  continuously reachable and config changes on the device side, an integration
  reload picks up the new values.
- Config key naming follows the pattern observed on the E18 test device.
  Other Akuvox models are assumed to use the same key naming convention.
- Relay letter suffixes (A, B, etc.) in the device configuration correspond
  to relay numbers (A=1, B=2, etc.) matching the existing relay identification
  scheme.
- Factory default for relay type is NO (normally-open).
- Factory default for hold delay is 5 seconds, consistent with existing
  behavior.
- The relay mode value (auto-close vs manual) stored on the device is passed
  through when triggering a relay but is not user-configurable through Home
  Assistant.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Lock entities display the device-configured relay name by
  default, with zero manual renaming needed when names are set on the device.
- **SC-002**: The device appears in Home Assistant with the device-configured
  location name, matching what the user sees in the device's own web UI.
- **SC-003**: Unlock duration matches the device's configured hold-delay value
  within 1 second of accuracy.
- **SC-004**: Lock state is correctly reported for both NO and NC relay
  configurations, with 100% accuracy for all state/type combinations.
- **SC-005**: When device config is unavailable or contains invalid values, the
  integration continues to function with safe defaults and no errors visible
  to the user (warnings in logs only).
- **SC-006**: When a device reconnects after being unavailable, updated
  configuration values take effect automatically without user intervention.
