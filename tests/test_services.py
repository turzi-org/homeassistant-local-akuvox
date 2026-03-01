# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Tests for Akuvox schedule and user CRUD services."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from pylocal_akuvox import (
    AccessSchedule,
    AkuvoxAuthenticationError,
    AkuvoxConnectionError,
    AkuvoxDeviceError,
    AkuvoxParseError,
    AkuvoxRequestError,
    AkuvoxUnsupportedError,
    AkuvoxValidationError,
    User,
)
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_capture_events,
)

from custom_components.akuvox.const import (
    DOMAIN,
    EVENT_SCHEDULE_CHANGED,
    EVENT_USER_CHANGED,
)

ENTITY_ID = "lock.testlab_intercom_front_gate"


async def _setup_entry(
    hass: HomeAssistant,
    config_data: dict[str, Any],
) -> MockConfigEntry:
    """Set up a loaded config entry with a lock entity for service testing.

    The caller must ensure the AkuvoxDevice mock is already patched
    (e.g. via the ``mock_akuvox_device`` fixture).

    Args:
        hass: The Home Assistant instance.
        config_data: Config entry data dict.

    Returns:
        The loaded MockConfigEntry.

    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=config_data,
        unique_id="AA:BB:CC:DD:EE:FF",
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


# Library-to-HA exception mapping pairs:
# (library_exception, expected_ha_exception)
LIBRARY_TO_HA_ERROR_MAP: list[tuple[type[Exception], type[Exception]]] = [
    (AkuvoxConnectionError, HomeAssistantError),
    (AkuvoxAuthenticationError, HomeAssistantError),
    (AkuvoxDeviceError, HomeAssistantError),
    (AkuvoxRequestError, HomeAssistantError),
    (AkuvoxParseError, HomeAssistantError),
    (AkuvoxUnsupportedError, HomeAssistantError),
    (AkuvoxValidationError, ServiceValidationError),
]


def get_ha_error_for_library_error(
    library_exc: type[Exception],
) -> type[Exception]:
    """Return the expected HA exception for a given library exception.

    Args:
        library_exc: The library exception class.

    Returns:
        The expected Home Assistant exception class.

    Raises:
        ValueError: If the library exception is not in the mapping.

    """
    for lib_exc, ha_exc in LIBRARY_TO_HA_ERROR_MAP:
        if lib_exc is library_exc:
            return ha_exc
    msg = f"No mapping for {library_exc.__name__}"
    raise ValueError(msg)


async def test_services_registered_on_setup(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
) -> None:
    """Test that all 10 services are registered after async_setup."""
    await _setup_entry(hass, mock_config_entry_data_none)

    expected_services = [
        "list_schedules",
        "add_schedule",
        "modify_schedule",
        "delete_schedule",
        "list_users",
        "add_user",
        "modify_user",
        "delete_user",
        "add_user_schedule_relay",
        "remove_user_schedule_relay",
    ]
    for svc_name in expected_services:
        assert hass.services.has_service(DOMAIN, svc_name), (
            f"Service {DOMAIN}.{svc_name} not registered"
        )


# ── list_schedules tests ──────────────────────────────────────


async def test_list_schedules_success(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_schedule_list: list[AccessSchedule],
) -> None:
    """Test list_schedules returns schedule dicts."""
    mock_akuvox_device.list_schedules.return_value = mock_schedule_list
    await _setup_entry(hass, mock_config_entry_data_none)

    result = await hass.services.async_call(
        DOMAIN,
        "list_schedules",
        service_data={"entity_id": ENTITY_ID},
        blocking=True,
        return_response=True,
    )

    assert result is not None
    entity_result = result[ENTITY_ID]
    assert isinstance(entity_result, dict)
    assert "schedules" in entity_result
    schedules = entity_result["schedules"]
    assert isinstance(schedules, list)
    assert len(schedules) == 2
    first = schedules[0]
    assert isinstance(first, dict)
    assert first["id"] == "1"
    assert first["schedule_type"] == "1"
    assert first["name"] == "Weekday Access"
    assert first["week"] == "12345"
    assert first["time_start"] == "08:00"
    assert first["time_end"] == "18:00"
    # Cloud schedule has source_type "2"
    cloud = schedules[1]
    assert isinstance(cloud, dict)
    assert cloud["source_type"] == "2"


async def test_list_schedules_empty(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
) -> None:
    """Test list_schedules with no schedules returns empty list."""
    mock_akuvox_device.list_schedules.return_value = []
    await _setup_entry(hass, mock_config_entry_data_none)

    result = await hass.services.async_call(
        DOMAIN,
        "list_schedules",
        service_data={"entity_id": ENTITY_ID},
        blocking=True,
        return_response=True,
    )

    assert result is not None
    assert result[ENTITY_ID] == {"schedules": []}


async def test_list_schedules_page_passed_through(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
) -> None:
    """Test page parameter is forwarded to device."""
    mock_akuvox_device.list_schedules.return_value = []
    await _setup_entry(hass, mock_config_entry_data_none)

    await hass.services.async_call(
        DOMAIN,
        "list_schedules",
        service_data={"entity_id": ENTITY_ID, "page": 3},
        blocking=True,
        return_response=True,
    )

    mock_akuvox_device.list_schedules.assert_called_once_with(page=3)


async def test_list_schedules_no_page_default(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
) -> None:
    """Test omitting page passes None."""
    mock_akuvox_device.list_schedules.return_value = []
    await _setup_entry(hass, mock_config_entry_data_none)

    await hass.services.async_call(
        DOMAIN,
        "list_schedules",
        service_data={"entity_id": ENTITY_ID},
        blocking=True,
        return_response=True,
    )

    mock_akuvox_device.list_schedules.assert_called_once_with(page=None)


@pytest.mark.parametrize(
    ("lib_exc", "ha_exc"),
    [
        (AkuvoxConnectionError, HomeAssistantError),
        (AkuvoxAuthenticationError, HomeAssistantError),
        (AkuvoxParseError, HomeAssistantError),
        (AkuvoxValidationError, ServiceValidationError),
    ],
    ids=["connection", "auth", "parse", "validation"],
)
async def test_list_schedules_device_errors(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    lib_exc: type[Exception],
    ha_exc: type[Exception],
) -> None:
    """Test device errors are mapped to HA exceptions."""
    mock_akuvox_device.list_schedules.side_effect = lib_exc("fail")
    await _setup_entry(hass, mock_config_entry_data_none)

    with pytest.raises(ha_exc):
        await hass.services.async_call(
            DOMAIN,
            "list_schedules",
            service_data={"entity_id": ENTITY_ID},
            blocking=True,
            return_response=True,
        )


async def test_list_schedules_all_fields_present(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_schedule_list: list[AccessSchedule],
) -> None:
    """Test all AccessSchedule fields appear in result dict."""
    mock_akuvox_device.list_schedules.return_value = mock_schedule_list
    await _setup_entry(hass, mock_config_entry_data_none)

    result = await hass.services.async_call(
        DOMAIN,
        "list_schedules",
        service_data={"entity_id": ENTITY_ID},
        blocking=True,
        return_response=True,
    )

    expected_keys = {
        "id",
        "schedule_type",
        "name",
        "week",
        "daily",
        "date_start",
        "date_end",
        "time_start",
        "time_end",
        "display_id",
        "source_type",
        "mode",
        "sun",
        "mon",
        "tue",
        "wed",
        "thur",
        "fri",
        "sat",
    }
    assert result is not None
    entity_result = result[ENTITY_ID]
    assert isinstance(entity_result, dict)
    schedules = entity_result["schedules"]
    assert isinstance(schedules, list)
    for sched in schedules:
        assert isinstance(sched, dict)
        assert set(sched.keys()) == expected_keys


# ── list_users tests ──────────────────────────────────────────


async def test_list_users_success(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_user_list: list[User],
) -> None:
    """Test list_users returns user dicts with plain-text PINs."""
    mock_akuvox_device.list_users.return_value = mock_user_list
    await _setup_entry(hass, mock_config_entry_data_none)

    result = await hass.services.async_call(
        DOMAIN,
        "list_users",
        service_data={"entity_id": ENTITY_ID},
        blocking=True,
        return_response=True,
    )

    assert result is not None
    entity_result = result[ENTITY_ID]
    assert isinstance(entity_result, dict)
    users = entity_result["users"]
    assert isinstance(users, list)
    assert len(users) == 2
    first = users[0]
    assert isinstance(first, dict)
    assert first["id"] == "42"
    assert first["name"] == "John Doe"
    assert first["user_id"] == "john.doe"
    assert first["private_pin"] == "1234"
    assert first["card_code"] == "ABC123"
    # Cloud user has source_type "2"
    cloud = users[1]
    assert isinstance(cloud, dict)
    assert cloud["source_type"] == "2"


async def test_list_users_empty(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
) -> None:
    """Test list_users with no users returns empty list."""
    mock_akuvox_device.list_users.return_value = []
    await _setup_entry(hass, mock_config_entry_data_none)

    result = await hass.services.async_call(
        DOMAIN,
        "list_users",
        service_data={"entity_id": ENTITY_ID},
        blocking=True,
        return_response=True,
    )

    assert result is not None
    assert result[ENTITY_ID] == {"users": []}


async def test_list_users_page_passed_through(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
) -> None:
    """Test page parameter is forwarded to device."""
    mock_akuvox_device.list_users.return_value = []
    await _setup_entry(hass, mock_config_entry_data_none)

    await hass.services.async_call(
        DOMAIN,
        "list_users",
        service_data={"entity_id": ENTITY_ID, "page": 2},
        blocking=True,
        return_response=True,
    )

    mock_akuvox_device.list_users.assert_called_once_with(page=2)


async def test_list_users_no_page_default(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
) -> None:
    """Test omitting page passes None."""
    mock_akuvox_device.list_users.return_value = []
    await _setup_entry(hass, mock_config_entry_data_none)

    await hass.services.async_call(
        DOMAIN,
        "list_users",
        service_data={"entity_id": ENTITY_ID},
        blocking=True,
        return_response=True,
    )

    mock_akuvox_device.list_users.assert_called_once_with(page=None)


@pytest.mark.parametrize(
    ("lib_exc", "ha_exc"),
    [
        (AkuvoxConnectionError, HomeAssistantError),
        (AkuvoxAuthenticationError, HomeAssistantError),
        (AkuvoxParseError, HomeAssistantError),
        (AkuvoxValidationError, ServiceValidationError),
    ],
    ids=["connection", "auth", "parse", "validation"],
)
async def test_list_users_device_errors(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    lib_exc: type[Exception],
    ha_exc: type[Exception],
) -> None:
    """Test device errors are mapped to HA exceptions."""
    mock_akuvox_device.list_users.side_effect = lib_exc("fail")
    await _setup_entry(hass, mock_config_entry_data_none)

    with pytest.raises(ha_exc):
        await hass.services.async_call(
            DOMAIN,
            "list_users",
            service_data={"entity_id": ENTITY_ID},
            blocking=True,
            return_response=True,
        )


async def test_list_users_all_fields_present(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_user_list: list[User],
) -> None:
    """Test all User fields appear in result dict."""
    mock_akuvox_device.list_users.return_value = mock_user_list
    await _setup_entry(hass, mock_config_entry_data_none)

    result = await hass.services.async_call(
        DOMAIN,
        "list_users",
        service_data={"entity_id": ENTITY_ID},
        blocking=True,
        return_response=True,
    )

    expected_keys = {
        "id",
        "name",
        "user_id",
        "schedule_relay",
        "web_relay",
        "private_pin",
        "card_code",
        "lift_floor_num",
        "user_type",
        "source",
        "source_type",
    }
    assert result is not None
    entity_result = result[ENTITY_ID]
    assert isinstance(entity_result, dict)
    users = entity_result["users"]
    assert isinstance(users, list)
    for user in users:
        assert isinstance(user, dict)
        assert set(user.keys()) == expected_keys


async def test_list_users_log_masks_sensitive_data(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_user_list: list[User],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test private_pin and card_code are masked in debug logs."""
    mock_akuvox_device.list_users.return_value = mock_user_list
    await _setup_entry(hass, mock_config_entry_data_none)

    import logging

    with caplog.at_level(logging.DEBUG, logger="custom_components.akuvox"):
        await hass.services.async_call(
            DOMAIN,
            "list_users",
            service_data={"entity_id": ENTITY_ID},
            blocking=True,
            return_response=True,
        )

    log_text = caplog.text
    # Plain-text values must NOT appear in logs
    assert "1234" not in log_text
    assert "5678" not in log_text
    assert "ABC123" not in log_text
    # Masked value should appear
    assert "****" in log_text


