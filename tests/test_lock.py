# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Tests for the Akuvox lock entity."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
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

    state = hass.states.get("lock.akuvox_e21v_relay_a")
    assert state is not None

    ent_reg = er.async_get(hass)
    entity_entry = ent_reg.async_get("lock.akuvox_e21v_relay_a")
    assert entity_entry is not None
    expected_uid = f"{MOCK_MAC.lower().replace(':', '')}_relay_1"
    assert entity_entry.unique_id == expected_uid


async def test_entity_name(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
) -> None:
    """Test entity name is 'Relay A'."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_entry_data_none,
        unique_id=MOCK_MAC,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("lock.akuvox_e21v_relay_a")
    assert state is not None
    assert state.attributes.get("friendly_name") == "Akuvox E21V Relay A"


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


@pytest.mark.parametrize(
    ("relay_state", "expected_ha_state"),
    [("closed", "locked"), ("inactive", "locked"), (0, "locked")],
)
async def test_is_locked_true(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    relay_state: str | int,
    expected_ha_state: str,
) -> None:
    """Test is_locked returns True for closed/inactive/0 states."""
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
            return_value={"RelayA": relay_state},
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

        state = hass.states.get("lock.akuvox_e21v_relay_a")
        assert state is not None
        assert state.state == expected_ha_state


@pytest.mark.parametrize(
    ("relay_state", "expected_ha_state"),
    [("open", "unlocked"), ("active", "unlocked"), (1, "unlocked")],
)
async def test_is_locked_false(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    relay_state: str | int,
    expected_ha_state: str,
) -> None:
    """Test is_locked returns False for open/active/1 states."""
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
            return_value={"RelayA": relay_state},
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

        state = hass.states.get("lock.akuvox_e21v_relay_a")
        assert state is not None
        assert state.state == expected_ha_state


@pytest.mark.parametrize("relay_state", [2, -1])
async def test_is_locked_unknown_for_unexpected_int(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    relay_state: int,
) -> None:
    """Test is_locked returns None for unexpected integer states."""
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
            return_value={"RelayA": relay_state},
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

        state = hass.states.get("lock.akuvox_e21v_relay_a")
        assert state is not None
        assert state.state == "unknown"


@pytest.mark.parametrize(
    ("relay_state", "expected_ha_state"),
    [({"state": 0}, "locked"), ({"state": 1}, "unlocked")],
)
async def test_is_locked_handles_dict_int_state(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    relay_state: dict[str, int],
    expected_ha_state: str,
) -> None:
    """Test is_locked handles dict-wrapped integer states."""
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
            return_value={"RelayA": relay_state},
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

        state = hass.states.get("lock.akuvox_e21v_relay_a")
        assert state is not None
        assert state.state == expected_ha_state


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
            return_value={"RelayA": "closed"},
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

        state = hass.states.get("lock.akuvox_e21v_relay_a")
        assert state is not None
        assert state.state == "locked"

        # Now make coordinator fail
        device.get_relay_status.side_effect = AkuvoxConnectionError(
            "Connection lost",
        )

        coordinator = hass.data[DOMAIN][entry.entry_id]
        await coordinator.async_refresh()
        await hass.async_block_till_done()

        state = hass.states.get("lock.akuvox_e21v_relay_a")
        assert state is not None
        assert state.state == "unavailable"


async def test_multi_relay_entities_created(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
) -> None:
    """Test multiple relay entities are created with correct IDs."""
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
            return_value={"RelayA": "closed", "RelayB": "open"},
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

        state_a = hass.states.get("lock.akuvox_e21v_relay_a")
        assert state_a is not None
        assert state_a.state == "locked"

        state_b = hass.states.get("lock.akuvox_e21v_relay_b")
        assert state_b is not None
        assert state_b.state == "unlocked"

        ent_reg = er.async_get(hass)
        mac_clean = MOCK_MAC.lower().replace(":", "")
        entry_a = ent_reg.async_get("lock.akuvox_e21v_relay_a")
        assert entry_a is not None
        assert entry_a.unique_id == f"{mac_clean}_relay_1"

        entry_b = ent_reg.async_get("lock.akuvox_e21v_relay_b")
        assert entry_b is not None
        assert entry_b.unique_id == f"{mac_clean}_relay_2"


async def test_is_locked_handles_dict_state_format(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
) -> None:
    """Test is_locked handles legacy dict state format defensively."""
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
            return_value={"RelayA": {"state": "closed"}},
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

        state = hass.states.get("lock.akuvox_e21v_relay_a")
        assert state is not None
        assert state.state == "locked"


async def test_unrecognized_relay_keys_skipped(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
) -> None:
    """Test that unrecognized relay keys are skipped."""
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
            return_value={
                "RelayA": "closed",
                "unknown_key": "open",
                "relay_b": "open",
            },
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

        # Only RelayA should be created
        state_a = hass.states.get("lock.akuvox_e21v_relay_a")
        assert state_a is not None

        ent_reg = er.async_get(hass)
        entities = er.async_entries_for_config_entry(
            ent_reg,
            entry.entry_id,
        )
        assert len(entities) == 1


# ──────────────────────────────────────────────────────
# User Story 2 — Control Door Lock
# ──────────────────────────────────────────────────────


async def test_async_unlock_calls_trigger_relay(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
) -> None:
    """Test async_unlock calls trigger_relay with correct params."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_entry_data_none,
        unique_id=MOCK_MAC,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "lock",
        "unlock",
        {"entity_id": "lock.akuvox_e21v_relay_a"},
        blocking=True,
    )

    mock_akuvox_device.trigger_relay.assert_called_once_with(num=1, delay=5)


