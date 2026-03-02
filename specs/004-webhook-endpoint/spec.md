<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Feature Specification: Webhook Endpoint

**Feature Branch**: `004-webhook-endpoint`
**Created**: 2026-03-02
**Status**: Draft
**Input**: User description: "Akuvox devices support webhooks related to actions
happening on the device. We are creating feature 004 and the purpose of this
feature is to add a webhook handler that assigns a unique per-device URL to each
configured Akuvox device so it can receive incoming webhooks from those devices.
We will also need updates to the configuration and
reconfiguration workflows to provide an option for the integration to set up the
webhook configuration on the device."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Receive Device Events via Webhook (Priority: P1)

As a home automation user, I want my Home Assistant instance to receive
real-time event notifications from my Akuvox device (such as doorbell
presses, door openings, and call events) so that I can build automations
that respond immediately to device activity instead of waiting for the
next polling cycle.

The integration defines a single webhook handler and registers it once
for each configured Akuvox device, assigning a unique URL to each
registration. When a device sends a webhook to its URL, the integration
parses the payload, identifies the event type, and fires a Home Assistant
event that automations can subscribe to. The event data MUST include, at
minimum:

- **device_id**: The stable Home Assistant device identifier for the
  Akuvox device (persists across restarts).
- **config_entry_id**: The stable integration config entry identifier
  (persists across restarts).
- **event_type**: A normalized event type string in `lowercase_snake_case`
  format (for example: `doorbell_pressed`, `door_opened`,
  `call_started`). The set of recognized types is extendable as new
  device event types are discovered.
- **payload**: A parsed representation of the webhook payload suitable
  for use in automations.

**Why this priority**: This is the core value of the feature. Without
the ability to receive and process webhook events, nothing else matters.
Real-time event delivery is the fundamental capability that enables all
downstream automation use cases.

**Independent Test**: Can be fully tested by sending a simulated webhook
payload to the endpoint and verifying that a Home Assistant event is
fired with the expected `device_id`, `config_entry_id`, `event_type`,
and `payload` values. Delivers immediate value
by enabling real-time automations.

**Acceptance Scenarios**:

1. **Given** the integration is configured and loaded, **When** the
   Akuvox device sends a valid webhook payload to the endpoint,
   **Then** the integration fires an event on the Home Assistant event
   bus containing the parsed event type and relevant data.
2. **Given** the integration is configured and loaded, **When** a
   malformed or unparsable payload (for example, invalid structure or
   a body from which the event type cannot be determined) is received
   at the webhook endpoint, **Then** the integration logs a warning
   that includes a clear rejection reason and a redacted view of the
   request (applying the Payload Sanitization Rules defined in FR-013),
   and does not fire any event.
3. **Given** the integration is configured and loaded, **When** a
   webhook is received with an identifier that does not match any
   stored webhook identifier for a configured device (as defined in
   FR-004), **Then** Home Assistant's webhook infrastructure returns
   HTTP 200 with `"Webhook not registered."` without invoking the
   integration's handler. No event is fired and no integration-level
   logging occurs for such requests.
4. **Given** the integration is configured and loaded, **When** the
   device sends multiple webhook events in rapid succession, **Then**
   each event is processed and fired independently without loss.

---

### User Story 2 - Configure Webhook During Setup (Priority: P2)

As a user setting up the Akuvox integration for the first time, I want
an option in the configuration flow to automatically configure the
webhook URL on my Akuvox device so that I do not need to manually log
into the device's web interface to set up the webhook destination.

During the initial configuration flow, after the connection to the
device is verified, the user is presented with an option to enable
webhook event delivery. If enabled, the integration generates a unique
webhook URL and pushes the webhook configuration to the device. The
user can also skip this step and configure it later via reconfiguration.

**Why this priority**: This story depends on the webhook endpoint
(Story 1) being functional. It streamlines the setup experience by
removing the need for manual device configuration, which is error-prone
and requires users to know the device's admin interface.

**Independent Test**: Can be tested by walking through the configuration
flow with webhook enabled and verifying the device receives the correct
webhook URL configuration. Delivers value by automating device setup.

**Acceptance Scenarios**:

1. **Given** a user is in the initial configuration flow and has
   successfully connected to the device, **When** the user enables the
   webhook option, **Then** the integration configures the webhook URL
   on the device and stores the webhook identifier in the config entry.
2. **Given** a user is in the initial configuration flow, **When** the
   user chooses to skip webhook setup, **Then** the integration
   completes setup without configuring webhooks on the device, and the
   user can enable it later via reconfiguration.