# ── add_schedule tests ────────────────────────────────────────


async def test_add_schedule_success(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
) -> None:
    """Test add_schedule calls device with converted params."""
    entry = await _setup_entry(hass, mock_config_entry_data_none)

    await hass.services.async_call(
        DOMAIN,
        "add_schedule",
        service_data={
            "entity_id": ENTITY_ID,
            "schedule_type": "0",
            "name": "Weekday",
            "week": ["mon", "tue", "wed", "thu", "fri"],
            "date_start": "2026-01-01",
            "date_end": "2026-12-31",
            "time_start": "08:00",
            "time_end": "18:00",
        },
        blocking=True,
    )

    mock_akuvox_device.add_schedule.assert_called_once_with(
        schedule_type="0",
        name="Weekday",
        week="12345",
        daily=None,
        date_start="20260101",
        date_end="20261231",
        time_start="08:00",
        time_end="18:00",
    )
    assert entry.entry_id  # sanity


async def test_add_schedule_fires_event(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
) -> None:
    """Test add_schedule fires akuvox_schedule_changed event."""
    entry = await _setup_entry(hass, mock_config_entry_data_none)
    events = async_capture_events(hass, EVENT_SCHEDULE_CHANGED)

    await hass.services.async_call(
        DOMAIN,
        "add_schedule",
        service_data={
            "entity_id": ENTITY_ID,
            "schedule_type": "2",
            "name": "Daily",
            "time_start": "08:00",
            "time_end": "18:00",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data["action"] == "add"
    assert events[0].data["config_entry_id"] == entry.entry_id


async def test_add_schedule_invalid_schedule_type(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
) -> None:
    """Test invalid schedule_type is rejected by schema."""
    await _setup_entry(hass, mock_config_entry_data_none)

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            "add_schedule",
            service_data={
                "entity_id": ENTITY_ID,
                "schedule_type": "9",
                "name": "Bad",
                "time_start": "08:00",
                "time_end": "18:00",
            },
            blocking=True,
        )

    mock_akuvox_device.add_schedule.assert_not_called()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("time_start", "25:00"),
        ("time_start", "abc"),
        ("time_end", "12:60"),
    ],
    ids=[
        "time_start_25",
        "time_start_alpha",
        "time_end_60",
    ],
)
async def test_add_schedule_invalid_time_format(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    field: str,
    value: str,
) -> None:
    """Test malformed time values are rejected by schema."""
    await _setup_entry(hass, mock_config_entry_data_none)

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            "add_schedule",
            service_data={
                "entity_id": ENTITY_ID,
                "schedule_type": "0",
                "name": "Test",
                field: value,
                "time_start" if field != "time_start" else "time_end": "12:00",
            },
            blocking=True,
        )

    mock_akuvox_device.add_schedule.assert_not_called()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("date_start", "abcdefgh"),
        ("date_start", "20260115"),
        ("date_end", "2026-13-01"),
    ],
    ids=[
        "date_start_alpha",
        "date_start_no_dashes",
        "date_end_month13",
    ],
)
async def test_add_schedule_invalid_date_format(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    field: str,
    value: str,
) -> None:
    """Test malformed date values are rejected by schema."""
    await _setup_entry(hass, mock_config_entry_data_none)

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            "add_schedule",
            service_data={
                "entity_id": ENTITY_ID,
                "schedule_type": "0",
                "name": "Test",
                field: value,
                "time_start": "08:00",
                "time_end": "18:00",
            },
            blocking=True,
        )

    mock_akuvox_device.add_schedule.assert_not_called()


