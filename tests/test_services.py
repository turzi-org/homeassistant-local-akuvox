# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Tests for Akuvox schedule and user CRUD services."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
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
)
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.akuvox.const import DOMAIN

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
    assert first["schedule_type"] == "0"
    assert first["name"] == "Weekday Access"
    assert first["week"] == "12345"
    assert first["time_start"] == "08:00"
    assert first["time_end"] == "18:00"
    # Cloud schedule has non-empty source_type
    cloud = schedules[1]
    assert isinstance(cloud, dict)
    assert cloud["source_type"] == "cloud"


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
    ],
    ids=["connection", "auth", "parse"],
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