3. **Given** a user enables webhook setup, **When** the integration
   fails to push the webhook configuration to the device, **Then** the
   user is shown a clear error message explaining the failure and is
   given the option to retry or skip.
4. **Given** the user has completed setup with webhooks enabled,
   **When** the integration loads, **Then** the webhook endpoint is
   registered and ready to receive events.

---

### User Story 3 - Manage Webhook via Reconfiguration (Priority: P3)

As a user with an existing Akuvox integration entry, I want to be able
to enable, disable, or reconfigure webhook event delivery through the
options flow so that I can adjust my setup without
removing and re-adding the integration.

The options flow includes a webhook section where the user can
toggle webhook support on or off. When enabling, the integration pushes
the webhook configuration to the device. When disabling, the integration
removes the webhook configuration from the device and unregisters the
local endpoint.

**Why this priority**: This provides ongoing management capability for
the webhook feature. It is important for users who did not enable
webhooks during initial setup or who need to change their configuration
over time, but it depends on both Stories 1 and 2.

**Independent Test**: Can be tested by reconfiguring an existing
integration entry to toggle webhook support on and off, verifying the
device configuration is updated accordingly each time.

**Acceptance Scenarios**:

1. **Given** an existing integration entry without webhooks enabled,
   **When** the user enables webhooks in the options flow,
   **Then** the integration generates a webhook URL, pushes it to the
   device, and begins receiving events.
2. **Given** an existing integration entry with webhooks enabled,
   **When** the user disables webhooks in the options flow,
   **Then** the integration removes the webhook configuration from the
   device and unregisters the local endpoint.
3. **Given** an existing integration entry with webhooks enabled,
   **When** the integration is reloaded (e.g., after a restart),
   **Then** the webhook endpoint is automatically re-registered using
   the stored webhook identifier.
4. **Given** the user disables webhooks via reconfiguration, **When**
   the device still sends a webhook to the old URL, **Then** the
   request is rejected since the endpoint is no longer registered.

---

### Edge Cases

- What happens when the device sends a webhook but the integration is
  currently reloading? The event must be gracefully dropped with a
  log entry; it must not cause an error, and the integration does not
  attempt to queue or retry the event.
- What happens when multiple Akuvox devices are configured and both
  send webhooks? Each device has its own config entry and webhook
  identifier; events must be attributed to the correct device.
- What happens when the Home Assistant instance URL changes (e.g.,
  moved to a new domain)? The webhook URL stored on the device becomes
  stale. The user must reconfigure webhooks to push the updated URL.
- What happens when the device sends an event type the integration
  does not recognize? The integration should fire a generic event with
  the sanitized payload (per Payload Sanitization Rules / FR-013) and
  log a warning so that unrecognized types can be identified and added
  in future updates.
- What happens when the network between the device and Home Assistant
  is interrupted during a webhook delivery? The delivery fails
  silently on the device side; no special handling is required from
  the integration since it simply will not receive the request.
- What happens when the integration is removed? The integration should
  attempt to remove the webhook configuration from the device and
  unregister the local endpoint during teardown.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST expose a single webhook endpoint per
  configured device that accepts incoming event payloads from the
  Akuvox device.
- **FR-002**: System MUST parse incoming webhook payloads and fire a
  corresponding event on the Home Assistant event bus with the event
  type and relevant data fields.
- **FR-003**: System MUST generate a webhook identifier for each
  configured device that: (a) is unique per device within the
  integration; (b) is generated using a cryptographically secure
  random source with at least 128 bits of entropy; (c) is represented
  as an ASCII, URL-safe string; and (d) is not derived from any
  device- or installation-specific identifiers (such as MAC address,
  IP address, or serial number) to prevent unauthorized access to the
  endpoint.
- **FR-004**: System MUST validate incoming webhook requests before
  processing by ensuring that the webhook identifier embedded in the
  request URL matches exactly a stored webhook identifier for a
  configured device. Requests with a missing, empty, or non-matching
  identifier MUST be rejected and MUST NOT be associated with any
  device. Such rejected requests MUST return an HTTP 200 (OK)
  response with a generic body that does not include any
  diagnostic details. (Home Assistant's webhook infrastructure
  returns HTTP 200 with `"Webhook not registered."` for
  unregistered webhook IDs; the integration cannot customize
  this response. The security goal — no diagnostic leak, no
  event fired — is still met.)
