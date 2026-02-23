<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Feature Specification: Akuvox Lock Integration

**Feature Branch**: `001-akuvox-lock-integration`
**Created**: 2026-02-23
**Status**: Draft
**Input**: User description: "Create a Home Assistant integration called
Akuvox that interacts with Akuvox intercom devices as locks via local APIs"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Add Akuvox Device (Priority: P1)

A Home Assistant user navigates to the integrations page, searches for
"Akuvox", and adds their Akuvox intercom device. They provide the
device's local IP address, select whether the device uses SSL (HTTPS),
and supply any required credentials. When SSL is enabled, a "Verify
SSL" checkbox appears; the user unchecks it if the device uses a
self-signed certificate. The integration connects to the device on
the local network and confirms a successful connection. The device
appears as a lock entity in Home Assistant.

**Why this priority**: Without device setup, no other functionality is
possible. This is the foundational capability that enables all
subsequent stories.

**Independent Test**: Can be fully tested by adding an Akuvox device
through the Home Assistant UI and confirming the lock entity appears
in the entity list with a valid state.

**Acceptance Scenarios**:

1. **Given** a user has an Akuvox intercom on the local network,
   **When** they add the Akuvox integration and provide the device IP
   and credentials, **Then** the integration creates a lock entity
   reflecting the device's current lock state.
2. **Given** a user provides an invalid IP or incorrect credentials,
   **When** they attempt to add the device, **Then** the integration
   displays a clear error message indicating the connection failure
   reason.
3. **Given** a user has already added an Akuvox device,
   **When** they attempt to add the same device again, **Then** the
   integration prevents duplicate entries and notifies the user.
4. **Given** a user has a device using HTTPS with a self-signed
   certificate, **When** they enable SSL in the config flow and leave
   "Verify SSL" unchecked, **Then** the integration connects
   successfully without certificate validation errors.
5. **Given** a user has a device using HTTPS with a valid certificate,
   **When** they enable SSL in the config flow and check "Verify SSL",
   **Then** the integration connects using full SSL certificate
   verification.
6. **Given** a user has a device using plain HTTP,
   **When** they leave SSL disabled in the config flow, **Then** the
   integration connects over HTTP and the "Verify SSL" option is not
   presented.

---

### User Story 2 - Control Door Lock (Priority: P1)

A Home Assistant user views their Akuvox lock entity and triggers an
unlock action (e.g., pressing "Unlock" in the UI, calling the
`lock.unlock` service, or using an automation). The integration sends
the unlock command to the Akuvox device via its local API, and the
lock entity state updates to reflect the change. The device
automatically re-locks after a configurable timeout.

**Why this priority**: Lock/unlock is the primary use case for
exposing intercom devices as locks. This is the core value proposition
of the integration.

**Independent Test**: Can be tested by triggering an unlock action
from the Home Assistant UI or service call and verifying the device
responds and the entity state updates accordingly.

**Acceptance Scenarios**:

1. **Given** an Akuvox lock entity exists and the device is reachable,
   **When** the user triggers an unlock action, **Then** the device
   unlocks and the entity state changes to "unlocked".
2. **Given** an Akuvox lock entity exists and the device is reachable,
   **When** the unlock timeout period expires, **Then** the device
   re-locks and the entity state changes to "locked".
3. **Given** the Akuvox device is unreachable (network issue),
   **When** the user triggers an unlock action, **Then** the
   integration reports the device as unavailable and the action fails
   gracefully with an error notification.

---

### User Story 3 - Monitor Lock State (Priority: P2)

A Home Assistant user views their dashboard and sees the current state
of their Akuvox lock (locked/unlocked/unavailable). The integration
periodically polls the device to keep the state current. If the device
becomes unreachable, the entity is marked unavailable.

**Why this priority**: Real-time state awareness is essential for
automations and user confidence, but depends on the device being
already set up and controllable.

**Independent Test**: Can be tested by observing the lock entity state
in Home Assistant while manually changing the lock state on the
physical device and verifying the entity state updates within the
polling interval.

**Acceptance Scenarios**:

1. **Given** an Akuvox device is configured and reachable,
   **When** the lock state changes on the device, **Then** the Home
   Assistant entity reflects the new state within the polling interval.
2. **Given** an Akuvox device becomes unreachable,
   **When** the next polling cycle occurs, **Then** the entity is
   marked as "unavailable".
3. **Given** an Akuvox device was unavailable and comes back online,
   **When** the next polling cycle occurs, **Then** the entity
   restores to the correct lock state.

---

### User Story 4 - Multiple Relay Support (Priority: P3)

An Akuvox intercom may control multiple door relays (e.g., a building
entrance and a unit door). The integration MUST create a separate lock
entity for each relay on the device, allowing users to control each
door independently.

