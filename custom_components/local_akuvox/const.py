# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Constants for the Akuvox integration."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from pylocal_akuvox import AuthMethod

DOMAIN: Final = "local_akuvox"
PLATFORMS: Final = ["lock", "switch", "binary_sensor", "event"]

# Webhook config keys
CONF_WEBHOOK_ID: Final = "webhook_id"
CONF_WEBHOOK_ENABLED: Final = "webhook_enabled"

# Webhook event name
EVENT_WEBHOOK_RECEIVED: Final = "local_akuvox_webhook_received"

# Action URL config key prefix
ACTIONURL_PREFIX: Final = "Config.Features.ACTIONURL"

# Action URL keys — maps logical name to device config key
# Covers all events across all 20 Akuvox models (A-D relays/inputs)
ACTIONURL_KEYS: Final[dict[str, str]] = {
    # Relay events (A-D)
    "RelayATriggered": f"{ACTIONURL_PREFIX}.RelayATriggered",
    "RelayAClosed": f"{ACTIONURL_PREFIX}.RelayAClosed",
    "RelayBTriggered": f"{ACTIONURL_PREFIX}.RelayBTriggered",
    "RelayBClosed": f"{ACTIONURL_PREFIX}.RelayBClosed",
    "RelayCTriggered": f"{ACTIONURL_PREFIX}.RelayCTriggered",
    "RelayCClosed": f"{ACTIONURL_PREFIX}.RelayCClosed",
    "RelayDTriggered": f"{ACTIONURL_PREFIX}.RelayDTriggered",
    "RelayDClosed": f"{ACTIONURL_PREFIX}.RelayDClosed",
    # Input events (A-D)
    "InputATriggered": f"{ACTIONURL_PREFIX}.InputATriggered",
    "InputAClosed": f"{ACTIONURL_PREFIX}.InputAClosed",
    "InputBTriggered": f"{ACTIONURL_PREFIX}.InputBTriggered",
    "InputBClosed": f"{ACTIONURL_PREFIX}.InputBClosed",
    "InputCTriggered": f"{ACTIONURL_PREFIX}.InputCTriggered",
    "InputCClosed": f"{ACTIONURL_PREFIX}.InputCClosed",
    "InputDTriggered": f"{ACTIONURL_PREFIX}.InputDTriggered",
    "InputDClosed": f"{ACTIONURL_PREFIX}.InputDClosed",
    # Code events
    "ValidCodeEntered": f"{ACTIONURL_PREFIX}.ValidCodeEntered",
    "InvalidCodeEntered": f"{ACTIONURL_PREFIX}.InvalidCodeEntered",
    # Card events
    "ValidCardEntered": f"{ACTIONURL_PREFIX}.ValidCardEntered",
    "InvalidCardEntered": f"{ACTIONURL_PREFIX}.InvalidCardEntered",
    # Face recognition events
    "ValidFaceRecognition": f"{ACTIONURL_PREFIX}.ValidFaceRecognition",
    "InvalidFaceRecognition": f"{ACTIONURL_PREFIX}.InvalidFaceRecognition",
    # QR code events
    "ValidQRCodeEntered": f"{ACTIONURL_PREFIX}.ValidQRCodeEntered",
    "InvalidQRCodeEntered": f"{ACTIONURL_PREFIX}.InvalidQRCodeEntered",
    # Tamper alarm
    "TamperAlarmTriggered": f"{ACTIONURL_PREFIX}.TamperAlarmTriggered",
    # Break-in alarms (A-D)
    "BreakInAlarmA": f"{ACTIONURL_PREFIX}.BreakInAlarmA",
    "BreakInAlarmB": f"{ACTIONURL_PREFIX}.BreakInAlarmB",
    "BreakInAlarmC": f"{ACTIONURL_PREFIX}.BreakInAlarmC",
    "BreakInAlarmD": f"{ACTIONURL_PREFIX}.BreakInAlarmD",
    # Call events
    "MakeCall": f"{ACTIONURL_PREFIX}.MakeCall",
    "HangUp": f"{ACTIONURL_PREFIX}.HangUp",
    # Door open timeout
    "AlarmDoorOpenedTimeoutA": f"{ACTIONURL_PREFIX}.AlarmDoorOpenedTimeoutA",
    "AlarmDoorOpenedTimeoutB": f"{ACTIONURL_PREFIX}.AlarmDoorOpenedTimeoutB",
}

# Action URL enable/method keys
ACTIONURL_ENABLE_KEY: Final = f"{ACTIONURL_PREFIX}.Enable"
ACTIONURL_METHOD_KEY: Final = f"{ACTIONURL_PREFIX}.Method"