@pytest.mark.parametrize(
    "value",
    [["xyz"], ["mon", "bad"], [], ["mon", "mon"]],
    ids=["unknown_day", "one_bad_day", "empty_list", "duplicate_day"],
)
async def test_add_schedule_invalid_week_values(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    value: list[str],
) -> None:
    """Test invalid week day names are rejected by schema."""
    await _setup_entry(hass, mock_config_entry_data_none)

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            "add_schedule",
            service_data={
                "entity_id": ENTITY_ID,
                "schedule_type": "1",
                "name": "Test",
                "week": value,
                "time_start": "08:00",
                "time_end": "18:00",
            },
            blocking=True,
        )

    mock_akuvox_device.add_schedule.assert_not_called()


async def test_add_schedule_rejects_empty_name(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
) -> None:
    """Test that an empty name is rejected by schema."""
    await _setup_entry(hass, mock_config_entry_data_none)

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            "add_schedule",
            service_data={
                "entity_id": ENTITY_ID,
                "schedule_type": "2",
                "name": "",
                "time_start": "08:00",
                "time_end": "18:00",
            },
            blocking=True,
        )

    mock_akuvox_device.add_schedule.assert_not_called()


@pytest.mark.parametrize(
    ("stype", "missing"),
    [
        ("0", "week"),
        ("0", "date_start"),
        ("0", "date_end"),
        ("1", "week"),
    ],
    ids=[
        "daterange_no_week",
        "daterange_no_date_start",
        "daterange_no_date_end",
        "weekly_no_week",
    ],
)
async def test_add_schedule_missing_required_field(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    stype: str,
    missing: str,
) -> None:
    """Test type-specific required fields raise ServiceValidationError."""
    await _setup_entry(hass, mock_config_entry_data_none)

    data: dict[str, Any] = {
        "entity_id": ENTITY_ID,
        "schedule_type": stype,
        "name": "Test",
        "week": ["mon", "tue"],
        "date_start": "2026-01-01",
        "date_end": "2026-12-31",
        "time_start": "08:00",
        "time_end": "18:00",
    }
    del data[missing]

    with pytest.raises(ServiceValidationError, match=missing):
        await hass.services.async_call(
            DOMAIN,
            "add_schedule",
            service_data=data,
            blocking=True,
        )

    mock_akuvox_device.add_schedule.assert_not_called()


async def test_add_schedule_daily_no_week_needed(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
) -> None:
    """Test type 2 (daily) succeeds without week or date fields."""
    await _setup_entry(hass, mock_config_entry_data_none)

    await hass.services.async_call(
        DOMAIN,
        "add_schedule",
        service_data={
            "entity_id": ENTITY_ID,
            "schedule_type": "2",
            "name": "Daily",
            "time_start": "09:00",
            "time_end": "17:00",
        },
        blocking=True,
    )

    mock_akuvox_device.add_schedule.assert_called_once_with(
        schedule_type="2",
        name="Daily",
        week=None,
        daily=None,
        date_start=None,
        date_end=None,
        time_start="09:00",
        time_end="17:00",
    )


@pytest.mark.parametrize(
    ("lib_exc", "ha_exc"),
    [
        (AkuvoxConnectionError, HomeAssistantError),
        (AkuvoxDeviceError, HomeAssistantError),
        (AkuvoxValidationError, ServiceValidationError),
    ],
    ids=["connection", "device", "validation"],
)
async def test_add_schedule_device_errors(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    lib_exc: type[Exception],
    ha_exc: type[Exception],
) -> None:
    """Test device errors are mapped to HA exceptions."""
    mock_akuvox_device.add_schedule.side_effect = lib_exc("fail")
    await _setup_entry(hass, mock_config_entry_data_none)

    with pytest.raises(ha_exc):
        await hass.services.async_call(
            DOMAIN,
            "add_schedule",
            service_data={
                "entity_id": ENTITY_ID,
                "schedule_type": "2",
                "name": "Test",
                "time_start": "08:00",
                "time_end": "18:00",
            },
            blocking=True,
        )


# ── modify_schedule tests ─────────────────────────────────────


async def test_modify_schedule_success(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_schedule_list: list[AccessSchedule],
) -> None:
    """Test modify_schedule passes id and updated fields to device."""
    mock_akuvox_device.list_schedules.return_value = mock_schedule_list
    await _setup_entry(hass, mock_config_entry_data_none)

    await hass.services.async_call(
        DOMAIN,
        "modify_schedule",
        service_data={
            "entity_id": ENTITY_ID,
            "id": "1",
            "name": "Updated Name",
            "time_start": "09:00",
            "time_end": "17:00",
        },
        blocking=True,
    )

    mock_akuvox_device.modify_schedule.assert_called_once_with(
        id="1",
        schedule_type=None,
        name="Updated Name",
        week=None,
        daily=None,
        date_start=None,
        date_end=None,
        time_start="09:00",
        time_end="17:00",
    )


async def test_modify_schedule_cloud_rejected(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_schedule_list: list[AccessSchedule],
) -> None:
    """Test cloud-provisioned schedule raises ServiceValidationError."""
    mock_akuvox_device.list_schedules.return_value = mock_schedule_list
    await _setup_entry(hass, mock_config_entry_data_none)

    with pytest.raises(ServiceValidationError, match="[Cc]loud"):
        await hass.services.async_call(
            DOMAIN,
            "modify_schedule",
            service_data={
                "entity_id": ENTITY_ID,
                "id": "2",
                "name": "Attempt Modify Cloud",
            },
            blocking=True,
        )

    mock_akuvox_device.modify_schedule.assert_not_called()


async def test_modify_schedule_not_found(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_schedule_list: list[AccessSchedule],
) -> None:
    """Test non-existent schedule ID raises HomeAssistantError."""
    mock_akuvox_device.list_schedules.return_value = mock_schedule_list
    await _setup_entry(hass, mock_config_entry_data_none)

    with pytest.raises(HomeAssistantError, match="not found"):
        await hass.services.async_call(
            DOMAIN,
            "modify_schedule",
            service_data={
                "entity_id": ENTITY_ID,
                "id": "999",
                "name": "Does Not Exist",
            },
            blocking=True,
        )

    mock_akuvox_device.modify_schedule.assert_not_called()


async def test_modify_schedule_invalid_field_values(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
) -> None:
    """Test invalid field values are rejected by schema."""
    await _setup_entry(hass, mock_config_entry_data_none)

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            "modify_schedule",
            service_data={
                "entity_id": ENTITY_ID,
                "id": "1",
                "schedule_type": "9",
            },
            blocking=True,
        )

    mock_akuvox_device.modify_schedule.assert_not_called()


async def test_modify_schedule_type_requires_fields(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_schedule_list: list[AccessSchedule],
) -> None:
    """Test schedule_type change validates required fields."""
    mock_akuvox_device.list_schedules.return_value = mock_schedule_list
    await _setup_entry(hass, mock_config_entry_data_none)

    with pytest.raises(ServiceValidationError, match="required"):
        await hass.services.async_call(
            DOMAIN,
            "modify_schedule",
            service_data={
                "entity_id": ENTITY_ID,
                "id": "1",
                "schedule_type": "1",
            },
            blocking=True,
        )

    mock_akuvox_device.modify_schedule.assert_not_called()


