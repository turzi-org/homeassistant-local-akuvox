# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Tests for the Akuvox coordinator."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed
from pylocal_akuvox import (
    AkuvoxAuthenticationError,
    AkuvoxConnectionError,
    AkuvoxDeviceError,
    AkuvoxParseError,
    DeviceInfo,
)

from custom_components.akuvox.const import DEFAULT_SCAN_INTERVAL
from custom_components.akuvox.coordinator import (
    AkuvoxCoordinatorData,
    AkuvoxDataUpdateCoordinator,
)


async def test_coordinator_fetches_data(
    hass: HomeAssistant,
    mock_device_info: DeviceInfo,
    mock_relay_status: dict[str, Any],
) -> None:
    """Test coordinator fetches device info and relay status."""
    device = AsyncMock()
    device.get_info = AsyncMock(return_value=mock_device_info)
    device.get_relay_status = AsyncMock(return_value=mock_relay_status)

    coordinator = AkuvoxDataUpdateCoordinator(hass=hass, device=device)
    data = await coordinator._async_update_data()

    assert isinstance(data, AkuvoxCoordinatorData)
    assert data.device_info == mock_device_info
    assert data.relay_status == mock_relay_status
    device.get_relay_status.assert_awaited_once()
    device.get_info.assert_awaited_once()


async def test_coordinator_update_failed_on_connection_error(
    hass: HomeAssistant,
) -> None:
    """Test coordinator raises UpdateFailed on AkuvoxConnectionError."""
    device = AsyncMock()
    device.get_relay_status = AsyncMock(
        side_effect=AkuvoxConnectionError("Connection failed"),
    )

    coordinator = AkuvoxDataUpdateCoordinator(hass=hass, device=device)

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_coordinator_update_failed_on_device_error(
    hass: HomeAssistant,
) -> None:
    """Test coordinator raises UpdateFailed on AkuvoxDeviceError."""
    device = AsyncMock()
    device.get_relay_status = AsyncMock(
        side_effect=AkuvoxDeviceError("Device error"),
    )

    coordinator = AkuvoxDataUpdateCoordinator(hass=hass, device=device)

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_coordinator_update_failed_on_parse_error(
    hass: HomeAssistant,
) -> None:
    """Test coordinator raises UpdateFailed on AkuvoxParseError."""
    device = AsyncMock()
    device.get_relay_status = AsyncMock(
        side_effect=AkuvoxParseError("Parse error"),
    )

    coordinator = AkuvoxDataUpdateCoordinator(hass=hass, device=device)

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_coordinator_auth_failed_on_auth_error(
    hass: HomeAssistant,
) -> None:
    """Test coordinator raises ConfigEntryAuthFailed on auth error."""
    device = AsyncMock()
    device.get_relay_status = AsyncMock(
        side_effect=AkuvoxAuthenticationError("Auth failed"),
    )

    coordinator = AkuvoxDataUpdateCoordinator(hass=hass, device=device)

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


async def test_coordinator_caches_device_info(
    hass: HomeAssistant,
    mock_device_info: DeviceInfo,
    mock_relay_status: dict[str, Any],
) -> None:
    """Test coordinator caches device_info after first call."""
    device = AsyncMock()
    device.get_info = AsyncMock(return_value=mock_device_info)
    device.get_relay_status = AsyncMock(return_value=mock_relay_status)

    coordinator = AkuvoxDataUpdateCoordinator(hass=hass, device=device)

    # First call should fetch device info
    await coordinator._async_update_data()
    assert device.get_info.await_count == 1

    # Second call should use cached device info
    await coordinator._async_update_data()
    assert device.get_info.await_count == 1


async def test_coordinator_update_interval(
    hass: HomeAssistant,
) -> None:
    """Test coordinator uses 30s update interval."""
    device = AsyncMock()
    coordinator = AkuvoxDataUpdateCoordinator(hass=hass, device=device)
    assert coordinator.update_interval == timedelta(
        seconds=DEFAULT_SCAN_INTERVAL,
    )
