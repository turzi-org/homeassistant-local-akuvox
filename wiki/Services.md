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

| Service                                   | Description            |
| ----------------------------------------- | ---------------------- |
| `local_akuvox.list_users`                 | Retrieve all users.    |
| `local_akuvox.add_user`                   | Create user (PIN/card) |
| `local_akuvox.modify_user`                | Update existing user.  |
| `local_akuvox.delete_user`                | Remove a user.         |
| `local_akuvox.add_user_schedule_relay`    | Assign schedule-relay. |
| `local_akuvox.remove_user_schedule_relay` | Remove schedule-relay. |

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