- **FR-005**: System MUST reject and log any webhook request with a
  malformed or unrecognizable payload without crashing or disrupting
  other operations. Such rejected requests MUST return an HTTP 400
  (Bad Request) response with a minimal, generic error indicator and
  MUST NOT include any internal diagnostic details.
- **FR-006**: System MUST include a webhook configuration step in the
  initial setup flow that allows the user to opt in to automatic
  device webhook configuration.
- **FR-007**: System MUST include a webhook management section in the
  options flow that allows the user to enable or
  disable webhook support.
- **FR-008**: When webhook support is enabled, the system MUST push
  the webhook URL to the Akuvox device's configuration.
- **FR-009**: When webhook support is disabled, the system MUST remove
  the webhook configuration from the Akuvox device and unregister the
  local endpoint.
- **FR-010**: System MUST persist the webhook identifier in the
  integration's config entry so that the endpoint can be re-registered
  after restarts.
- **FR-011**: System MUST automatically re-register the webhook
  endpoint when the integration loads if webhook support was previously
  enabled.
- **FR-012**: System MUST attempt to remove the webhook configuration
  from the device when the integration entry is removed.
- **FR-013**: System MUST define and apply a single set of **Payload
  Sanitization Rules** for inbound webhook payloads. These rules are
  the authoritative reference for all logging and event emission
  involving webhook data. At a minimum, these rules MUST:
  (a) replace the value of any field whose key contains `token`,
  `secret`, `password`, `authorization`, `auth`, `key`, `cookie`,
  or `code` (case-insensitive) with `[REDACTED]`;
  (b) mask webhook identifiers by showing only the first 4 and last 2
  characters with the middle replaced by `***` (or use a constant
  placeholder such as `[REDACTED_ID]` if the identifier is 8 or fewer
  characters);
  (c) truncate any individual field value that exceeds 1024 characters,
  appending `...[TRUNCATED]`;
  (d) exclude binary or non-text payloads from logging (log content
  type and size only).
  When the system fires a generic event for unrecognized event types,
  it MUST include the incoming payload only after applying these rules
  and MUST log a warning-level message identifying the unknown type.
  Any log entries that include request payload data MUST also apply
  these rules.
- **FR-014**: System MUST handle concurrent webhook deliveries from the
  same device without event loss or processing errors.

### Key Entities

- **Webhook Endpoint**: A unique URL associated with a specific
  integration config entry. Attributes include the webhook identifier,
  the owning device reference, and the active/inactive state.
- **Webhook Event**: An inbound event payload received from the Akuvox
  device. Contains the event type (e.g., doorbell press, door open,
  call event), a timestamp, and event-specific data fields. Mapped to
  a Home Assistant event bus event after parsing.
- **Device Webhook Configuration**: The webhook URL and related
  settings stored on the Akuvox device. Managed by the integration
  during setup, reconfiguration, and teardown.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users receive Home Assistant events within 2 seconds of
  the Akuvox device triggering a webhook, enabling near-real-time
  automations.
- **SC-002**: 100% of valid webhook payloads from the device received
  while the integration is loaded and the webhook is enabled are
  successfully parsed and delivered as Home Assistant events without
  loss; payloads received during integration reload, disable, or
  teardown windows may be gracefully dropped as defined in the Edge
  Cases section.
- **SC-003**: Users can enable webhook support during initial setup in
  under 1 minute with no manual device configuration required.
- **SC-004**: Users can toggle webhook support on or off via
  reconfiguration without removing and re-adding the integration.
- **SC-005**: Invalid or malformed webhook requests are rejected
  without causing errors, service disruptions, or unintended side
  effects in the integration.
- **SC-006**: After a Home Assistant restart, webhook endpoints are
  automatically restored and functional without user intervention.

## Assumptions

- The Akuvox device exposes a configuration interface that allows
  setting a webhook destination URL programmatically (via the same
  connection method used for other device configuration in this
  integration).
- The Akuvox device sends webhook payloads as HTTP GET requests to the
  configured URL with event data encoded as query parameters.
- Home Assistant's internal webhook infrastructure is available and
  used for registering local webhook endpoints (this is a standard
  Home Assistant capability).
- Each Akuvox device sends webhooks independently; there is no
  centralized webhook relay or aggregation service involved.
- The webhook URL must be reachable from the device's network. The
  integration does not handle NAT traversal or external URL
  provisioning; the device and Home Assistant must be on the same
  network or have appropriate routing configured.