# Known event types (from device action URL names)
KNOWN_EVENT_TYPES: Final[frozenset[str]] = frozenset(
    {
        # Relay events (A-D)
        "relay_a_triggered",
        "relay_a_closed",
        "relay_b_triggered",
        "relay_b_closed",
        "relay_c_triggered",
        "relay_c_closed",
        "relay_d_triggered",
        "relay_d_closed",
        # Input events (A-D)
        "input_a_triggered",
        "input_a_closed",
        "input_b_triggered",
        "input_b_closed",
        "input_c_triggered",
        "input_c_closed",
        "input_d_triggered",
        "input_d_closed",
        # Code events
        "valid_code_entered",
        "invalid_code_entered",
        # Card events
        "valid_card_entered",
        "invalid_card_entered",
        # Face recognition events
        "valid_face_recognition",
        "invalid_face_recognition",
        # QR code events
        "valid_qr_code_entered",
        "invalid_qr_code_entered",
        # Tamper alarm
        "tamper_alarm_triggered",
        # Break-in alarms (A-D)
        "break_in_alarm_a",
        "break_in_alarm_b",
        "break_in_alarm_c",
        "break_in_alarm_d",
        # Call events
        "make_call",
        "hang_up",
        # Door open timeout
        "alarm_door_opened_timeout_a",
        "alarm_door_opened_timeout_b",
    }
)

# Event types that trigger coordinator refresh
REFRESH_EVENT_TYPES: Final[frozenset[str]] = frozenset(
    {
        "relay_a_triggered",
        "relay_a_closed",
        "relay_b_triggered",
        "relay_b_closed",
        "relay_c_triggered",
        "relay_c_closed",
        "relay_d_triggered",
        "relay_d_closed",
        "valid_code_entered",
    }
)

# Service names
SERVICE_LIST_SCHEDULES: Final = "list_schedules"
SERVICE_ADD_SCHEDULE: Final = "add_schedule"
SERVICE_MODIFY_SCHEDULE: Final = "modify_schedule"
SERVICE_DELETE_SCHEDULE: Final = "delete_schedule"
SERVICE_LIST_USERS: Final = "list_users"
SERVICE_ADD_USER: Final = "add_user"
SERVICE_MODIFY_USER: Final = "modify_user"
SERVICE_DELETE_USER: Final = "delete_user"
SERVICE_ADD_USER_SCHEDULE_RELAY: Final = "add_user_schedule_relay"
SERVICE_REMOVE_USER_SCHEDULE_RELAY: Final = "remove_user_schedule_relay"
SERVICE_LIST_CONTACTS: Final = "list_contacts"
SERVICE_ADD_CONTACT: Final = "add_contact"
SERVICE_MODIFY_CONTACT: Final = "modify_contact"
SERVICE_DELETE_CONTACT: Final = "delete_contact"
SERVICE_LIST_GROUPS: Final = "list_groups"
SERVICE_ADD_GROUP: Final = "add_group"
SERVICE_MODIFY_GROUP: Final = "modify_group"
SERVICE_DELETE_GROUP: Final = "delete_group"

# Event names
EVENT_SCHEDULE_CHANGED: Final = "local_akuvox_schedule_changed"
EVENT_USER_CHANGED: Final = "local_akuvox_user_changed"
EVENT_CONTACT_CHANGED: Final = "local_akuvox_contact_changed"
EVENT_GROUP_CHANGED: Final = "local_akuvox_group_changed"

# Config keys
CONF_HOST: Final = "host"
CONF_USE_SSL: Final = "use_ssl"
CONF_VERIFY_SSL: Final = "verify_ssl"
CONF_AUTH_METHOD: Final = "auth_method"
CONF_USERNAME: Final = "username"
CONF_PASSWORD: Final = "password"  # noqa: S105

# Auth mode constants
AUTH_NONE: Final = "none"
AUTH_BASIC: Final = "basic"
AUTH_DIGEST: Final = "digest"

# Defaults
DEFAULT_SCAN_INTERVAL: Final = 30

# Device config key prefix
CONFIG_KEY_PREFIX: Final = "Config.DoorSetting"

# Device config keys (full dot-separated paths)
CONFIG_KEY_LOCATION: Final = f"{CONFIG_KEY_PREFIX}.DEVICENODE.Location"

# Relay config key patterns — use with relay letter suffix (A, B, etc.)
# Name/HoldDelay: PREFIX.RELAY.{Property}{Letter} (e.g., NameA, HoldDelayA)
CONFIG_KEY_RELAY_NAME: Final = f"{CONFIG_KEY_PREFIX}.RELAY.Name"
CONFIG_KEY_RELAY_HOLD_DELAY: Final = f"{CONFIG_KEY_PREFIX}.RELAY.HoldDelay"
# Type/Mode: PREFIX.RELAY.Relay{Letter}{Property} (e.g., RelayAType, RelayAMode)
CONFIG_KEY_RELAY_PREFIX: Final = f"{CONFIG_KEY_PREFIX}.RELAY.Relay"
CONFIG_KEY_RELAY_TYPE_SUFFIX: Final = "Type"
CONFIG_KEY_RELAY_MODE_SUFFIX: Final = "Mode"