async def test_async_unlock_shows_unlocked_optimistically(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
) -> None:
    """Test unlock shows unlocked even if device hasn't updated yet.

    After triggering the relay, the device may still report locked
    because it hasn't processed the command yet. The entity must
    optimistically report unlocked immediately after a successful
    trigger.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_entry_data_none,
        unique_id=MOCK_MAC,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Relay status is NOT updated — device still reports locked.
    # The entity must still show unlocked via optimistic state.

    await hass.services.async_call(
        "lock",
        "unlock",
        {"entity_id": "lock.akuvox_e21v_relay_a"},
        blocking=True,
    )

    # State must be unlocked optimistically despite device lag
    state = hass.states.get("lock.akuvox_e21v_relay_a")
    assert state is not None
    assert state.state == "unlocked"


async def test_optimistic_state_survives_coordinator_update(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
) -> None:
    """Test optimistic unlocked state survives a coordinator poll.

    If the coordinator refreshes during the unlock-delay window, the
    device may still report locked. The optimistic override must not
    be cleared until the delayed refresh fires.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_entry_data_none,
        unique_id=MOCK_MAC,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "lock",
        "unlock",
        {"entity_id": "lock.akuvox_e21v_relay_a"},
        blocking=True,
    )

    # Simulate a coordinator poll returning stale locked state
    coordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Entity must still report unlocked despite stale coordinator data
    state = hass.states.get("lock.akuvox_e21v_relay_a")
    assert state is not None
    assert state.state == "unlocked"


