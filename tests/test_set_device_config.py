# SPDX-FileCopyrightText: 2026 Turzi
# SPDX-License-Identifier: Apache-2.0

"""Tests for the admin-only set_device_config action."""

from __future__ import annotations

import logging
from typing import Any
from unittest.mock import AsyncMock

import pytest
import voluptuous as vol
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import (
    HomeAssistantError,
    ServiceValidationError,
    Unauthorized,
)
from homeassistant.helpers import device_registry as dr
from pylocal_akuvox import (
    AkuvoxAuthenticationError,
    AkuvoxConnectionError,
    AkuvoxDeviceError,
    AkuvoxValidationError,
)

from custom_components.local_akuvox.const import DOMAIN
from tests.conftest import setup_entry

SERVICE = "set_device_config"


@pytest.fixture(autouse=True)
def _async_set_device_config(mock_akuvox_device: AsyncMock) -> None:
    """Make the device mock's set_device_config awaitable."""
    mock_akuvox_device.set_device_config = AsyncMock(return_value=None)


def _device_id(hass: HomeAssistant, entry_id: str) -> str:
    """Return the registry id of the device created for a config entry."""
    devices = dr.async_entries_for_config_entry(dr.async_get(hass), entry_id)
    assert len(devices) == 1
    return devices[0].id


async def test_service_registered(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
) -> None:
    """The action exists once the integration is loaded."""
    await setup_entry(hass, mock_config_entry_data_none)

    assert hass.services.has_service(DOMAIN, SERVICE)


async def test_writes_settings_as_text(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
) -> None:
    """Numbers and booleans reach the device as the strings it expects."""
    entry = await setup_entry(hass, mock_config_entry_data_none)

    await hass.services.async_call(
        DOMAIN,
        SERVICE,
        {
            "device_id": _device_id(hass, entry.entry_id),
            "settings": {
                "Config.Settings.LOGLEVEL.Level": 3,
                "Config.Settings.LOGLEVEL.RemoteSyslog": True,
                "Config.Settings.LOGLEVEL.RemoteServer": "10.0.0.5",
            },
        },
        blocking=True,
    )

    mock_akuvox_device.set_device_config.assert_awaited_once_with(
        {
            "Config.Settings.LOGLEVEL.Level": "3",
            "Config.Settings.LOGLEVEL.RemoteSyslog": "1",
            "Config.Settings.LOGLEVEL.RemoteServer": "10.0.0.5",
        }
    )


async def test_config_is_reread_after_writing(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
) -> None:
    """The next update re-reads the device config, once."""
    entry = await setup_entry(hass, mock_config_entry_data_none)
    coordinator = hass.data[DOMAIN][entry.entry_id]
    mock_akuvox_device.get_device_config.reset_mock()

    await hass.services.async_call(
        DOMAIN,
        SERVICE,
        {
            "device_id": _device_id(hass, entry.entry_id),
            "settings": {"Config.DoorSetting.RELAY.HoldDelayA": "7"},
        },
        blocking=True,
    )
    await coordinator.async_refresh()
    await coordinator.async_refresh()

    mock_akuvox_device.get_device_config.assert_awaited_once()


@pytest.mark.parametrize(
    "settings",
    [
        {},
        {"Settings.LOGLEVEL.Level": "3"},
        {"Config.Level": "3"},
        {"Config.Settings.LOGLEVEL.Level": ["3"]},
        {f"Config.Settings.KEY.Item{i}": "1" for i in range(51)},
    ],
    ids=["empty", "no-config-prefix", "too-short", "list-value", "too-many"],
)
async def test_rejects_invalid_settings(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    settings: dict[str, Any],
) -> None:
    """Malformed settings never reach the device."""
    entry = await setup_entry(hass, mock_config_entry_data_none)

    with pytest.raises((vol.Invalid, ServiceValidationError)):
        await hass.services.async_call(
            DOMAIN,
            SERVICE,
            {"device_id": _device_id(hass, entry.entry_id), "settings": settings},
            blocking=True,
        )

    mock_akuvox_device.set_device_config.assert_not_awaited()


async def test_unknown_device_changes_nothing(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
) -> None:
    """One unknown id in the list stops the call before any write."""
    entry = await setup_entry(hass, mock_config_entry_data_none)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE,
            {
                "device_id": [_device_id(hass, entry.entry_id), "not-a-device"],
                "settings": {"Config.Settings.LOGLEVEL.Level": "3"},
            },
            blocking=True,
        )

    mock_akuvox_device.set_device_config.assert_not_awaited()


@pytest.mark.parametrize(
    ("library_error", "ha_error"),
    [
        (AkuvoxValidationError("bad key"), ServiceValidationError),
        (AkuvoxAuthenticationError("denied"), HomeAssistantError),
        (AkuvoxConnectionError("offline"), HomeAssistantError),
        (AkuvoxDeviceError("busy"), HomeAssistantError),
    ],
    ids=["validation", "auth", "connection", "device"],
)
async def test_device_errors_are_reported(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    library_error: Exception,
    ha_error: type[Exception],
) -> None:
    """Library errors surface as Home Assistant errors."""
    entry = await setup_entry(hass, mock_config_entry_data_none)
    mock_akuvox_device.set_device_config.side_effect = library_error

    with pytest.raises(ha_error):
        await hass.services.async_call(
            DOMAIN,
            SERVICE,
            {
                "device_id": _device_id(hass, entry.entry_id),
                "settings": {"Config.Settings.LOGLEVEL.Level": "3"},
            },
            blocking=True,
        )


async def test_non_admin_is_refused(
    hass: HomeAssistant,
    hass_read_only_user: Any,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
) -> None:
    """Only administrators may write device settings."""
    entry = await setup_entry(hass, mock_config_entry_data_none)

    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            SERVICE,
            {
                "device_id": _device_id(hass, entry.entry_id),
                "settings": {"Config.Settings.LOGLEVEL.Level": "3"},
            },
            blocking=True,
            context=Context(user_id=hass_read_only_user.id),
        )

    mock_akuvox_device.set_device_config.assert_not_awaited()


async def test_setting_values_stay_out_of_the_log(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Keys are logged, values (which may be passwords) are not."""
    entry = await setup_entry(hass, mock_config_entry_data_none)
    caplog.set_level(logging.DEBUG, logger="custom_components.local_akuvox")

    await hass.services.async_call(
        DOMAIN,
        SERVICE,
        {
            "device_id": _device_id(hass, entry.entry_id),
            "settings": {"Config.Account1.GENERAL.Pwd": "s3cret-value"},
        },
        blocking=True,
    )

    assert "Config.Account1.GENERAL.Pwd" in caplog.text
    assert "s3cret-value" not in caplog.text
