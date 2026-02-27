<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Feature Specification: Schedule & User Management Services

**Feature Branch**: `003-schedule-user-services`
**Created**: 2026-02-27
**Status**: Draft
**Input**: User description: "Update the integration to add services for getting,
setting, modifying and deleting both schedules and users."

## User Scenarios & Testing *(mandatory)*

<!--
  IMPORTANT: User stories should be PRIORITIZED as user journeys ordered by
  importance. Each user story/journey must be INDEPENDENTLY TESTABLE - meaning
  if you implement just ONE of them, you should still have a viable MVP
  (Minimum Viable Product) that delivers value.

  Assign priorities (P1, P2, P3, etc.) to each story, where P1 is the most
  critical. Think of each story as a standalone slice of functionality that
  can be:
  - Developed independently
  - Tested independently
  - Deployed independently
  - Demonstrated to users independently
-->

### User Story 1 - List Schedules (Priority: P1)

As a home administrator, I want to retrieve all access schedules configured
on my Akuvox device so that I can see the current schedule configuration and
use that information in automations or dashboards.

**Why this priority**: Reading schedules is the foundational operation. All
other schedule operations (create, modify, delete) build upon the ability to
view existing schedules. It also provides immediate value by making previously
hidden device data visible within Home Assistant.

**Independent Test**: Can be fully tested by calling the list schedules
service and verifying the returned data matches the schedules configured on
the device. Delivers value as a standalone read-only capability.

**Acceptance Scenarios**:

1. **Given** a configured Akuvox device with existing schedules, **When** the
   user calls the list schedules service, **Then** all schedules are returned
   with their names, types, time ranges, and day configurations.
2. **Given** a configured Akuvox device with no schedules, **When** the user
   calls the list schedules service, **Then** an empty list is returned with
   no errors.
3. **Given** a device with more schedules than fit on one page, **When** the
   user calls the list schedules service with a page number, **Then** only
   the requested page of results is returned.
4. **Given** a device that is unreachable, **When** the user calls the list
   schedules service, **Then** an appropriate error is raised indicating the
   device is unavailable.

---

### User Story 2 - List Users (Priority: P1)

As a home administrator, I want to retrieve all users configured on my
Akuvox device so that I can see who has access and review their settings
within Home Assistant.

**Why this priority**: Reading users is the foundational operation for user
management, on par with listing schedules. Users are linked to schedules, so
both read operations together enable full visibility into device access
configuration.

**Independent Test**: Can be fully tested by calling the list users service
and verifying the returned data matches the users configured on the device.

**Acceptance Scenarios**:

1. **Given** a configured Akuvox device with existing users, **When** the
   user calls the list users service, **Then** all users are returned with
   their names, IDs, schedule-relay assignments, and optional attributes
   (PIN, card code) with actual values in plain text.
2. **Given** a configured Akuvox device with no users, **When** the user
   calls the list users service, **Then** an empty list is returned with
   no errors.
3. **Given** a device with more users than fit on one page, **When** the
   user calls the list users service with a page number, **Then** only
   the requested page of results is returned.
4. **Given** a device that is unreachable, **When** the user calls the list
   users service, **Then** an appropriate error is raised indicating the
   device is unavailable.

---

### User Story 3 - Create Schedule (Priority: P2)

As a home administrator, I want to create a new access schedule on my Akuvox
device so that I can define time-based access windows for door control.

**Why this priority**: Creating schedules is the first write operation and
enables the core access-control use case. Schedules must exist before users
can be assigned to them, making this a prerequisite for meaningful user
management.

**Independent Test**: Can be fully tested by creating a schedule with valid
parameters and then listing schedules to confirm it appears on the device.

**Acceptance Scenarios**:

1. **Given** a configured Akuvox device, **When** the user calls the add
   schedule service with a valid schedule type and time parameters, **Then**
   the schedule is created on the device and a success response is returned.
2. **Given** a configured Akuvox device, **When** the user calls the add
   schedule service with an invalid schedule type, **Then** a validation
   error is raised before any device communication occurs.
3. **Given** a configured Akuvox device, **When** the user calls the add
   schedule service with malformed time ranges, **Then** a validation error
   is raised with a clear description of the expected format.

---

### User Story 4 - Modify Schedule (Priority: P2)

As a home administrator, I want to modify an existing access schedule on my
Akuvox device so that I can adjust access windows without recreating the
entire schedule.

**Why this priority**: Modifying schedules completes the schedule write
operations and avoids forcing users to delete and recreate schedules for
minor changes.

