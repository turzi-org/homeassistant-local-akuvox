<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Data Model: Schedule & User Management Services

**Feature**: 003-schedule-user-services
**Date**: 2026-02-27

## Service Response Models

These models represent the data returned by list services and
accepted by write services. They mirror the library's data classes
but are documented here for contract purposes.

### AccessSchedule (read from device)

| Field | Type | Description | Mutable |
| ----- | ---- | ----------- | ------- |
| id | str | Device-assigned schedule ID | No |
| schedule_type | str | Type code: "0", "1", or "2" | Yes |
| name | str \| None | Display name | Yes |
| week | str \| None | Day-of-week codes (digits 0-6) | Yes |
| daily | str \| None | Daily time range (HH:MM-HH:MM) | Yes |
| date_start | str \| None | Start date (YYYYMMDD) | Yes |
| date_end | str \| None | End date (YYYYMMDD) | Yes |
| time_start | str \| None | Start time (HH:MM) | Yes |
| time_end | str \| None | End time (HH:MM) | Yes |
| display_id | str \| None | Device display identifier | No |
| source_type | str \| None | Origin indicator (cloud vs local) | No |
| mode | str \| None | Schedule mode | No |
| sun | str \| None | Sunday flag | No |
| mon | str \| None | Monday flag | No |
| tue | str \| None | Tuesday flag | No |
| wed | str \| None | Wednesday flag | No |
| thur | str \| None | Thursday flag | No |
| fri | str \| None | Friday flag | No |
| sat | str \| None | Saturday flag | No |

**Cloud entity rule**: When `source_type` is `"2"`, the schedule
is cloud-provisioned and MUST be treated as read-only. Modify and
delete operations MUST be rejected with a descriptive error.
Cloud-provisioned schedules MUST NOT be usable in `schedule_relay`
assignments when creating local users. A `source_type` of `"1"`
indicates a locally created schedule.

### User (read from device)

| Field | Type | Description | Mutable |
| ----- | ---- | ----------- | ------- |
| id | str | Device-assigned user ID | No |
| name | str | User display name | Yes |
| user_id | str | External user identifier | Yes |
| schedule_relay | str | Schedule-relay pairs (`<ID>-<Relay>;`) | Yes |
| web_relay | str \| None | Web relay assignment | Yes |
| private_pin | str \| None | 4-8 digit PIN (plain text) | Yes |
| card_code | str \| None | Card/badge code (plain text) | Yes |
| lift_floor_num | str \| None | Elevator floor access | Yes |
| user_type | str \| None | User type indicator | No |
| source | str \| None | Origin source | No |
| source_type | str \| None | Origin indicator (cloud vs local) | No |

**Cloud entity rule**: When `source_type` is `"2"`, the user
is cloud-provisioned and MUST be treated as read-only. Modify and
delete operations MUST be rejected with a descriptive error.
A `source_type` of `"1"` indicates a locally created user.

**Sensitive data rule**: `private_pin` and `card_code` are returned
in plain text in service responses. They MUST NOT appear in log
output; log entries MUST mask or omit these values.

### ScheduleRelayPair (logical sub-structure of User.schedule_relay)

The `schedule_relay` field is a semicolon-delimited string of
`<ScheduleID>-<RelayID>` pairs. A single user can have multiple
pairs (e.g. `"1-1;2-3;5-2;"`).

| Component | Type | Description |
| --------- | ---- | ----------- |
| schedule_id | str (int) | Reference to an AccessSchedule.id |
| relay_id | str (int) | Reference to a device relay number |

**Format**: `"<schedule_id>-<relay_id>;"` per pair, concatenated.
**Regex**: `^([0-9]+-[0-9]+;)+$` (at least one pair required).
**Examples**: `"1-1;"`, `"1-1;2-3;"`, `"5-2;10-4;"`.

The pylocal-akuvox library treats this as an opaque string. The
integration provides two convenience services for pair
manipulation of this string representation:

- `add_user_schedule_relay` — appends a pair to existing string
- `remove_user_schedule_relay` — removes a specific pair

Both operate via fetch-then-modify on the full `schedule_relay`
string using `modify_user()`, and are not atomic with respect
to concurrent updates.

## Validation Rules

### Schedule Input Validation

**add_schedule** schema-level (vol.Invalid on failure):