**Why this priority**: Many Akuvox installations control more than one
door. This extends the core functionality but is not required for a
minimal viable integration.

**Independent Test**: Can be tested by configuring a device with
multiple relays and verifying that each relay appears as a separate
lock entity that can be controlled independently.

**Acceptance Scenarios**:

1. **Given** an Akuvox device with two relays is configured,
   **When** the integration initializes, **Then** two separate lock
   entities are created, one per relay.
2. **Given** two lock entities exist for the same device,
   **When** the user unlocks one relay, **Then** only that relay's
   entity changes state; the other remains unchanged.

---

### Edge Cases

- What happens when the device firmware is updated and the local API
  changes behavior?
- How does the system handle concurrent unlock requests from multiple
  Home Assistant users or automations?
- What happens when the device is power-cycled while the integration
  is polling?
- How does the integration behave if the device responds with
  unexpected or malformed data?
- What happens if the user changes the device IP address after
  initial setup?
- What happens when a device switches from HTTP to HTTPS (or vice
  versa) after a firmware update?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The integration MUST provide a config flow for adding
  Akuvox devices via the Home Assistant UI.
- **FR-002**: The integration MUST communicate with Akuvox devices
  exclusively via their local network API (no cloud dependency).
- **FR-003**: The integration MUST expose each Akuvox intercom relay
  as a Home Assistant lock entity.
- **FR-004**: The integration MUST support the `lock.unlock` service
  to trigger door release on the device.
- **FR-005**: The integration MUST poll the device periodically to
  keep lock state current.
- **FR-006**: The integration MUST mark entities as "unavailable"
  when the device cannot be reached.
- **FR-007**: The integration MUST validate device connectivity
  during the config flow setup process.
- **FR-008**: The integration MUST support devices with multiple
  relays by creating one lock entity per relay.
- **FR-009**: The integration MUST handle device communication
  errors gracefully without crashing Home Assistant.
- **FR-010**: The integration MUST support reconfiguration of device
  connection parameters (IP, credentials, SSL settings) without
  removing and re-adding the device.
- **FR-011**: The integration MUST support three authentication
  modes for device communication: None/AllowList (no credentials
  required), HTTP Basic Auth, and HTTP Digest Auth. The config flow
  MUST allow the user to select the authentication mode and, when
  applicable, provide username and password credentials.
- **FR-012**: The config flow MUST provide a "Use SSL" option that
  the user MUST explicitly set to indicate whether the device uses
  HTTPS. When SSL is enabled, a "Verify SSL" checkbox MUST be
  presented to control whether SSL certificate verification is
  enforced. The "Verify SSL" option MUST NOT appear when SSL is
  disabled.
- **FR-013**: The integration MUST support both HTTP and HTTPS
  connections to Akuvox devices based on the user's explicit SSL
  selection, including HTTPS with self-signed certificates when
  SSL verification is disabled.

### Key Entities

- **Akuvox Device**: Represents a physical Akuvox intercom unit.
  Attributes include IP address, device model, firmware version,
  number of relays, connection status, SSL verification preference,
  and protocol (HTTP or HTTPS).
- **Lock (Relay)**: Represents a single relay on an Akuvox device
  exposed as a Home Assistant lock entity. Attributes include relay
  number, current state (locked/unlocked/unavailable), and parent
  device reference.

### Assumptions

- The integration uses the `pylocal-akuvox` library for all device
  communication.
- Akuvox devices expose a local HTTP or HTTPS API for relay control
  and status queries (no cloud API dependency). The library does not
  auto-detect whether the device uses SSL; the user MUST explicitly
  specify this during setup.
- The "Verify SSL" checkbox defaults to unchecked since most local
  Akuvox deployments use self-signed certificates.
- The underlying library (pylocal-akuvox) handles both valid and
  invalid (self-signed) SSL certificates.
- The device API supports querying the number of available relays.
- Lock entities default to a "locked" state since intercom doors
  are normally locked.
- Polling interval defaults to 30 seconds, which balances
  responsiveness with device/network load.
- The integration follows standard Home Assistant patterns for
  config flow, coordinator-based polling, and entity registration.
- Device authentication supports three modes: None/AllowList,
  HTTP Basic Auth, and HTTP Digest Auth.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can add an Akuvox device and see lock entities
  within 60 seconds of completing the setup flow.
- **SC-002**: Unlock commands are delivered to the device and the
  entity state updates within 5 seconds of user action.
- **SC-003**: Lock state changes on the device are reflected in Home
  Assistant within one polling interval (default 30 seconds).
- **SC-004**: The integration recovers device availability within
  two polling cycles after the device comes back online.
- **SC-005**: The integration operates entirely over the local
  network with zero cloud service dependencies.
- **SC-006**: All device communication errors are handled without
  impacting Home Assistant stability or other integrations.