**Independent Test**: Can be fully tested by modifying a schedule attribute
and then listing schedules to confirm the change persists on the device.

**Acceptance Scenarios**:

1. **Given** a device with an existing schedule, **When** the user calls the
   modify schedule service with the schedule ID and updated fields, **Then**
   only the specified fields are updated and all other fields remain
   unchanged.
2. **Given** a device with an existing schedule, **When** the user calls the
   modify schedule service with a non-existent schedule ID, **Then** an
   appropriate error is raised indicating the schedule was not found.
3. **Given** a device with an existing schedule, **When** the user calls the
   modify schedule service with invalid field values, **Then** a validation
   error is raised before any device communication occurs.

---

### User Story 5 - Delete Schedule (Priority: P2)

As a home administrator, I want to delete an access schedule from my Akuvox
device so that I can remove outdated or unnecessary access windows.

**Why this priority**: Deletion completes the full CRUD lifecycle for
schedules and is necessary for ongoing schedule management.

**Independent Test**: Can be fully tested by deleting a schedule by ID and
then listing schedules to confirm it is no longer present.

**Acceptance Scenarios**:

1. **Given** a device with an existing schedule, **When** the user calls the
   delete schedule service with the schedule ID, **Then** the schedule is
   removed from the device.
2. **Given** a device, **When** the user calls the delete schedule service
   with a non-existent schedule ID, **Then** an appropriate error is raised
   indicating the schedule was not found.

---

### User Story 6 - Create User (Priority: P3)

As a home administrator, I want to create a new user on my Akuvox device so
that I can grant individuals access through the intercom with specific
schedule and relay assignments.

**Why this priority**: User creation depends on schedules already existing
(for schedule-relay assignment) and on the read operations being available
for verification. It is the first user write operation.

**Independent Test**: Can be fully tested by creating a user with valid
parameters (name, user ID, schedule-relay assignment) and then listing users
to confirm the user appears on the device.

**Acceptance Scenarios**:

1. **Given** a configured device with at least one schedule, **When** the
   user calls the add user service with a name, user ID, and schedule-relay
   assignment, **Then** the user is created on the device.
2. **Given** a configured device, **When** the user calls the add user
   service with an optional PIN, **Then** the user is created with the PIN
   configured for keypad access.
3. **Given** a configured device, **When** the user calls the add user
   service with an optional card code, **Then** the user is created with
   the card code configured for badge access.
4. **Given** a configured device, **When** the user calls the add user
   service with a PIN that is too short or too long, **Then** a validation
   error is raised indicating the PIN must be 4-8 digits.
5. **Given** a configured device, **When** the user calls the add user
   service with a malformed schedule-relay assignment, **Then** a validation
   error is raised with a clear description of the expected format.

---

### User Story 7 - Modify User (Priority: P3)

As a home administrator, I want to modify an existing user on my Akuvox
device so that I can update their access credentials, schedule assignments,
or personal details without recreating the user.

**Why this priority**: Modifying users is a natural extension of user
creation and avoids the overhead of deleting and recreating users for
simple changes.

**Independent Test**: Can be fully tested by modifying a user attribute and
then listing users to confirm the change persists on the device.

**Acceptance Scenarios**:

1. **Given** a device with an existing user, **When** the user calls the
   modify user service with the user's device ID and updated fields, **Then**
   only the specified fields are updated and all other fields remain
   unchanged.
2. **Given** a device with an existing user, **When** the user calls the
   modify user service with a non-existent device ID, **Then** an
   appropriate error is raised indicating the user was not found.
3. **Given** a device with an existing user, **When** the user calls the
   modify user service with invalid field values (e.g., a 3-digit PIN),
   **Then** a validation error is raised before any device communication
   occurs.

---

### User Story 8 - Delete User (Priority: P3)

As a home administrator, I want to delete a user from my Akuvox device so
that I can revoke access for individuals who no longer need it.

**Why this priority**: Deletion completes the full CRUD lifecycle for users
and is essential for access revocation.

**Independent Test**: Can be fully tested by deleting a user by device ID and
then listing users to confirm the user is no longer present.

**Acceptance Scenarios**:

1. **Given** a device with an existing user, **When** the user calls the
   delete user service with the user's device ID, **Then** the user is
   removed from the device.
2. **Given** a device, **When** the user calls the delete user service with
   a non-existent device ID, **Then** an appropriate error is raised
   indicating the user was not found.

---

### Edge Cases

- What happens when the device returns a partial or malformed response during
  schedule or user listing? The system should handle parsing failures
  gracefully and return an error rather than partial data.
