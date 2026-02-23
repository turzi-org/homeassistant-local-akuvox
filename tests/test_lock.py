# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Tests for the Akuvox lock entity."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.akuvox.const import DOMAIN
from tests.conftest import MOCK_MAC


async def test_entity_unique_id(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
) -> None:
    """Test entity created with correct unique_id {mac}_relay_{num}."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_entry_data_none,
        unique_id=MOCK_MAC,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("lock.akuvox_e21v_relay_1")
    assert state is not None

    ent_reg = er.async_get(hass)
    entity_entry = ent_reg.async_get("lock.akuvox_e21v_relay_1")
    assert entity_entry is not None
    expected_uid = f"{MOCK_MAC.lower().replace(':', '')}_relay_1"
    assert entity_entry.unique_id == expected_uid


async def test_entity_name(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
) -> None:
    """Test entity name is 'Relay {num}'."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_entry_data_none,
        unique_id=MOCK_MAC,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("lock.akuvox_e21v_relay_1")
    assert state is not None
    assert state.attributes.get("friendly_name") == "Akuvox E21V Relay 1"


async def test_entity_device_info(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
) -> None:
    """Test entity device_info maps library DeviceInfo to HA DeviceInfo."""
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
    device = dev_reg.async_get_device(
        identifiers={(DOMAIN, mac_clean)},
    )
    assert device is not None
    assert device.manufacturer == "Akuvox"
    assert device.model == "E21V"


async def test_is_locked_true_when_relay_inactive(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
) -> None:
    """Test is_locked returns True when relay is closed/inactive."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_entry_data_none,
        unique_id=MOCK_MAC,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("lock.akuvox_e21v_relay_1")
    assert state is not None
    assert state.state == "locked"


async def test_is_locked_false_when_relay_active(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
) -> None:
    """Test is_locked returns False when relay is open/active."""
    with patch(
        "custom_components.akuvox.AkuvoxDevice",
        autospec=True,
    ) as mock_cls:
        from pylocal_akuvox import DeviceInfo

        device = mock_cls.return_value
        device.get_info = AsyncMock(
            return_value=DeviceInfo(
                model="E21V",
                mac_address=MOCK_MAC,
                firmware_version="1.0.0",
                hardware_version="2.0.0",
            ),
        )
        device.get_relay_status = AsyncMock(
            return_value={"1": {"state": "open"}},
        )
        device.trigger_relay = AsyncMock(return_value=None)
        device.__aenter__ = AsyncMock(return_value=device)
        device.__aexit__ = AsyncMock(return_value=None)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data=mock_config_entry_data_none,
            unique_id=MOCK_MAC,
        )
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("lock.akuvox_e21v_relay_1")
        assert state is not None
        assert state.state == "unlocked"


async def test_entity_unavailable_when_coordinator_fails(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
) -> None:
    """Test entity becomes unavailable when coordinator fails."""
    from pylocal_akuvox import AkuvoxConnectionError, DeviceInfo

    with patch(
        "custom_components.akuvox.AkuvoxDevice",
        autospec=True,
    ) as mock_cls:
        device = mock_cls.return_value
        device.get_info = AsyncMock(
            return_value=DeviceInfo(
                model="E21V",
                mac_address=MOCK_MAC,
                firmware_version="1.0.0",
                hardware_version="2.0.0",
            ),
        )
        device.get_relay_status = AsyncMock(
            return_value={"1": {"state": "closed"}},
        )
        device.trigger_relay = AsyncMock(return_value=None)
        device.__aenter__ = AsyncMock(return_value=device)
        device.__aexit__ = AsyncMock(return_value=None)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data=mock_config_entry_data_none,
            unique_id=MOCK_MAC,
        )
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("lock.akuvox_e21v_relay_1")
        assert state is not None
        assert state.state == "locked"

        # Now make coordinator fail
        device.get_relay_status.side_effect = AkuvoxConnectionError(
            "Connection lost",
        )

        coordinator = hass.data[DOMAIN][entry.entry_id]
        await coordinator.async_refresh()
        await hass.async_block_till_done()

        state = hass.states.get("lock.akuvox_e21v_relay_1")
        assert state is not None
        assert state.state == "unavailable"
