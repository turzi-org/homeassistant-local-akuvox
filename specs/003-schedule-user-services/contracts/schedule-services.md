<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Contract: Schedule Services

**Feature**: 003-schedule-user-services
**Component**: `lock.py` (entity service methods)

## Service: `akuvox.list_schedules`

### Input Schema: list_schedules

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| page | int | No | Page number for pagination |

**Entity targeting**: Uses HA standard entity/device/area targeting.
The service is called on an `AkuvoxLockEntity` instance.

### Behavior: list_schedules

1. HA routes the call to the targeted `AkuvoxLockEntity` instance.
2. Entity accesses device via `self.coordinator.device`.
3. Call `await device.list_schedules(page=page)`.
4. Convert each `AccessSchedule` to a dict.
5. Return `{"schedules": [list of schedule dicts]}`.

### Response Format: list_schedules

```python
{
    "schedules": [
        {
            "id": "1",
            "schedule_type": "0",
            "name": "Weekday Access",
            "week": "12345",
            "daily": None,
            "date_start": None,
            "date_end": None,
            "time_start": "08:00",
            "time_end": "18:00",
            "display_id": "1",
            "source_type": "1",    # "1" = local, "2" = cloud
            "mode": None,
            "sun": None,
            "mon": "1",
            "tue": "1",
            "wed": "1",
            "thur": "1",
            "fri": "1",
            "sat": None,
        }
    ]
}
```

Cloud-provisioned schedules (`source_type` of `"2"`) appear in
the list but are clearly identifiable by the `source_type` field.

### Error Handling: list_schedules

| Condition | Exception | Message |
| --------- | --------- | ------- |
| Device offline | HomeAssistantError | "Device unavailable..." |
| Auth failure | HomeAssistantError | "Authentication failed..." |
| Parse error | HomeAssistantError | "Failed to parse device response" |

---

## Service: `akuvox.add_schedule`

### Input Schema: add_schedule

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| schedule_type | str | Yes | "0", "1", or "2" |
| name | str | No | Schedule display name |
| week | str | No | Day codes (digits 0-6) |
| daily | str | No | Time range (HH:MM-HH:MM) |
| date_start | str | No | Start date (YYYYMMDD) |
| date_end | str | No | End date (YYYYMMDD) |
| time_start | str | No | Start time (HH:MM) |
| time_end | str | No | End time (HH:MM) |

**Entity targeting**: Uses HA standard entity/device/area targeting.

### Behavior: add_schedule

1. HA routes the call to the targeted `AkuvoxLockEntity` instance.
2. Validate `schedule_type` is "0", "1", or "2".
3. Validate time/date/week/daily formats if provided.
4. Call `await device.add_schedule(...)`.
5. Fire event `akuvox_schedule_changed` with
   `{"action": "add", "config_entry_id": entry_id}`
   (schedule_id included if device returns it).

### Error Handling: add_schedule

| Condition | Exception | Message |
| --------- | --------- | ------- |
| Invalid schedule_type | ServiceValidationError | "Invalid schedule type..." |
| Malformed time | ServiceValidationError | "Invalid time format..." |
| Library validation | ServiceValidationError | Forwarded message |
| Device error | HomeAssistantError | "Device error..." |

---

## Service: `akuvox.modify_schedule`

### Input Schema: modify_schedule

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| id | str | Yes | Schedule ID to modify |
| schedule_type | str | No | Updated type |
| name | str | No | Updated name |
| week | str | No | Updated day codes |
| daily | str | No | Updated daily range |
| date_start | str | No | Updated start date |
| date_end | str | No | Updated end date |
| time_start | str | No | Updated start time |
| time_end | str | No | Updated end time |

**Entity targeting**: Uses HA standard entity/device/area targeting.

### Behavior: modify_schedule

1. HA routes the call to the targeted `AkuvoxLockEntity` instance.
2. Validate provided fields (same rules as add).
3. **Cloud check**: Fetch current schedule list, find schedule by
   `id`, check `source_type`. If `"2"` (cloud), raise
   `ServiceValidationError` with message "Cannot modify
   cloud-provisioned schedule".
4. Call `await device.modify_schedule(id=id, ...)`.
5. Fire event `akuvox_schedule_changed` with
   `{"action": "modify", "schedule_id": id,
   "config_entry_id": entry_id}`.

### Error Handling: modify_schedule

Inherits from add_schedule, plus:

| Condition | Exception | Message |
| --------- | --------- | ------- |
| Cloud schedule | ServiceValidationError | "Cannot modify cloud schedule" |
| Schedule not found | HomeAssistantError | "Schedule not found" |

---

## Service: `akuvox.delete_schedule`

### Input Schema: delete_schedule

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| id | str | Yes | Schedule ID to delete |

**Entity targeting**: Uses HA standard entity/device/area targeting.

### Behavior: delete_schedule

1. HA routes the call to the targeted `AkuvoxLockEntity` instance.
2. **Cloud check**: Fetch current schedule list, find schedule by
   `id`, check `source_type`. If `"2"` (cloud), raise
   `ServiceValidationError`.
3. Call `await device.delete_schedule(id=id)`.
4. Fire event `akuvox_schedule_changed` with
   `{"action": "delete", "schedule_id": id,
   "config_entry_id": entry_id}`.

### Error Handling: delete_schedule

| Condition | Exception | Message |
| --------- | --------- | ------- |
| Cloud schedule | ServiceValidationError | "Cannot delete cloud schedule" |
| Schedule not found | HomeAssistantError | "Schedule not found" |
| Device error | HomeAssistantError | "Device error..." |
