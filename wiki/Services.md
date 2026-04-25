<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Services

All services target `lock` entities belonging to this integration.
Call them via **Developer Tools** → **Services** or from
automations and scripts.

## Schedule Management

| Service                        | Description                    |
| ------------------------------ | ------------------------------ |
| `local_akuvox.list_schedules`  | Retrieve all access schedules. |
| `local_akuvox.add_schedule`    | Create a new access schedule.  |
| `local_akuvox.modify_schedule` | Update an existing schedule.   |
| `local_akuvox.delete_schedule` | Remove a schedule.             |

### Schedule Types

The `schedule_type` field must be a string:

| Value | Type       | Description                       |
| ----- | ---------- | --------------------------------- |
| `"0"` | Date Range | Specific start and end dates.     |
| `"1"` | Weekly     | Selected days of the week.        |
| `"2"` | Daily      | Every day, all day.               |

## User Management

| Service                                   | Description             |
| ----------------------------------------- | ----------------------- |
| `local_akuvox.list_users`                 | Retrieve all users.     |
| `local_akuvox.add_user`                   | Create user (PIN/card). |
| `local_akuvox.modify_user`                | Update existing user.   |
| `local_akuvox.delete_user`                | Remove a user.          |
| `local_akuvox.add_user_schedule_relay`    | Assign schedule-relay.  |
| `local_akuvox.remove_user_schedule_relay` | Remove schedule-relay.  |

## Example: Add a User with PIN Access

```yaml
service: local_akuvox.add_user
target:
  entity_id: lock.local_akuvox_front_gate
data:
  name: "Jane Doe"
  schedules: "10, 20"
  lift_floor_num: "3"
  private_pin: "5678"
```

This creates a user called "Jane Doe" with PIN `5678`, assigned
to schedules 10 and 20, with lift access to floor 3.

## Contact Management

| Service                         | Description                    |
| ------------------------------- | ------------------------------ |
| `local_akuvox.list_contacts`    | Retrieve the contact list.     |
| `local_akuvox.add_contact`      | Create a new contact.          |
| `local_akuvox.modify_contact`   | Update an existing contact.    |
| `local_akuvox.delete_contact`   | Remove one or more contacts.   |

### `local_akuvox.list_contacts`

Retrieves the contact list stored on the device.

| Parameter | Required | Type    | Description                  |
| --------- | -------- | ------- | ---------------------------- |
| `page`    | No       | integer | Page of results to retrieve. |

When called from **Developer Tools** with response enabled, or
from scripts using `response_variable`, returns a dictionary
keyed by `entity_id`; each payload contains a `contacts` list.

### `local_akuvox.add_contact`

Creates a new contact on the device. Fires
`local_akuvox_contact_changed` with `action: add`.

| Parameter | Required | Type   | Description                    |
| --------- | -------- | ------ | ------------------------------ |
| `name`    | Yes      | string | Contact name (1–32 chars).     |
| `phone`   | No       | string | Phone number.                  |
| `group`   | No       | string | Group name (not ID) to assign. |

### `local_akuvox.modify_contact`

Updates an existing contact on the device. Fires
`local_akuvox_contact_changed` with `action: modify`.

| Parameter | Required | Type   | Description                  |
| --------- | -------- | ------ | ---------------------------- |
| `id`      | Yes      | string | Contact ID to modify.        |
| `name`    | No       | string | New name (1–32 chars).       |
| `phone`   | No       | string | New phone number.            |
| `group`   | No       | string | New group name (not ID).     |

### `local_akuvox.delete_contact`

Deletes one or more contacts from the device. Fires
`local_akuvox_contact_changed` with `action: delete`.

| Parameter | Required | Type   | Description                  |
| --------- | -------- | ------ | ---------------------------- |
| `id`      | Yes      | string | Contact ID(s) to delete.     |

> **Tip:** Pass comma-separated IDs for batch deletion,
> e.g. `"42, 43"`.

## Group Management

| Service                        | Description                    |
| ------------------------------ | ------------------------------ |
| `local_akuvox.list_groups`     | Retrieve the group list.       |
| `local_akuvox.add_group`       | Create a new group.            |
| `local_akuvox.modify_group`    | Rename an existing group.      |
| `local_akuvox.delete_group`    | Remove a group.                |

### `local_akuvox.list_groups`

Retrieves the group list from the device.

| Parameter | Required | Type    | Description                  |
| --------- | -------- | ------- | ---------------------------- |
| `page`    | No       | integer | Page of results to retrieve. |

When called from **Developer Tools** with response enabled, or
from scripts using `response_variable`, returns a dictionary
keyed by `entity_id`; each payload contains a `groups` list.

### `local_akuvox.add_group`

Creates a new group on the device. Fires
`local_akuvox_group_changed` with `action: add`.

| Parameter | Required | Type   | Description                  |
| --------- | -------- | ------ | ---------------------------- |
| `name`    | Yes      | string | Group name (1–32 chars).     |

### `local_akuvox.modify_group`

Updates a group's name on the device. Fires
`local_akuvox_group_changed` with `action: modify`.

| Parameter | Required | Type   | Description                  |
| --------- | -------- | ------ | ---------------------------- |
| `id`      | Yes      | string | Group ID to modify.          |
| `name`    | Yes      | string | New group name (1–32 chars). |

### `local_akuvox.delete_group`

Deletes a group from the device. Performs a best-effort
orphan check — if contacts still reference the deleted
group, a warning is logged. Fires
`local_akuvox_group_changed` with `action: delete`.

| Parameter | Required | Type   | Description                  |
| --------- | -------- | ------ | ---------------------------- |
| `id`      | Yes      | string | Group ID to delete.          |

## Example: Create a Group and Add a Contact

```yaml
# Create a "Family" group
service: local_akuvox.add_group
target:
  entity_id: lock.local_akuvox_front_gate
data:
  name: "Family"
```

```yaml
# Add a contact assigned to a group
service: local_akuvox.add_contact
target:
  entity_id: lock.local_akuvox_front_gate
data:
  name: "Alice Smith"
  phone: "555-0199"
  group: "Family"
```