# Relay key pattern — matches "RelayA", "RelayB", etc.
RELAY_KEY_RE: Final = re.compile(r"Relay([A-Z])")

# Device config defaults
DEFAULT_HOLD_DELAY_SECONDS: Final = 5
DEFAULT_RELAY_TYPE: Final = 0
DEFAULT_RELAY_MODE: Final = 0

# Entity configuration keys (stored in entry.options["entity_config"])
CONF_ENTITY_CONFIG: Final = "entity_config"

# Valid device classes for input binary sensors
VALID_INPUT_DEVICE_CLASSES: Final = [
    "door",
    "garage_door",
    "gate",
    "window",
    "motion",
    "opening",
    "tamper",
    "safety",
    "none",
]

# Device model stored in entry.data
CONF_DEVICE_MODEL: Final = "device_model"

# Model capabilities — relay and input counts per model
# Derived from Akuvox "Action URLs Supported by Different Models" spec
MODEL_CAPABILITIES: Final[dict[str, dict[str, int]]] = {
    # S series
    "S539": {"relays": 3, "inputs": 3},
    "S535": {"relays": 1, "inputs": 2},
    "S532": {"relays": 2, "inputs": 4},
    # X series
    "X916": {"relays": 4, "inputs": 4},
    "X915": {"relays": 3, "inputs": 3},
    "X915V2": {"relays": 3, "inputs": 3},
    "X912": {"relays": 2, "inputs": 3},
    "X910": {"relays": 2, "inputs": 2},
    # R series
    "R29": {"relays": 3, "inputs": 3},
    "R28": {"relays": 3, "inputs": 3},
    "R28V2": {"relays": 3, "inputs": 3},
    "R20": {"relays": 2, "inputs": 2},
    "R25": {"relays": 2, "inputs": 2},
    # E series
    "E18": {"relays": 2, "inputs": 3},
    "E16": {"relays": 1, "inputs": 1},
    "E16V2": {"relays": 1, "inputs": 1},
    "E13": {"relays": 1, "inputs": 2},
    "E12": {"relays": 1, "inputs": 2},
    # A series
    "A095": {"relays": 4, "inputs": 4},
    "A094": {"relays": 4, "inputs": 0},
    "A05": {"relays": 1, "inputs": 1},
    "A03": {"relays": 1, "inputs": 2},
    "A02": {"relays": 1, "inputs": 2},
    "A01": {"relays": 1, "inputs": 2},
}

# Default capabilities when model is unknown
DEFAULT_MODEL_CAPABILITIES: Final[dict[str, int]] = {
    "relays": 2,
    "inputs": 2,
}


def get_model_capabilities(model: str) -> dict[str, int]:
    """Look up relay/input counts for a model name.

    Performs fuzzy matching: tries exact match first, then checks
    if the model string starts with a known prefix (e.g., "R29S"
    matches "R29", "E16V2-IP" matches "E16V2").

    Args:
        model: The device model string from get_info().

    Returns:
        Dict with 'relays' and 'inputs' counts.

    """
    # Exact match
    upper = model.upper().strip()
    if upper in MODEL_CAPABILITIES:
        return MODEL_CAPABILITIES[upper]

    # Prefix match (longest match wins)
    best_match = ""
    for key in MODEL_CAPABILITIES:
        if upper.startswith(key) and len(key) > len(best_match):
            best_match = key

    if best_match:
        return MODEL_CAPABILITIES[best_match]

    return dict(DEFAULT_MODEL_CAPABILITIES)

# Day-of-week name → digit mapping (single source of truth)
DAY_NAME_TO_DIGIT: Final[dict[str, str]] = {
    "sun": "0",
    "mon": "1",
    "tue": "2",
    "wed": "3",
    "thu": "4",
    "fri": "5",
    "sat": "6",
}
VALID_DAYS: Final = list(DAY_NAME_TO_DIGIT.keys())

# Lazy import: AuthMethod lives in pylocal_akuvox and is imported at
# runtime to avoid a top-level heavy dependency in const.py.  The map
# is built once on first call and cached.
_AUTH_METHOD_MAP: dict[str, AuthMethod] | None = None


def get_auth_method_map() -> dict[str, AuthMethod]:
    """Return the AUTH_METHOD_MAP, importing AuthMethod on first use.

    Returns:
        Mapping from string auth constants to AuthMethod enum values.

    """
    global _AUTH_METHOD_MAP  # noqa: PLW0603
    if _AUTH_METHOD_MAP is None:
        from pylocal_akuvox import AuthMethod as _AuthMethod

        _AUTH_METHOD_MAP = {
            AUTH_NONE: _AuthMethod.NONE,
            AUTH_BASIC: _AuthMethod.BASIC,
            AUTH_DIGEST: _AuthMethod.DIGEST,
        }
    return _AUTH_METHOD_MAP