| Field | Rule |
| ----- | ---- |
| schedule_type | Required; "0", "1", "2" |
| name | Required; non-empty string |
| time_start | Required; cv.time (HH:MM) |
| time_end | Required; cv.time (HH:MM) |
| date_start | Optional; cv.date (YYYY-MM-DD) |
| date_end | Optional; cv.date (YYYY-MM-DD) |
| week | Optional; non-empty list of day names |

**modify_schedule**: All fields optional except `id`
(required). Same type validators apply when provided.

**Type-specific required fields** (add only, validated
in entity; raises ServiceValidationError):

| Type | Label | Required Fields |
| ---- | ----- | --------------- |
| "0" | Date Range | week, date_start, date_end, time_start, time_end |
| "1" | Weekly | week, time_start, time_end |
| "2" | Daily | time_start, time_end |

**UI selectors**: schedule_type shows labels ("Date Range",
"Weekly", "Daily"); week is multi-select with day-of-week
checkboxes; date fields use date picker; time fields use
time picker.

**Input conversion** (entity → device):

- Day names → digit string: `["mon", "fri"]` → `"15"`
  (0=Sun, 1=Mon, …, 6=Sat)
- Date objects → YYYYMMDD: `2026-01-15` → `"20260115"`
- Time objects → HH:MM: `08:00` → `"08:00"`

### User Input Validation (for add/modify)

| Field | Rule | Error Message |
| ----- | ---- | ------------- |
| name | Non-empty string | "Name is required" |
| user_id | Non-empty string | "User ID is required" |
| schedule_relay | `<int>-<int>;` pairs | "Expected `<ID>-<Relay>;` pairs" |
| private_pin | 4-8 digits if provided | "PIN must be 4-8 digits" |
| lift_floor_num | Required for add | "Lift floor number is required" |

**Note on name/user_id length and charset**: The pylocal-akuvox
library and device firmware enforce maximum lengths and allowed
characters for `name` and `user_id`. The integration does not
duplicate these checks; library-raised validation errors are
mapped to `ServiceValidationError` and forwarded to the caller.

## Relationships

```text
ConfigEntry (1)
  │
  ├── AkuvoxDevice (1) ─── pylocal-akuvox client instance
  │
  ├── DataUpdateCoordinator (1) ─── existing, unchanged
  │     └── AkuvoxCoordinatorData (unchanged)
  │
  ├── LockEntity (1..N) ─── existing, unchanged
  │
  └── Services (10) ─── entity methods on AkuvoxLockEntity
        ├── list_schedules ─────────→ device.list_schedules()
        ├── add_schedule ───────────→ device.add_schedule()
        ├── modify_schedule ────────→ device.modify_schedule()
        ├── delete_schedule ────────→ device.delete_schedule()
        ├── list_users ─────────────→ device.list_users()
        ├── add_user ───────────────→ device.add_user()
        ├── modify_user ────────────→ device.modify_user()
        ├── delete_user ────────────→ device.delete_user()
        ├── add_user_schedule_relay → fetch + modify_user()
        └── remove_user_schedule_relay → fetch + modify_user()

AccessSchedule
  └── referenced by User.schedule_relay (ID linkage)

Events (fired after write operations)
  ├── akuvox_schedule_changed {action, config_entry_id, schedule_id?}
  └── akuvox_user_changed {action, config_entry_id, device_user_id?}
```

**Note**: `schedule_id` and `device_user_id` are included when
available. `device_user_id` is the device-assigned identifier,
distinct from the `User` field `user_id` (external identifier).
For add operations, the created entity ID is included if the
device returns it in the response; otherwise it is omitted.

## State Transitions

### Service Call Flow

```text
Service Call Received (HA routes to AkuvoxLockEntity)
  │
  ├── Entity accesses device via self.coordinator.device
  │
  ├── [For write operations on existing entities]
  │   └── Check source_type → ERROR if "2" (cloud)
  │
  ├── [For schedule_relay pair operations]
  │   ├── Fetch current user via device.list_users()
  │   ├── Parse schedule_relay string into pairs
  │   ├── Add/remove specified pair
  │   └── Cloud schedule check if adding
  │
  ├── Validate input parameters → ServiceValidationError if invalid
  │
  ├── Call library method on device
  │   ├── Success → return result (list) or fire event (write)
  │   └── Exception → map to HomeAssistantError
  │
  └── [For write operations]
      └── Fire event: akuvox_{type}_changed
```
