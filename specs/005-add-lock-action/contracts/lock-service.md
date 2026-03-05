<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Contracts: Add Lock Action

## No New External Interfaces

This feature does not introduce any new external interfaces. The lock
action is exposed through the standard Home Assistant `lock.lock`
service, which is already part of the `LockEntity` base class API.

### Existing Interface (unchanged)

**Service**: `lock.lock`
**Entity**: Any `lock.*` entity provided by the Akuvox integration
**Parameters**: `entity_id` (standard HA service target)
**Behavior change**: Previously raised `HomeAssistantError`; now
executes a mode-aware lock action as defined in the spec.

### Error Contract

| Condition              | Behavior                                      |
| ---------------------- | --------------------------------------------- |
| Device unreachable     | `HomeAssistantError` with descriptive message |
| Already locked (bist.) | No-op; no error raised                        |
| Any state (auto-close) | State refresh only; no error raised           |