async def test_rapid_unlock_resets_optimistic_window(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
) -> None:
    """Test rapid successive unlocks keep optimistic state active.

    When a second unlock is issued before the first timer fires, the
    earlier timer is cancelled and a new window starts.  The entity
    must remain unlocked until the latest window expires.
    """
    import datetime

    from homeassistant.util import dt as dt_util
    from pytest_homeassistant_custom_component.common import (
        async_fire_time_changed,
    )

    from custom_components.akuvox.lock import (
        _RELAY_REFRESH_BUFFER_SECONDS,
        _RELAY_UNLOCK_DELAY_SECONDS,
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_entry_data_none,
        unique_id=MOCK_MAC,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    start = dt_util.utcnow()

    # First unlock
    await hass.services.async_call(
        "lock",
        "unlock",
        {"entity_id": "lock.akuvox_e21v_relay_a"},
        blocking=True,
    )

    # Advance part-way through the first window
    async_fire_time_changed(
        hass,
        start
        + datetime.timedelta(
            seconds=_RELAY_UNLOCK_DELAY_SECONDS - 1,
        ),
    )
    await hass.async_block_till_done()

    # Second unlock — resets the timer
    await hass.services.async_call(
        "lock",
        "unlock",
        {"entity_id": "lock.akuvox_e21v_relay_a"},
        blocking=True,
    )

    second_unlock = dt_util.utcnow()

    # Advance past the original window but before the new one expires
    async_fire_time_changed(
        hass,
        second_unlock
        + datetime.timedelta(
            seconds=_RELAY_UNLOCK_DELAY_SECONDS,
        ),
    )
    await hass.async_block_till_done()

    # Entity must still report unlocked (second timer hasn't fired)
    state = hass.states.get("lock.akuvox_e21v_relay_a")
    assert state is not None
    assert state.state == "unlocked"

    # Now advance past the second window
    mock_akuvox_device.get_relay_status.return_value = {"RelayA": 0}
    async_fire_time_changed(
        hass,
        second_unlock
        + datetime.timedelta(
            seconds=_RELAY_UNLOCK_DELAY_SECONDS + _RELAY_REFRESH_BUFFER_SECONDS + 1,
        ),
    )
    await hass.async_block_till_done()

    # Now entity should reflect real device state (locked)
    state = hass.states.get("lock.akuvox_e21v_relay_a")
    assert state is not None
    assert state.state == "locked"


async def test_delayed_refresh_clears_optimistic_state(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
) -> None:
    """Test delayed refresh fires, clears optimistic state, re-syncs.

    After the unlock-delay window expires the timer must trigger a
    coordinator refresh and clear the optimistic override so the entity
    reports real device state.
    """
    import datetime

    from homeassistant.util import dt as dt_util
    from pytest_homeassistant_custom_component.common import (
        async_fire_time_changed,
    )

    from custom_components.akuvox.lock import (
        _RELAY_REFRESH_BUFFER_SECONDS,
        _RELAY_UNLOCK_DELAY_SECONDS,
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_entry_data_none,
        unique_id=MOCK_MAC,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    start = dt_util.utcnow()

    await hass.services.async_call(
        "lock",
        "unlock",
        {"entity_id": "lock.akuvox_e21v_relay_a"},
        blocking=True,
    )

    # Device now returns locked (relay re-locked after delay)
    mock_akuvox_device.get_relay_status.return_value = {"RelayA": 0}

    # Advance time past the unlock-delay + buffer window
    async_fire_time_changed(
        hass,
        start
        + datetime.timedelta(
            seconds=_RELAY_UNLOCK_DELAY_SECONDS + _RELAY_REFRESH_BUFFER_SECONDS + 1,
        ),
    )
    await hass.async_block_till_done()

    # Entity should now reflect real device state (locked)
    state = hass.states.get("lock.akuvox_e21v_relay_a")
    assert state is not None
    assert state.state == "locked"


async def test_entity_removal_cancels_delayed_refresh(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
) -> None:
    """Test entity removal cancels pending delayed refresh timer.

    When the entity is removed from Home Assistant while a delayed
    refresh timer is pending, the timer must be cancelled to avoid
    refreshing a torn-down coordinator.
    """
    import datetime

    from homeassistant.util import dt as dt_util
    from pytest_homeassistant_custom_component.common import (
        async_fire_time_changed,
    )

    from custom_components.akuvox.lock import (
        _RELAY_REFRESH_BUFFER_SECONDS,
        _RELAY_UNLOCK_DELAY_SECONDS,
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_entry_data_none,
        unique_id=MOCK_MAC,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    start = dt_util.utcnow()

    # Trigger unlock to schedule a delayed refresh
    await hass.services.async_call(
        "lock",
        "unlock",
        {"entity_id": "lock.akuvox_e21v_relay_a"},
        blocking=True,
    )

    # Record call count before removal
    refresh_count = mock_akuvox_device.get_relay_status.call_count

    # Unload the config entry (removes entities)
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    # Advance time past the unlock-delay + buffer window
    async_fire_time_changed(
        hass,
        start
        + datetime.timedelta(
            seconds=_RELAY_UNLOCK_DELAY_SECONDS + _RELAY_REFRESH_BUFFER_SECONDS + 1,
        ),
    )
    await hass.async_block_till_done()

    # No additional refresh should have been triggered
    assert mock_akuvox_device.get_relay_status.call_count == refresh_count


@pytest.mark.parametrize(
    "exception_cls",
    [
        "AkuvoxConnectionError",
        "AkuvoxAuthenticationError",
        "AkuvoxError",
    ],
)
async def test_async_unlock_raises_on_device_error(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    exception_cls: str,
) -> None:
    """Test async_unlock raises HomeAssistantError on device errors."""
    import pylocal_akuvox
    from homeassistant.exceptions import HomeAssistantError

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
            return_value={"RelayA": "closed"},
        )
        exc = getattr(pylocal_akuvox, exception_cls)
        device.trigger_relay = AsyncMock(
            side_effect=exc("trigger failed"),
        )
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

        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                "lock",
                "unlock",
                {"entity_id": "lock.akuvox_e21v_relay_a"},
                blocking=True,
            )


async def test_async_lock_raises_error(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_akuvox_device: AsyncMock,
) -> None:
    """Test async_lock raises HomeAssistantError."""
    from homeassistant.exceptions import HomeAssistantError

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_entry_data_none,
        unique_id=MOCK_MAC,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(HomeAssistantError, match="auto-locks via hardware"):
        await hass.services.async_call(
            "lock",
            "lock",
            {"entity_id": "lock.akuvox_e21v_relay_a"},
            blocking=True,
        )
