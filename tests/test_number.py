# SPDX-FileCopyrightText: 2026 Turzi
# SPDX-License-Identifier: Apache-2.0

"""Tests for the Akuvox hold delay number entity."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    mock_restore_cache_with_extra_data,
)

from custom_components.local_akuvox.const import CONFIG_KEY_RELAY_HOLD_DELAY, DOMAIN
from tests.conftest import MOCK_MAC

LOCK_ENTITY = "lock.testlab_intercom_front_gate"
HOLD_DELAY_UNIQUE_ID = f"{MOCK_MAC.lower().replace(':', '')}_hold_delay_a"


def _restore(
    hass: HomeAssistant, entity_id: str, value: float, attributes: dict[str, Any]
) -> None:
    """Seed the restore cache with a previous hold delay state."""
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(entity_id, str(value), attributes),
                {
                    "native_max_value": 60,
                    "native_min_value": 1,
                    "native_step": 1,
                    "native_unit_of_measurement": "s",
                    "native_value": value,
                },
            )
        ],
    )


async def _setup(hass: HomeAssistant, data: dict[str, Any]) -> MockConfigEntry:
    """Set up the integration and return its config entry."""
    entry = MockConfigEntry(domain=DOMAIN, data=data, unique_id=MOCK_MAC)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _device_changes_hold_delay(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_akuvox_device: AsyncMock,
    mock_device_config_factory: Any,
    seconds: int,
) -> None:
    """Simulate HoldDelayA changing on the device while it was offline.

    The integration re-reads the device config when the device comes back.
    """
    from pylocal_akuvox import AkuvoxConnectionError

    coordinator = hass.data[DOMAIN][entry.entry_id]
    status = mock_akuvox_device.get_relay_status.return_value
    mock_akuvox_device.get_relay_status.side_effect = AkuvoxConnectionError("offline")
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    mock_akuvox_device.get_relay_status.side_effect = None
    mock_akuvox_device.get_relay_status.return_value = status
    mock_akuvox_device.get_device_config = AsyncMock(
        return_value=mock_device_config_factory(
            **{f"{CONFIG_KEY_RELAY_HOLD_DELAY}A": str(seconds)},
        )
    )
    await coordinator.async_refresh()
    await hass.async_block_till_done()


async def _unlock_delay(hass: HomeAssistant, mock_akuvox_device: AsyncMock) -> int:
    """Unlock the front gate and return the delay sent to the relay."""
    mock_akuvox_device.trigger_relay.reset_mock()
    await hass.services.async_call(
        "lock", "unlock", {"entity_id": LOCK_ENTITY}, blocking=True
    )
    return int(mock_akuvox_device.trigger_relay.call_args.kwargs["delay"])


async def test_follows_device_until_set_in_ha(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_device_config_factory: Any,
) -> None:
    """Without an HA value, the entity and the lock track the device."""
    entry = await _setup(hass, mock_config_entry_data_none)
    entity_id = er.async_get(hass).async_get_entity_id(
        "number", DOMAIN, HOLD_DELAY_UNIQUE_ID
    )
    assert entity_id is not None

    await _device_changes_hold_delay(
        hass, entry, mock_akuvox_device, mock_device_config_factory, 10
    )

    state = hass.states.get(entity_id)
    assert state is not None
    assert float(state.state) == 10
    assert state.attributes["source"] == "device"
    assert await _unlock_delay(hass, mock_akuvox_device) == 10


async def test_value_set_in_ha_overrides_device(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_device_config_factory: Any,
) -> None:
    """A value set in HA wins over later changes on the device."""
    entry = await _setup(hass, mock_config_entry_data_none)
    entity_id = er.async_get(hass).async_get_entity_id(
        "number", DOMAIN, HOLD_DELAY_UNIQUE_ID
    )
    assert entity_id is not None

    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": entity_id, "value": 8},
        blocking=True,
    )
    await _device_changes_hold_delay(
        hass, entry, mock_akuvox_device, mock_device_config_factory, 10
    )

    state = hass.states.get(entity_id)
    assert state is not None
    assert float(state.state) == 8
    assert state.attributes["source"] == "home_assistant"
    assert await _unlock_delay(hass, mock_akuvox_device) == 8


async def test_restored_ha_value_is_kept(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_device_config_factory: Any,
) -> None:
    """An override saved before a restart still applies after it."""
    _restore(
        hass,
        "number.testlab_intercom_hold_delay_front_gate",
        8,
        {"source": "home_assistant"},
    )
    entry = await _setup(hass, mock_config_entry_data_none)
    await _device_changes_hold_delay(
        hass, entry, mock_akuvox_device, mock_device_config_factory, 10
    )

    assert await _unlock_delay(hass, mock_akuvox_device) == 8


async def test_legacy_copy_of_device_value_is_not_an_override(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_device_config_factory: Any,
) -> None:
    """State saved by older versions held a copy of the device value.

    A restored value equal to the device's must not pin the delay: the
    device changing it later has to take effect.
    """
    _restore(hass, "number.testlab_intercom_hold_delay_front_gate", 5, {})
    entry = await _setup(hass, mock_config_entry_data_none)
    await _device_changes_hold_delay(
        hass, entry, mock_akuvox_device, mock_device_config_factory, 10
    )

    assert await _unlock_delay(hass, mock_akuvox_device) == 10
