# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Tests for the Akuvox integration setup."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.akuvox.const import CONFIG_KEY_LOCATION, DOMAIN
from tests.conftest import MOCK_MAC


async def test_setup_entry_creates_coordinator(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_device_info: Any,
    mock_relay_status: dict[str, Any],
) -> None:
    """Test async_setup_entry creates coordinator in hass.data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_entry_data_none,
        unique_id="AA:BB:CC:DD:EE:FF",
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert DOMAIN in hass.data
    assert entry.entry_id in hass.data[DOMAIN]


async def test_setup_entry_forwards_to_lock(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_device_info: Any,
    mock_relay_status: dict[str, Any],
) -> None:
    """Test async_setup_entry forwards to lock platform."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_entry_data_none,
        unique_id="AA:BB:CC:DD:EE:FF",
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    # Verify lock entity was created (platform was forwarded)
    state = hass.states.get("lock.testlab_intercom_front_gate")
    assert state is not None


async def test_unload_entry_cleans_up(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_device_info: Any,
    mock_relay_status: dict[str, Any],
) -> None:
    """Test async_unload_entry cleans up hass.data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_entry_data_none,
        unique_id="AA:BB:CC:DD:EE:FF",
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state == ConfigEntryState.NOT_LOADED  # type: ignore[comparison-overlap]
    assert entry.entry_id not in hass.data.get(DOMAIN, {})


async def test_setup_fails_on_connection_error(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
) -> None:
    """Test setup fails gracefully on initial connection error."""
    from pylocal_akuvox import AkuvoxConnectionError

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_entry_data_none,
        unique_id="AA:BB:CC:DD:EE:FF",
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.akuvox.AkuvoxDevice",
        autospec=True,
    ) as mock_cls:
        device = mock_cls.return_value
        device.get_relay_status = AsyncMock(
            side_effect=AkuvoxConnectionError("Cannot connect"),
        )
        device.__aenter__ = AsyncMock(return_value=device)
        device.__aexit__ = AsyncMock(return_value=None)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


# ── T018: Device name from config location ──────────────────────


async def test_device_name_from_config_location(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_device_config_factory: Any,
) -> None:
    """Test HA device name matches DeviceConfig location."""
    cfg = mock_device_config_factory(
        **{CONFIG_KEY_LOCATION: "Front Door"},
    )
    mock_akuvox_device.get_device_config = AsyncMock(return_value=cfg)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_entry_data_none,
        unique_id=MOCK_MAC,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    dev_reg = dr.async_get(hass)
    mac_clean = MOCK_MAC.lower().replace(":", "")
    device = dev_reg.async_get_device(identifiers={(DOMAIN, mac_clean)})
    assert device is not None
    assert device.name == "Front Door"


async def test_device_name_fallback_when_location_empty(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_device_config_factory: Any,
) -> None:
    """Test fallback to 'Akuvox {model}' when location is empty."""
    cfg = mock_device_config_factory(
        **{CONFIG_KEY_LOCATION: ""},
    )
    mock_akuvox_device.get_device_config = AsyncMock(return_value=cfg)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_entry_data_none,
        unique_id=MOCK_MAC,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    dev_reg = dr.async_get(hass)
    mac_clean = MOCK_MAC.lower().replace(":", "")
    device = dev_reg.async_get_device(identifiers={(DOMAIN, mac_clean)})
    assert device is not None
    assert device.name == "Akuvox E21V"


# ── T038: Config fetch during integration reload ─────────────────


async def test_config_fetched_on_reload(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
) -> None:
    """Test get_device_config is called after unload and reload."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_entry_data_none,
        unique_id=MOCK_MAC,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    # Record how many times config was fetched during initial setup
    initial_config_calls = mock_akuvox_device.get_device_config.call_count

    # Unload
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.NOT_LOADED  # type: ignore[comparison-overlap]

    # Reload
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    # get_device_config should have been called again on reload
    assert mock_akuvox_device.get_device_config.call_count > initial_config_calls
