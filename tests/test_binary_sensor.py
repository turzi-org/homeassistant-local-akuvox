# SPDX-FileCopyrightText: 2026 Turzi
# SPDX-License-Identifier: Apache-2.0

"""Tests for the Akuvox input binary sensors."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.local_akuvox.const import (
    CONF_ENTITY_CONFIG,
    CONF_INPUT_INVERT,
    DOMAIN,
    EVENT_WEBHOOK_RECEIVED,
)
from tests.conftest import MOCK_MAC

INPUT_A = "binary_sensor.testlab_intercom_input_a"
INPUT_B = "binary_sensor.testlab_intercom_input_b"
S535_TRIGGER_A = "Config.DoorSetting.INPUT.InputTrigger"
S535_TRIGGER_B = "Config.DoorSetting.INPUT.InputBTrigger"
INVERTED_A = {"input_a": {"name": "", "device_class": "door", CONF_INPUT_INVERT: True}}


async def _setup(
    hass: HomeAssistant,
    data: dict[str, Any],
    **extra: Any,
) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**data, **extra},
        unique_id=MOCK_MAC,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _fire(hass: HomeAssistant, entry: MockConfigEntry, event: str, status: str) -> None:
    hass.bus.async_fire(
        EVENT_WEBHOOK_RECEIVED,
        {
            "config_entry_id": entry.entry_id,
            "event_type": event,
            "payload": {"event": event, "status": status},
        },
    )


async def test_level_matching_trigger_is_on(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_device_config_factory: Any,
) -> None:
    """A level equal to the trigger level reads as triggered (on)."""
    mock_akuvox_device.get_device_config.return_value = mock_device_config_factory(
        **{S535_TRIGGER_A: "0", S535_TRIGGER_B: "0"}
    )
    mock_akuvox_device._http.get.return_value = {"InputA": 0, "InputB": 1}
    await _setup(hass, mock_config_entry_data_none)

    assert hass.states.get(INPUT_A).state == STATE_ON
    assert hass.states.get(INPUT_B).state == STATE_OFF


async def test_high_trigger_with_low_level_is_off(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_device_config_factory: Any,
) -> None:
    """Input A set to trigger high and reading low is not triggered."""
    mock_akuvox_device.get_device_config.return_value = mock_device_config_factory(
        **{S535_TRIGGER_A: "1"}
    )
    mock_akuvox_device._http.get.return_value = {"InputA": 0, "InputB": 1}
    await _setup(hass, mock_config_entry_data_none)

    assert hass.states.get(INPUT_A).state == STATE_OFF


async def test_a02_trigger_key(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_device_config_factory: Any,
) -> None:
    """A02-style firmware keeps the trigger level in INPUTA.Option."""
    mock_akuvox_device.get_device_config.return_value = mock_device_config_factory(
        **{"Config.DoorSetting.INPUTA.Option": "1"}
    )
    mock_akuvox_device._http.get.return_value = {"InputA": 1, "InputB": 1}
    await _setup(hass, mock_config_entry_data_none)

    assert hass.states.get(INPUT_A).state == STATE_ON


async def test_webhook_updates_then_poll_corrects(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_device_config_factory: Any,
) -> None:
    """A missed or stale webhook is overwritten by the next poll."""
    mock_akuvox_device.get_device_config.return_value = mock_device_config_factory(
        **{S535_TRIGGER_A: "1"}
    )
    mock_akuvox_device._http.get.return_value = {"InputA": 0, "InputB": 1}
    entry = await _setup(hass, mock_config_entry_data_none)
    assert hass.states.get(INPUT_A).state == STATE_OFF

    _fire(hass, entry, "input_a_triggered", "1")
    await hass.async_block_till_done()
    assert hass.states.get(INPUT_A).state == STATE_ON

    # The device never sent the matching "closed"; the poll still reads low.
    coordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(INPUT_A).state == STATE_OFF


async def test_webhook_state_kept_when_device_reports_no_levels(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
) -> None:
    """Without polled levels the sensor falls back to webhook state."""
    mock_akuvox_device._http.get.return_value = {}
    entry = await _setup(hass, mock_config_entry_data_none)
    assert hass.states.get(INPUT_A).state == STATE_OFF

    _fire(hass, entry, "input_a_triggered", "0")
    await hass.async_block_till_done()
    assert hass.states.get(INPUT_A).state == STATE_ON

    coordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(INPUT_A).state == STATE_ON

    _fire(hass, entry, "input_a_closed", "1")
    await hass.async_block_till_done()
    assert hass.states.get(INPUT_A).state == STATE_OFF


@pytest.mark.parametrize(
    ("level", "expected"),
    [(0, STATE_OFF), (1, STATE_ON)],
)
async def test_invert_flips_polled_state(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
    mock_device_config_factory: Any,
    level: int,
    expected: str,
) -> None:
    """The invert option flips a polled input (trigger low, level 0 = on)."""
    mock_akuvox_device.get_device_config.return_value = mock_device_config_factory(
        **{S535_TRIGGER_A: "0"}
    )
    mock_akuvox_device._http.get.return_value = {"InputA": level, "InputB": 1}
    await _setup(
        hass,
        mock_config_entry_data_none,
        **{CONF_ENTITY_CONFIG: INVERTED_A},
    )

    assert hass.states.get(INPUT_A).state == expected


async def test_invert_flips_webhook_state(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
) -> None:
    """The invert option applies to webhook events too."""
    mock_akuvox_device._http.get.return_value = {}
    entry = await _setup(
        hass,
        mock_config_entry_data_none,
        **{CONF_ENTITY_CONFIG: INVERTED_A},
    )
    assert hass.states.get(INPUT_A).state == STATE_ON

    _fire(hass, entry, "input_a_triggered", "1")
    await hass.async_block_till_done()
    assert hass.states.get(INPUT_A).state == STATE_OFF