async def test_modify_schedule_fires_event(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_schedule_list: list[AccessSchedule],
) -> None:
    """Test modify_schedule fires akuvox_schedule_changed event."""
    mock_akuvox_device.list_schedules.return_value = mock_schedule_list
    entry = await _setup_entry(hass, mock_config_entry_data_none)
    events = async_capture_events(hass, EVENT_SCHEDULE_CHANGED)

    await hass.services.async_call(
        DOMAIN,
        "modify_schedule",
        service_data={
            "entity_id": ENTITY_ID,
            "id": "1",
            "name": "New Name",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data["action"] == "modify"
    assert events[0].data["schedule_id"] == "1"
    assert events[0].data["config_entry_id"] == entry.entry_id


@pytest.mark.parametrize(
    ("lib_exc", "ha_exc"),
    [
        (AkuvoxConnectionError, HomeAssistantError),
        (AkuvoxDeviceError, HomeAssistantError),
        (AkuvoxValidationError, ServiceValidationError),
    ],
    ids=["connection", "device", "validation"],
)
async def test_modify_schedule_device_errors(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_schedule_list: list[AccessSchedule],
    lib_exc: type[Exception],
    ha_exc: type[Exception],
) -> None:
    """Test device errors are mapped to HA exceptions."""
    mock_akuvox_device.list_schedules.return_value = mock_schedule_list
    mock_akuvox_device.modify_schedule.side_effect = lib_exc("fail")
    await _setup_entry(hass, mock_config_entry_data_none)

    with pytest.raises(ha_exc):
        await hass.services.async_call(
            DOMAIN,
            "modify_schedule",
            service_data={
                "entity_id": ENTITY_ID,
                "id": "1",
                "name": "Test",
            },
            blocking=True,
        )


async def test_modify_schedule_with_week_conversion(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_schedule_list: list[AccessSchedule],
) -> None:
    """Test week day names are converted to digit string."""
    mock_akuvox_device.list_schedules.return_value = mock_schedule_list
    await _setup_entry(hass, mock_config_entry_data_none)

    await hass.services.async_call(
        DOMAIN,
        "modify_schedule",
        service_data={
            "entity_id": ENTITY_ID,
            "id": "1",
            "week": ["mon", "wed", "fri"],
        },
        blocking=True,
    )

    mock_akuvox_device.modify_schedule.assert_called_once()
    call_kwargs = mock_akuvox_device.modify_schedule.call_args[1]
    assert call_kwargs["week"] == "135"


async def test_modify_schedule_with_date_conversion(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_schedule_list: list[AccessSchedule],
) -> None:
    """Test date objects are converted to YYYYMMDD strings."""
    mock_akuvox_device.list_schedules.return_value = mock_schedule_list
    await _setup_entry(hass, mock_config_entry_data_none)

    await hass.services.async_call(
        DOMAIN,
        "modify_schedule",
        service_data={
            "entity_id": ENTITY_ID,
            "id": "1",
            "date_start": "2026-03-01",
            "date_end": "2026-06-30",
        },
        blocking=True,
    )

    mock_akuvox_device.modify_schedule.assert_called_once()
    call_kwargs = mock_akuvox_device.modify_schedule.call_args[1]
    assert call_kwargs["date_start"] == "20260301"
    assert call_kwargs["date_end"] == "20260630"


# ── delete_schedule tests ─────────────────────────────────────


async def test_delete_schedule_success(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_schedule_list: list[AccessSchedule],
) -> None:
    """Test delete_schedule calls device.delete_schedule with id."""
    mock_akuvox_device.list_schedules.return_value = mock_schedule_list
    mock_akuvox_device.list_users.return_value = []
    await _setup_entry(hass, mock_config_entry_data_none)

    await hass.services.async_call(
        DOMAIN,
        "delete_schedule",
        service_data={
            "entity_id": ENTITY_ID,
            "id": "1",
        },
        blocking=True,
    )

    mock_akuvox_device.delete_schedule.assert_called_once_with(id="1")


async def test_delete_schedule_cloud_rejected(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_schedule_list: list[AccessSchedule],
) -> None:
    """Test cloud-provisioned schedule raises ServiceValidationError."""
    mock_akuvox_device.list_schedules.return_value = mock_schedule_list
    await _setup_entry(hass, mock_config_entry_data_none)

    with pytest.raises(ServiceValidationError, match="[Cc]loud"):
        await hass.services.async_call(
            DOMAIN,
            "delete_schedule",
            service_data={
                "entity_id": ENTITY_ID,
                "id": "2",
            },
            blocking=True,
        )

    mock_akuvox_device.delete_schedule.assert_not_called()


async def test_delete_schedule_not_found(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_schedule_list: list[AccessSchedule],
) -> None:
    """Test non-existent schedule raises HomeAssistantError."""
    mock_akuvox_device.list_schedules.return_value = mock_schedule_list
    await _setup_entry(hass, mock_config_entry_data_none)

    with pytest.raises(HomeAssistantError, match="not found"):
        await hass.services.async_call(
            DOMAIN,
            "delete_schedule",
            service_data={
                "entity_id": ENTITY_ID,
                "id": "999",
            },
            blocking=True,
        )

    mock_akuvox_device.delete_schedule.assert_not_called()


async def test_delete_schedule_fires_event(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_schedule_list: list[AccessSchedule],
) -> None:
    """Test delete_schedule fires akuvox_schedule_changed event."""
    mock_akuvox_device.list_schedules.return_value = mock_schedule_list
    mock_akuvox_device.list_users.return_value = []
    entry = await _setup_entry(hass, mock_config_entry_data_none)
    events = async_capture_events(hass, EVENT_SCHEDULE_CHANGED)

    await hass.services.async_call(
        DOMAIN,
        "delete_schedule",
        service_data={
            "entity_id": ENTITY_ID,
            "id": "1",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data["action"] == "delete"
    assert events[0].data["schedule_id"] == "1"
    assert events[0].data["config_entry_id"] == entry.entry_id


@pytest.mark.parametrize(
    ("lib_exc", "ha_exc"),
    [
        (AkuvoxConnectionError, HomeAssistantError),
        (AkuvoxDeviceError, HomeAssistantError),
        (AkuvoxValidationError, ServiceValidationError),
    ],
    ids=["connection", "device", "validation"],
)
async def test_delete_schedule_device_errors(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_schedule_list: list[AccessSchedule],
    lib_exc: type[Exception],
    ha_exc: type[Exception],
) -> None:
    """Test device errors are mapped to HA exceptions."""
    mock_akuvox_device.list_schedules.return_value = mock_schedule_list
    mock_akuvox_device.delete_schedule.side_effect = lib_exc("fail")
    await _setup_entry(hass, mock_config_entry_data_none)

    with pytest.raises(ha_exc):
        await hass.services.async_call(
            DOMAIN,
            "delete_schedule",
            service_data={
                "entity_id": ENTITY_ID,
                "id": "1",
            },
            blocking=True,
        )


async def test_delete_schedule_orphaned_warning(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_schedule_list: list[AccessSchedule],
    mock_user_list: list[User],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test warning logged when deleted schedule is referenced by users."""
    import logging

    mock_akuvox_device.list_schedules.return_value = mock_schedule_list
    mock_akuvox_device.list_users.return_value = mock_user_list
    await _setup_entry(hass, mock_config_entry_data_none)

    with caplog.at_level(logging.WARNING, logger="custom_components.akuvox"):
        await hass.services.async_call(
            DOMAIN,
            "delete_schedule",
            service_data={
                "entity_id": ENTITY_ID,
                "id": "1",
            },
            blocking=True,
        )

    assert "orphan" in caplog.text.lower()
    assert "John Doe" in caplog.text


async def test_delete_schedule_no_orphan_warning_on_failure(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_schedule_list: list[AccessSchedule],
    mock_user_list: list[User],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test no orphan warning when deletion fails."""
    import logging

    mock_akuvox_device.list_schedules.return_value = mock_schedule_list
    mock_akuvox_device.delete_schedule.side_effect = AkuvoxDeviceError("fail")
    mock_akuvox_device.list_users.return_value = mock_user_list
    await _setup_entry(hass, mock_config_entry_data_none)

    with (
        caplog.at_level(logging.WARNING, logger="custom_components.akuvox"),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            "delete_schedule",
            service_data={
                "entity_id": ENTITY_ID,
                "id": "1",
            },
            blocking=True,
        )

    assert "orphan" not in caplog.text.lower()


# ── add_user tests ────────────────────────────────────────────


async def test_add_user_success(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_schedule_list: list[AccessSchedule],
) -> None:
    """Test add_user calls device.add_user with correct params."""
    mock_akuvox_device.list_schedules.return_value = mock_schedule_list
    await _setup_entry(hass, mock_config_entry_data_none)

    await hass.services.async_call(
        DOMAIN,
        "add_user",
        service_data={
            "entity_id": ENTITY_ID,
            "name": "Jane Doe",
            "user_id": "jane.doe",
            "schedules": ["10"],
            "lift_floor_num": "5",
        },
        blocking=True,
    )

    mock_akuvox_device.add_user.assert_called_once()
    call_kwargs = mock_akuvox_device.add_user.call_args[1]
    assert call_kwargs["name"] == "Jane Doe"
    assert call_kwargs["user_id"] == "jane.doe"
    assert call_kwargs["schedule_relay"] == "10-1"
    assert call_kwargs["lift_floor_num"] == "5"
    assert call_kwargs["web_relay"] is None
    assert call_kwargs["private_pin"] is None
    assert call_kwargs["card_code"] is None


async def test_add_user_auto_user_id(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_schedule_list: list[AccessSchedule],
) -> None:
    """Test user_id is auto-generated as numeric timestamp when omitted."""
    mock_akuvox_device.list_schedules.return_value = mock_schedule_list
    await _setup_entry(hass, mock_config_entry_data_none)

    with patch("custom_components.akuvox.lock.time") as mock_time:
        mock_time.time.return_value = 1709153400.0
        await hass.services.async_call(
            DOMAIN,
            "add_user",
            service_data={
                "entity_id": ENTITY_ID,
                "name": "Jane Doe",
                "schedules": ["10"],
                "lift_floor_num": "5",
            },
            blocking=True,
        )

    mock_akuvox_device.add_user.assert_called_once()
    call_kwargs = mock_akuvox_device.add_user.call_args[1]
    assert call_kwargs["user_id"] == "1709153400"


async def test_add_user_multiple_schedules(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_schedule_list: list[AccessSchedule],
) -> None:
    """Test multiple schedules build correct schedule_relay."""
    local2 = AccessSchedule(
        id="3",
        schedule_type="1",
        name="Extra",
        display_id="30",
        source_type="1",
        week="12345",
        daily=None,
        date_start=None,
        date_end=None,
        time_start="09:00",
        time_end="17:00",
        mode=None,
        sun=None,
        mon=None,
        tue=None,
        wed=None,
        thur=None,
        fri=None,
        sat=None,
    )
    mock_akuvox_device.list_schedules.return_value = [
        *mock_schedule_list,
        local2,
    ]
    await _setup_entry(hass, mock_config_entry_data_none)

    await hass.services.async_call(
        DOMAIN,
        "add_user",
        service_data={
            "entity_id": ENTITY_ID,
            "name": "Jane Doe",
            "schedules": ["10", "30"],
            "lift_floor_num": "5",
        },
        blocking=True,
    )

    mock_akuvox_device.add_user.assert_called_once()
    call_kwargs = mock_akuvox_device.add_user.call_args[1]
    assert call_kwargs["schedule_relay"] == "10-1,30-1"


async def test_add_user_csv_schedules(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_schedule_list: list[AccessSchedule],
) -> None:
    """Test comma-separated schedule string is split correctly."""
    local2 = AccessSchedule(
        id="3",
        schedule_type="1",
        name="Extra",
        display_id="30",
        source_type="1",
        week="12345",
        daily=None,
        date_start=None,
        date_end=None,
        time_start="09:00",
        time_end="17:00",
        mode=None,
        sun=None,
        mon=None,
        tue=None,
        wed=None,
        thur=None,
        fri=None,
        sat=None,
    )
    mock_akuvox_device.list_schedules.return_value = [
        *mock_schedule_list,
        local2,
    ]
    await _setup_entry(hass, mock_config_entry_data_none)

    await hass.services.async_call(
        DOMAIN,
        "add_user",
        service_data={
            "entity_id": ENTITY_ID,
            "name": "Jane Doe",
            "schedules": "10, 30",
            "lift_floor_num": "5",
        },
        blocking=True,
    )

    mock_akuvox_device.add_user.assert_called_once()
    call_kwargs = mock_akuvox_device.add_user.call_args[1]
    assert call_kwargs["schedule_relay"] == "10-1,30-1"


async def test_add_user_with_optional_pin(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_schedule_list: list[AccessSchedule],
) -> None:
    """Test optional private_pin is passed through."""
    mock_akuvox_device.list_schedules.return_value = mock_schedule_list
    await _setup_entry(hass, mock_config_entry_data_none)

    await hass.services.async_call(
        DOMAIN,
        "add_user",
        service_data={
            "entity_id": ENTITY_ID,
            "name": "Jane Doe",
            "schedules": ["10"],
            "lift_floor_num": "5",
            "private_pin": "4321",
        },
        blocking=True,
    )

    mock_akuvox_device.add_user.assert_called_once()
    call_kwargs = mock_akuvox_device.add_user.call_args[1]
    assert call_kwargs["private_pin"] == "4321"


async def test_add_user_with_optional_card_code(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_schedule_list: list[AccessSchedule],
) -> None:
    """Test optional card_code is passed through."""
    mock_akuvox_device.list_schedules.return_value = mock_schedule_list
    await _setup_entry(hass, mock_config_entry_data_none)

    await hass.services.async_call(
        DOMAIN,
        "add_user",
        service_data={
            "entity_id": ENTITY_ID,
            "name": "Jane Doe",
            "schedules": ["10"],
            "lift_floor_num": "5",
            "card_code": "XYZ789",
        },
        blocking=True,
    )

    mock_akuvox_device.add_user.assert_called_once()
    call_kwargs = mock_akuvox_device.add_user.call_args[1]
    assert call_kwargs["card_code"] == "XYZ789"


async def test_add_user_with_optional_web_relay(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_schedule_list: list[AccessSchedule],
) -> None:
    """Test optional web_relay is passed through."""
    mock_akuvox_device.list_schedules.return_value = mock_schedule_list
    await _setup_entry(hass, mock_config_entry_data_none)

    await hass.services.async_call(
        DOMAIN,
        "add_user",
        service_data={
            "entity_id": ENTITY_ID,
            "name": "Jane Doe",
            "schedules": ["10"],
            "lift_floor_num": "5",
            "web_relay": "1",
        },
        blocking=True,
    )

    mock_akuvox_device.add_user.assert_called_once()
    call_kwargs = mock_akuvox_device.add_user.call_args[1]
    assert call_kwargs["web_relay"] == "1"


async def test_add_user_empty_schedules_rejected(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
) -> None:
    """Test empty schedules list raises error."""
    await _setup_entry(hass, mock_config_entry_data_none)

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            "add_user",
            service_data={
                "entity_id": ENTITY_ID,
                "name": "Jane Doe",
                "schedules": [],
                "lift_floor_num": "5",
            },
            blocking=True,
        )

    mock_akuvox_device.add_user.assert_not_called()


async def test_add_user_non_digit_schedule_rejected(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
) -> None:
    """Test non-digit schedule display_id raises schema error."""
    await _setup_entry(hass, mock_config_entry_data_none)

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            "add_user",
            service_data={
                "entity_id": ENTITY_ID,
                "name": "Jane Doe",
                "schedules": ["abc"],
                "lift_floor_num": "5",
            },
            blocking=True,
        )

    mock_akuvox_device.add_user.assert_not_called()


async def test_add_user_duplicate_schedules_rejected(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
) -> None:
    """Test duplicate schedule display_ids raises schema error."""
    await _setup_entry(hass, mock_config_entry_data_none)

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            "add_user",
            service_data={
                "entity_id": ENTITY_ID,
                "name": "Jane Doe",
                "schedules": ["10", "10"],
                "lift_floor_num": "5",
            },
            blocking=True,
        )

    mock_akuvox_device.add_user.assert_not_called()


@pytest.mark.parametrize(
    "bad_pin",
    ["12", "123", "123456789", "abcd", "12a4"],
    ids=["too-short-2", "too-short-3", "too-long-9", "letters", "mixed"],
)
async def test_add_user_invalid_pin(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_schedule_list: list[AccessSchedule],
    bad_pin: str,
) -> None:
    """Test invalid PIN (not 4-8 digits) raises error."""
    mock_akuvox_device.list_schedules.return_value = mock_schedule_list
    await _setup_entry(hass, mock_config_entry_data_none)

    with pytest.raises(ServiceValidationError, match="PIN"):
        await hass.services.async_call(
            DOMAIN,
            "add_user",
            service_data={
                "entity_id": ENTITY_ID,
                "name": "Jane Doe",
                "schedules": ["10"],
                "lift_floor_num": "5",
                "private_pin": bad_pin,
            },
            blocking=True,
        )

    mock_akuvox_device.add_user.assert_not_called()


async def test_add_user_cloud_schedule_rejected(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_schedule_list: list[AccessSchedule],
) -> None:
    """Test referencing cloud schedule raises ServiceValidationError."""
    mock_akuvox_device.list_schedules.return_value = mock_schedule_list
    await _setup_entry(hass, mock_config_entry_data_none)

    with pytest.raises(ServiceValidationError, match="[Cc]loud"):
        await hass.services.async_call(
            DOMAIN,
            "add_user",
            service_data={
                "entity_id": ENTITY_ID,
                "name": "Jane Doe",
                "schedules": ["20"],
                "lift_floor_num": "5",
            },
            blocking=True,
        )

    mock_akuvox_device.add_user.assert_not_called()


async def test_add_user_nonexistent_schedule_rejected(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_schedule_list: list[AccessSchedule],
) -> None:
    """Test referencing non-existent schedule raises error."""
    mock_akuvox_device.list_schedules.return_value = mock_schedule_list
    await _setup_entry(hass, mock_config_entry_data_none)

    with pytest.raises(ServiceValidationError, match="not found"):
        await hass.services.async_call(
            DOMAIN,
            "add_user",
            service_data={
                "entity_id": ENTITY_ID,
                "name": "Jane Doe",
                "schedules": ["999"],
                "lift_floor_num": "5",
            },
            blocking=True,
        )

    mock_akuvox_device.add_user.assert_not_called()


async def test_add_user_schedule_check_validation_error(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
) -> None:
    """Test AkuvoxValidationError from list_schedules maps correctly."""
    mock_akuvox_device.list_schedules.side_effect = AkuvoxValidationError("bad")
    await _setup_entry(hass, mock_config_entry_data_none)

    with pytest.raises(ServiceValidationError, match="verify schedules"):
        await hass.services.async_call(
            DOMAIN,
            "add_user",
            service_data={
                "entity_id": ENTITY_ID,
                "name": "Jane Doe",
                "schedules": ["10"],
                "lift_floor_num": "5",
            },
            blocking=True,
        )


async def test_add_user_fires_event(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_schedule_list: list[AccessSchedule],
) -> None:
    """Test add_user fires akuvox_user_changed event."""
    mock_akuvox_device.list_schedules.return_value = mock_schedule_list
    entry = await _setup_entry(hass, mock_config_entry_data_none)
    events = async_capture_events(hass, EVENT_USER_CHANGED)

    await hass.services.async_call(
        DOMAIN,
        "add_user",
        service_data={
            "entity_id": ENTITY_ID,
            "name": "Jane Doe",
            "schedules": ["10"],
            "lift_floor_num": "5",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data["action"] == "add"
    assert events[0].data["config_entry_id"] == entry.entry_id


@pytest.mark.parametrize(
    ("lib_exc", "ha_exc"),
    [
        (AkuvoxConnectionError, HomeAssistantError),
        (AkuvoxDeviceError, HomeAssistantError),
        (AkuvoxValidationError, ServiceValidationError),
    ],
    ids=["connection", "device", "validation"],
)
async def test_add_user_device_errors(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_schedule_list: list[AccessSchedule],
    lib_exc: type[Exception],
    ha_exc: type[Exception],
) -> None:
    """Test device errors are mapped to HA exceptions."""
    mock_akuvox_device.list_schedules.return_value = mock_schedule_list
    mock_akuvox_device.add_user.side_effect = lib_exc("fail")
    await _setup_entry(hass, mock_config_entry_data_none)

    with pytest.raises(ha_exc):
        await hass.services.async_call(
            DOMAIN,
            "add_user",
            service_data={
                "entity_id": ENTITY_ID,
                "name": "Jane Doe",
                "schedules": ["10"],
                "lift_floor_num": "5",
            },
            blocking=True,
        )


# ── modify_user tests ─────────────────────────────────────────


async def test_modify_user_success(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_user_list: list[User],
) -> None:
    """Test modify_user calls device.modify_user with correct params."""
    mock_akuvox_device.list_users.return_value = mock_user_list
    await _setup_entry(hass, mock_config_entry_data_none)

    await hass.services.async_call(
        DOMAIN,
        "modify_user",
        service_data={
            "entity_id": ENTITY_ID,
            "id": "42",
            "name": "Updated Name",
            "lift_floor_num": "7",
        },
        blocking=True,
    )

    mock_akuvox_device.modify_user.assert_called_once()
    call_kwargs = mock_akuvox_device.modify_user.call_args[1]
    assert call_kwargs["id"] == "42"
    assert call_kwargs["name"] == "Updated Name"
    assert call_kwargs["lift_floor_num"] == "7"


async def test_modify_user_cloud_rejected(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_user_list: list[User],
) -> None:
    """Test modifying a cloud user raises ServiceValidationError."""
    mock_akuvox_device.list_users.return_value = mock_user_list
    await _setup_entry(hass, mock_config_entry_data_none)

    with pytest.raises(ServiceValidationError, match="[Cc]loud"):
        await hass.services.async_call(
            DOMAIN,
            "modify_user",
            service_data={
                "entity_id": ENTITY_ID,
                "id": "99",
                "name": "New Name",
            },
            blocking=True,
        )

    mock_akuvox_device.modify_user.assert_not_called()


async def test_modify_user_not_found(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_user_list: list[User],
) -> None:
    """Test modifying a non-existent user raises HomeAssistantError."""
    mock_akuvox_device.list_users.return_value = mock_user_list
    await _setup_entry(hass, mock_config_entry_data_none)

    with pytest.raises(HomeAssistantError, match="not found"):
        await hass.services.async_call(
            DOMAIN,
            "modify_user",
            service_data={
                "entity_id": ENTITY_ID,
                "id": "999",
                "name": "Ghost",
            },
            blocking=True,
        )

    mock_akuvox_device.modify_user.assert_not_called()


async def test_modify_user_schedule_relay_cloud_rejected(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_user_list: list[User],
    mock_schedule_list: list[AccessSchedule],
) -> None:
    """Test schedule_relay referencing cloud schedule raises error."""
    mock_akuvox_device.list_users.return_value = mock_user_list
    mock_akuvox_device.list_schedules.return_value = mock_schedule_list
    await _setup_entry(hass, mock_config_entry_data_none)

    with pytest.raises(ServiceValidationError, match="[Cc]loud"):
        await hass.services.async_call(
            DOMAIN,
            "modify_user",
            service_data={
                "entity_id": ENTITY_ID,
                "id": "42",
                "schedule_relay": "20-1",
            },
            blocking=True,
        )

    mock_akuvox_device.modify_user.assert_not_called()


@pytest.mark.parametrize(
    "bad_pin",
    ["12", "123", "123456789", "abcd", "12a4"],
    ids=["too-short-2", "too-short-3", "too-long-9", "letters", "mixed"],
)
async def test_modify_user_invalid_pin(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_user_list: list[User],
    bad_pin: str,
) -> None:
    """Test invalid PIN (not 4-8 digits) raises error."""
    mock_akuvox_device.list_users.return_value = mock_user_list
    await _setup_entry(hass, mock_config_entry_data_none)

    with pytest.raises(ServiceValidationError, match="PIN"):
        await hass.services.async_call(
            DOMAIN,
            "modify_user",
            service_data={
                "entity_id": ENTITY_ID,
                "id": "42",
                "private_pin": bad_pin,
            },
            blocking=True,
        )

    mock_akuvox_device.modify_user.assert_not_called()


async def test_modify_user_malformed_schedule_relay(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_user_list: list[User],
) -> None:
    """Test malformed schedule_relay entry raises ServiceValidationError."""
    mock_akuvox_device.list_users.return_value = mock_user_list
    await _setup_entry(hass, mock_config_entry_data_none)

    with pytest.raises(ServiceValidationError, match="Invalid schedule_relay"):
        await hass.services.async_call(
            DOMAIN,
            "modify_user",
            service_data={
                "entity_id": ENTITY_ID,
                "id": "42",
                "schedule_relay": "bad-format-here",
            },
            blocking=True,
        )

    mock_akuvox_device.modify_user.assert_not_called()


async def test_modify_user_semicolon_schedule_relay_normalized(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_user_list: list[User],
    mock_schedule_list: list[AccessSchedule],
) -> None:
    """Test semicolon-separated schedule_relay is normalized to commas."""
    mock_akuvox_device.list_users.return_value = mock_user_list
    mock_akuvox_device.list_schedules.return_value = mock_schedule_list
    await _setup_entry(hass, mock_config_entry_data_none)

    await hass.services.async_call(
        DOMAIN,
        "modify_user",
        service_data={
            "entity_id": ENTITY_ID,
            "id": "42",
            "schedule_relay": "10-1;10-2;",
        },
        blocking=True,
    )

    call_kwargs = mock_akuvox_device.modify_user.call_args[1]
    assert call_kwargs["schedule_relay"] == "10-1,10-2"


async def test_modify_user_event_fired(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_user_list: list[User],
) -> None:
    """Test modify_user fires akuvox_user_changed event."""
    mock_akuvox_device.list_users.return_value = mock_user_list
    entry = await _setup_entry(hass, mock_config_entry_data_none)
    events = async_capture_events(hass, EVENT_USER_CHANGED)

    await hass.services.async_call(
        DOMAIN,
        "modify_user",
        service_data={
            "entity_id": ENTITY_ID,
            "id": "42",
            "name": "Updated Name",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data["action"] == "modify"
    assert events[0].data["device_user_id"] == "42"
    assert events[0].data["config_entry_id"] == entry.entry_id


@pytest.mark.parametrize(
    ("lib_exc", "ha_exc"),
    [
        (AkuvoxConnectionError, HomeAssistantError),
        (AkuvoxDeviceError, HomeAssistantError),
        (AkuvoxValidationError, ServiceValidationError),
    ],
    ids=["connection", "device", "validation"],
)
async def test_modify_user_device_errors(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_user_list: list[User],
    lib_exc: type[Exception],
    ha_exc: type[Exception],
) -> None:
    """Test device errors are mapped to HA exceptions."""
    mock_akuvox_device.list_users.return_value = mock_user_list
    mock_akuvox_device.modify_user.side_effect = lib_exc("fail")
    await _setup_entry(hass, mock_config_entry_data_none)

    with pytest.raises(ha_exc):
        await hass.services.async_call(
            DOMAIN,
            "modify_user",
            service_data={
                "entity_id": ENTITY_ID,
                "id": "42",
                "name": "Updated Name",
            },
            blocking=True,
        )


# ── delete_user (US8) ────────────────────────────────────────


async def test_delete_user_success(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_user_list: list[User],
) -> None:
    """Test delete_user calls device.delete_user with id."""
    mock_akuvox_device.list_users.return_value = mock_user_list
    await _setup_entry(hass, mock_config_entry_data_none)

    await hass.services.async_call(
        DOMAIN,
        "delete_user",
        service_data={
            "entity_id": ENTITY_ID,
            "id": "42",
        },
        blocking=True,
    )

    mock_akuvox_device.delete_user.assert_called_once_with(id="42")


async def test_delete_user_cloud_rejected(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_user_list: list[User],
) -> None:
    """Test cloud-provisioned user raises ServiceValidationError."""
    mock_akuvox_device.list_users.return_value = mock_user_list
    await _setup_entry(hass, mock_config_entry_data_none)

    with pytest.raises(ServiceValidationError, match="[Cc]loud"):
        await hass.services.async_call(
            DOMAIN,
            "delete_user",
            service_data={
                "entity_id": ENTITY_ID,
                "id": "99",
            },
            blocking=True,
        )

    mock_akuvox_device.delete_user.assert_not_called()


async def test_delete_user_not_found(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_user_list: list[User],
) -> None:
    """Test non-existent user raises HomeAssistantError."""
    mock_akuvox_device.list_users.return_value = mock_user_list
    await _setup_entry(hass, mock_config_entry_data_none)

    with pytest.raises(HomeAssistantError, match="not found"):
        await hass.services.async_call(
            DOMAIN,
            "delete_user",
            service_data={
                "entity_id": ENTITY_ID,
                "id": "999",
            },
            blocking=True,
        )

    mock_akuvox_device.delete_user.assert_not_called()


async def test_delete_user_event_fired(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_user_list: list[User],
) -> None:
    """Test delete_user fires akuvox_user_changed event."""
    mock_akuvox_device.list_users.return_value = mock_user_list
    entry = await _setup_entry(hass, mock_config_entry_data_none)
    events = async_capture_events(hass, EVENT_USER_CHANGED)

    await hass.services.async_call(
        DOMAIN,
        "delete_user",
        service_data={
            "entity_id": ENTITY_ID,
            "id": "42",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data["action"] == "delete"
    assert events[0].data["device_user_id"] == "42"
    assert events[0].data["config_entry_id"] == entry.entry_id


@pytest.mark.parametrize(
    ("lib_exc", "ha_exc"),
    [
        (AkuvoxConnectionError, HomeAssistantError),
        (AkuvoxDeviceError, HomeAssistantError),
        (AkuvoxValidationError, ServiceValidationError),
    ],
    ids=["connection", "device", "validation"],
)
async def test_delete_user_device_errors(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_user_list: list[User],
    lib_exc: type[Exception],
    ha_exc: type[Exception],
) -> None:
    """Test device errors are mapped to HA exceptions."""
    mock_akuvox_device.list_users.return_value = mock_user_list
    mock_akuvox_device.delete_user.side_effect = lib_exc("fail")
    await _setup_entry(hass, mock_config_entry_data_none)

    with pytest.raises(ha_exc):
        await hass.services.async_call(
            DOMAIN,
            "delete_user",
            service_data={
                "entity_id": ENTITY_ID,
                "id": "42",
            },
            blocking=True,
        )


# ── add_user_schedule_relay (Convenience) ─────────────────────


async def test_add_user_schedule_relay_success(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_user_list: list[User],
    mock_schedule_list: list[AccessSchedule],
) -> None:
    """Test add_user_schedule_relay appends pair and calls modify_user."""
    mock_akuvox_device.list_users.return_value = mock_user_list
    mock_akuvox_device.list_schedules.return_value = mock_schedule_list
    await _setup_entry(hass, mock_config_entry_data_none)

    await hass.services.async_call(
        DOMAIN,
        "add_user_schedule_relay",
        service_data={
            "entity_id": ENTITY_ID,
            "id": "42",
            "schedule_id": "10",
            "relay_id": "2",
        },
        blocking=True,
    )

    call_kwargs = mock_akuvox_device.modify_user.call_args[1]
    assert call_kwargs["id"] == "42"
    assert call_kwargs["schedule_relay"] == "10-1,10-2"


async def test_add_user_schedule_relay_duplicate(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_user_list: list[User],
    mock_schedule_list: list[AccessSchedule],
) -> None:
    """Test duplicate pair raises ServiceValidationError."""
    mock_akuvox_device.list_users.return_value = mock_user_list
    mock_akuvox_device.list_schedules.return_value = mock_schedule_list
    await _setup_entry(hass, mock_config_entry_data_none)

    with pytest.raises(ServiceValidationError, match="[Aa]lready assigned"):
        await hass.services.async_call(
            DOMAIN,
            "add_user_schedule_relay",
            service_data={
                "entity_id": ENTITY_ID,
                "id": "42",
                "schedule_id": "10",
                "relay_id": "1",
            },
            blocking=True,
        )

    mock_akuvox_device.modify_user.assert_not_called()


async def test_add_user_schedule_relay_cloud_user(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_user_list: list[User],
) -> None:
    """Test cloud user raises ServiceValidationError."""
    mock_akuvox_device.list_users.return_value = mock_user_list
    await _setup_entry(hass, mock_config_entry_data_none)

    with pytest.raises(ServiceValidationError, match="[Cc]loud"):
        await hass.services.async_call(
            DOMAIN,
            "add_user_schedule_relay",
            service_data={
                "entity_id": ENTITY_ID,
                "id": "99",
                "schedule_id": "10",
                "relay_id": "1",
            },
            blocking=True,
        )

    mock_akuvox_device.modify_user.assert_not_called()


async def test_add_user_schedule_relay_cloud_schedule(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_user_list: list[User],
    mock_schedule_list: list[AccessSchedule],
) -> None:
    """Test cloud schedule reference raises ServiceValidationError."""
    mock_akuvox_device.list_users.return_value = mock_user_list
    mock_akuvox_device.list_schedules.return_value = mock_schedule_list
    await _setup_entry(hass, mock_config_entry_data_none)

    with pytest.raises(ServiceValidationError, match="[Cc]loud"):
        await hass.services.async_call(
            DOMAIN,
            "add_user_schedule_relay",
            service_data={
                "entity_id": ENTITY_ID,
                "id": "42",
                "schedule_id": "20",
                "relay_id": "1",
            },
            blocking=True,
        )

    mock_akuvox_device.modify_user.assert_not_called()


async def test_add_user_schedule_relay_user_not_found(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_user_list: list[User],
) -> None:
    """Test user not found raises HomeAssistantError."""
    mock_akuvox_device.list_users.return_value = mock_user_list
    await _setup_entry(hass, mock_config_entry_data_none)

    with pytest.raises(HomeAssistantError, match="not found"):
        await hass.services.async_call(
            DOMAIN,
            "add_user_schedule_relay",
            service_data={
                "entity_id": ENTITY_ID,
                "id": "999",
                "schedule_id": "10",
                "relay_id": "1",
            },
            blocking=True,
        )

    mock_akuvox_device.modify_user.assert_not_called()


async def test_add_user_schedule_relay_event_fired(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_user_list: list[User],
    mock_schedule_list: list[AccessSchedule],
) -> None:
    """Test add_user_schedule_relay fires event."""
    mock_akuvox_device.list_users.return_value = mock_user_list
    mock_akuvox_device.list_schedules.return_value = mock_schedule_list
    entry = await _setup_entry(hass, mock_config_entry_data_none)
    events = async_capture_events(hass, EVENT_USER_CHANGED)

    await hass.services.async_call(
        DOMAIN,
        "add_user_schedule_relay",
        service_data={
            "entity_id": ENTITY_ID,
            "id": "42",
            "schedule_id": "10",
            "relay_id": "2",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data["action"] == "add_schedule_relay"
    assert events[0].data["device_user_id"] == "42"
    assert events[0].data["schedule_id"] == "10"
    assert events[0].data["relay_id"] == "2"
    assert events[0].data["config_entry_id"] == entry.entry_id


# ── remove_user_schedule_relay (Convenience) ──────────────────


async def test_remove_user_schedule_relay_success(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_user_list: list[User],
) -> None:
    """Test remove_user_schedule_relay removes pair and calls modify_user."""
    # Give user two pairs so removal leaves one
    from dataclasses import replace

    mock_user_list[0] = replace(mock_user_list[0], schedule_relay="10-1,10-2")
    mock_akuvox_device.list_users.return_value = mock_user_list
    await _setup_entry(hass, mock_config_entry_data_none)

    await hass.services.async_call(
        DOMAIN,
        "remove_user_schedule_relay",
        service_data={
            "entity_id": ENTITY_ID,
            "id": "42",
            "schedule_id": "10",
            "relay_id": "2",
        },
        blocking=True,
    )

    call_kwargs = mock_akuvox_device.modify_user.call_args[1]
    assert call_kwargs["id"] == "42"
    assert call_kwargs["schedule_relay"] == "10-1"


async def test_remove_user_schedule_relay_not_assigned(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_user_list: list[User],
) -> None:
    """Test pair not found raises ServiceValidationError."""
    mock_akuvox_device.list_users.return_value = mock_user_list
    await _setup_entry(hass, mock_config_entry_data_none)

    with pytest.raises(ServiceValidationError, match="not assigned"):
        await hass.services.async_call(
            DOMAIN,
            "remove_user_schedule_relay",
            service_data={
                "entity_id": ENTITY_ID,
                "id": "42",
                "schedule_id": "99",
                "relay_id": "1",
            },
            blocking=True,
        )

    mock_akuvox_device.modify_user.assert_not_called()


async def test_remove_user_schedule_relay_last_pair(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_user_list: list[User],
) -> None:
    """Test removing last pair raises ServiceValidationError."""
    mock_akuvox_device.list_users.return_value = mock_user_list
    await _setup_entry(hass, mock_config_entry_data_none)

    with pytest.raises(ServiceValidationError, match="[Ll]ast pair"):
        await hass.services.async_call(
            DOMAIN,
            "remove_user_schedule_relay",
            service_data={
                "entity_id": ENTITY_ID,
                "id": "42",
                "schedule_id": "10",
                "relay_id": "1",
            },
            blocking=True,
        )

    mock_akuvox_device.modify_user.assert_not_called()


async def test_remove_user_schedule_relay_cloud_user(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_user_list: list[User],
) -> None:
    """Test cloud user raises ServiceValidationError."""
    mock_akuvox_device.list_users.return_value = mock_user_list
    await _setup_entry(hass, mock_config_entry_data_none)

    with pytest.raises(ServiceValidationError, match="[Cc]loud"):
        await hass.services.async_call(
            DOMAIN,
            "remove_user_schedule_relay",
            service_data={
                "entity_id": ENTITY_ID,
                "id": "99",
                "schedule_id": "20",
                "relay_id": "1",
            },
            blocking=True,
        )

    mock_akuvox_device.modify_user.assert_not_called()


async def test_remove_user_schedule_relay_user_not_found(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_user_list: list[User],
) -> None:
    """Test user not found raises HomeAssistantError."""
    mock_akuvox_device.list_users.return_value = mock_user_list
    await _setup_entry(hass, mock_config_entry_data_none)

    with pytest.raises(HomeAssistantError, match="not found"):
        await hass.services.async_call(
            DOMAIN,
            "remove_user_schedule_relay",
            service_data={
                "entity_id": ENTITY_ID,
                "id": "999",
                "schedule_id": "10",
                "relay_id": "1",
            },
            blocking=True,
        )

    mock_akuvox_device.modify_user.assert_not_called()


async def test_remove_user_schedule_relay_event_fired(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_user_list: list[User],
) -> None:
    """Test remove_user_schedule_relay fires event."""
    from dataclasses import replace

    mock_user_list[0] = replace(mock_user_list[0], schedule_relay="10-1,10-2")
    mock_akuvox_device.list_users.return_value = mock_user_list
    entry = await _setup_entry(hass, mock_config_entry_data_none)
    events = async_capture_events(hass, EVENT_USER_CHANGED)

    await hass.services.async_call(
        DOMAIN,
        "remove_user_schedule_relay",
        service_data={
            "entity_id": ENTITY_ID,
            "id": "42",
            "schedule_id": "10",
            "relay_id": "2",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data["action"] == "remove_schedule_relay"
    assert events[0].data["device_user_id"] == "42"
    assert events[0].data["schedule_id"] == "10"
    assert events[0].data["relay_id"] == "2"
    assert events[0].data["config_entry_id"] == entry.entry_id