- What happens when a user attempts to create a schedule or user while the
  device is in the middle of a firmware update or restart? The system should
  detect the connection failure and report the device as unavailable.
- What happens when the user provides a page number that exceeds the total
  number of pages? The system should return an empty list.
- What happens when multiple Home Assistant users call write services
  (create, modify, delete) simultaneously targeting the same device? The
  system should serialize requests to prevent race conditions on the device.
- What happens when a schedule is deleted while users are still assigned to
  it? The system should allow the deletion (this is device-managed behavior)
  but log a warning about orphaned user-schedule assignments.
- What happens when service parameters contain special characters or
  excessively long values? The system should validate input lengths and
  character sets before sending to the device.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST expose a service to list all access schedules from
  the device, returning schedule details including name, type, day
  configuration, and time ranges.
- **FR-002**: System MUST expose a service to create a new access schedule on
  the device, accepting schedule type, optional name, day selection, and time
  range parameters.
- **FR-003**: System MUST expose a service to modify an existing access
  schedule on the device, identified by schedule ID, allowing partial updates
  to any mutable schedule field.
- **FR-004**: System MUST expose a service to delete an access schedule from
  the device, identified by schedule ID.
- **FR-005**: System MUST expose a service to list all users from the device,
  returning user details including name, user ID, schedule-relay assignments,
  and optional attributes (PIN, card code) with actual values in plain text.
- **FR-006**: System MUST expose a service to create a new user on the
  device, accepting name, user ID, schedule-relay assignment, and optional
  PIN, card code, web relay, and lift floor parameters.
- **FR-007**: System MUST expose a service to modify an existing user on the
  device, identified by device-assigned user ID, allowing partial updates to
  any mutable user field.
- **FR-008**: System MUST expose a service to delete a user from the device,
  identified by device-assigned user ID.
- **FR-009**: System MUST validate all service input parameters before
  communicating with the device, rejecting invalid values with descriptive
  error messages.
- **FR-010**: System MUST support optional pagination for list operations,
  allowing the caller to request a specific page of results.
- **FR-011**: System MUST propagate device communication errors (connection
  failures, authentication failures, device errors) as appropriate service
  call errors.
- **FR-012**: System MUST scope all services to a specific device entry,
  ensuring multi-device setups route requests to the correct device.
- **FR-013**: System MUST fire an event after successful write operations
  (create, modify, delete) to enable automations that react to schedule or
  user changes.

### Key Entities

- **Access Schedule**: A time-based access rule configured on the Akuvox
  device. Key attributes: device-assigned ID, schedule type (defines the
  time rule structure), name, day-of-week selections, daily time ranges,
  and date ranges. Schedules are referenced by users for relay access
  assignments.
- **User**: An access credential record on the Akuvox device representing a
  person with intercom access. Key attributes: device-assigned ID, name,
  external user identifier, schedule-relay assignments (linking the user to
  one or more schedule/relay pairs), optional PIN for keypad entry, optional
  card code for badge entry, optional web relay access, and optional lift
  floor assignment.

### Assumptions

- The Akuvox device manages all data persistence. The integration acts as a
  pass-through to the device's local API and does not cache or store schedule
  or user data within Home Assistant.
- Schedule types, day codes, and time formats follow the conventions defined
  by the Akuvox device firmware and are passed through with client-side
  validation matching the device's expected formats.
- The device handles referential integrity between schedules and users. If a
  schedule is deleted while users reference it, the device determines the
  resulting behavior.
- Services follow Home Assistant conventions for service registration,
  parameter schemas, and error reporting.
- PINs and card codes MUST be returned in plain text in service response
  data, as downstream automations and integrations depend on reading the
  actual values. However, PINs and card codes MUST NOT be written to
  logs in plain text; log entries should mask or omit these values.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Administrators can list all schedules and users from the device
  within 5 seconds of calling the respective service.
- **SC-002**: Administrators can create, modify, and delete schedules and
  users through service calls with 100% of valid inputs succeeding on the
  first attempt.
- **SC-003**: 100% of invalid inputs (malformed times, out-of-range values,
  invalid IDs) are rejected with a descriptive error message before any
  device communication occurs.
- **SC-004**: All eight services (list/add/modify/delete for both schedules
  and users) are individually callable from Home Assistant automations,
  scripts, and the developer tools service panel.
- **SC-005**: Write operations (create, modify, delete) fire events that
  automations can trigger on, enabling reactive workflows such as
  notifications when access is granted or revoked.
- **SC-006**: Service calls against an unreachable device return a clear
  error within 10 seconds rather than hanging indefinitely.
