# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Lock platform for the Akuvox integration."""

from __future__ import annotations

import logging
import re
from typing import Any

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later
from pylocal_akuvox import AkuvoxError

from .const import DOMAIN
from .coordinator import AkuvoxDataUpdateCoordinator
from .entity import AkuvoxEntity

_LOGGER = logging.getLogger(__name__)

# Default relay unlock delay in seconds. Akuvox intercoms default
# to a 5-second auto-relock delay on a fresh configuration.
_RELAY_UNLOCK_DELAY_SECONDS = 5

# Akuvox devices expose relays as "RelayA", "RelayB", etc.
# with a single uppercase letter A-Z suffix.
_RELAY_NUM_RE = re.compile(r"Relay([A-Z])")


def _relay_key_to_number(relay_key: str) -> int | None:
    """Convert a relay key like 'RelayA' to a relay number (1-based).

    Args:
        relay_key: The relay key from the device (e.g., "RelayA").

    Returns:
        The 1-based relay number, or None if format is unrecognized.

    """
    match = _RELAY_NUM_RE.fullmatch(relay_key)
    if match:
        return ord(match.group(1)) - ord("A") + 1
    _LOGGER.warning(
        "Unexpected relay key format '%s'; skipping",
        relay_key,
    )
    return None


def _relay_key_to_label(relay_key: str) -> str:
    """Convert a relay key like 'RelayA' to a display label.

    Args:
        relay_key: The relay key from the device.

    Returns:
        A human-readable label (e.g., "Relay A").

    """
    match = _RELAY_NUM_RE.fullmatch(relay_key)
    if match:
        return f"Relay {match.group(1)}"
    _LOGGER.warning(
        "Unexpected relay key format '%s'; using raw key as label",
        relay_key,
    )
    return relay_key


def _parse_relay_state(
    relay_key: str,
    state: object,
) -> bool | None:
    """Parse a relay state value into a locked boolean.

    Args:
        relay_key: The relay key for logging context.
        state: The raw state value from the device.

    Returns:
        True if locked, False if unlocked, None if unknown.

    """
    if isinstance(state, int):
        return _parse_int_state(relay_key, state)

    if isinstance(state, str):
        return _parse_str_state(relay_key, state)

    if isinstance(state, dict):
        inner = state.get("state")
        if isinstance(inner, int):
            return _parse_int_state(relay_key, inner)
        if isinstance(inner, str):
            return _parse_str_state(relay_key, inner)
        _LOGGER.debug(
            "Unrecognized dict relay state for %s: %r",
            relay_key,
            state,
        )
        return None

    _LOGGER.debug(
        "Unexpected relay state type for %s: %r (type=%s)",
        relay_key,
        state,
        type(state).__name__,
    )
    return None


def _parse_int_state(relay_key: str, state: int) -> bool | None:
    """Parse an integer relay state value.

    Args:
        relay_key: The relay key for logging context.
        state: The integer state value (0=locked, 1=unlocked).

    Returns:
        True if locked, False if unlocked, None if unknown.

    """
    if state == 0:
        return True
    if state == 1:
        return False
    _LOGGER.debug(
        "Unexpected integer relay state %d for %s",
        state,
        relay_key,
    )
    return None


def _parse_str_state(relay_key: str, state: str) -> bool | None:
    """Parse a string relay state value.

    Args:
        relay_key: The relay key for logging context.
        state: The string state value.

    Returns:
        True if locked, False if unlocked, None if unknown.

    """
    if state in ("closed", "inactive"):
        return True
    if state in ("open", "active"):
        return False
    _LOGGER.debug(
        "Unrecognized relay state '%s' for %s",
        state,
        relay_key,
    )
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Akuvox lock entities from a config entry.

    Args:
        hass: The Home Assistant instance.
        entry: The config entry.
        async_add_entities: Callback to add entities.

    """
    coordinator: AkuvoxDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    if coordinator.data is None:
        _LOGGER.warning("No data available for %s", entry.title)
        return

    relay_status = coordinator.data.relay_status
    entities: list[AkuvoxLockEntity] = []

    for relay_key in relay_status:
        if _relay_key_to_number(relay_key) is None:
            continue
        entities.append(
            AkuvoxLockEntity(
                coordinator=coordinator,
                relay_key=relay_key,
            ),
        )

    async_add_entities(entities)


class AkuvoxLockEntity(AkuvoxEntity, LockEntity):
    """Represents an Akuvox relay as a lock entity."""

    def __init__(
        self,
        coordinator: AkuvoxDataUpdateCoordinator,
        relay_key: str,
    ) -> None:
        """Initialize the lock entity.

        Args:
            coordinator: The data update coordinator.
            relay_key: The relay key from the device (e.g., "RelayA").

        """
        super().__init__(coordinator)
        self._relay_key = relay_key
        relay_number = _relay_key_to_number(relay_key)
        if relay_number is None:
            msg = f"Invalid relay key: {relay_key}"
            raise ValueError(msg)
        self._relay_number = relay_number
        mac_clean = coordinator.data.device_info.mac_address.lower().replace(
            ":",
            "",
        )
        self._attr_unique_id = f"{mac_clean}_relay_{self._relay_number}"
        self._attr_has_entity_name = True
        self._attr_name = _relay_key_to_label(relay_key)
        self._optimistic_locked: bool | None = None
        self._delayed_refresh_cancel: CALLBACK_TYPE | None = None

    @property
    def is_locked(self) -> bool | None:
        """Return true if the relay is closed/inactive/0 (locked).

        Returns:
            True if locked (closed/inactive/0), False if unlocked
            (open/active/1), None if unknown.

        """
        if self._optimistic_locked is not None:
            return self._optimistic_locked

        relay_status = self.coordinator.data.relay_status
        state = relay_status.get(self._relay_key)

        if state is None:
            return None

        return _parse_relay_state(self._relay_key, state)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle coordinator data updates.

        Optimistic state is preserved during the unlock-delay window
        Optimistic state is preserved during the unlock-delay window
        by the is_locked property, which returns the optimistic value
        when set. Coordinator updates are still processed so that
        availability and other attributes remain accurate.
        """
        super()._handle_coordinator_update()

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the door (not supported — auto-locks via hardware).

        Raises:
            HomeAssistantError: Always, as locking is not supported.

        """
        raise HomeAssistantError(
            "Lock operation not supported; door auto-locks via hardware."
        )

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the door by triggering the relay.

        Raises:
            HomeAssistantError: If the device communication fails.

        """
        try:
            await self.coordinator.device.trigger_relay(
                num=self._relay_number,
                delay=_RELAY_UNLOCK_DELAY_SECONDS,
            )
        except AkuvoxError as err:
            raise HomeAssistantError(
                f"Failed to unlock relay {self._relay_number}: {err}"
            ) from err
        self._optimistic_locked = False
        self.async_write_ha_state()
        self._schedule_delayed_refresh()

    def _schedule_delayed_refresh(self) -> None:
        """Schedule a coordinator refresh after the unlock delay expires.

        If called while a previous timer is pending (e.g. rapid unlock
        calls), the earlier timer is cancelled and only the latest
        unlock window is tracked.
        """
        if self._delayed_refresh_cancel is not None:
            self._delayed_refresh_cancel()

        @callback
        def _refresh(_now: Any) -> None:
            """Kick off async refresh after unlock window expires."""
            self._delayed_refresh_cancel = None
            self.hass.async_create_task(
                self._async_finish_optimistic_unlock(),
            )

        self._delayed_refresh_cancel = async_call_later(
            self.hass,
            _RELAY_UNLOCK_DELAY_SECONDS,
            _refresh,
        )

    async def _async_finish_optimistic_unlock(self) -> None:
        """Refresh coordinator then clear optimistic state.

        The optimistic override is kept until the refresh completes so
        that any coordinator update triggered during the refresh does
        not write stale device state to Home Assistant.  A finally
        block ensures the override is always cleared even if the
        refresh fails.
        """
        try:
            await self.coordinator.async_refresh()
        except Exception:  # noqa: BLE001
            _LOGGER.exception(
                "Error refreshing coordinator after optimistic unlock for relay %s",
                self._relay_key,
            )
        finally:
            self._optimistic_locked = None
            self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        """Cancel pending timers on entity removal."""
        if self._delayed_refresh_cancel is not None:
            self._delayed_refresh_cancel()
            self._delayed_refresh_cancel = None
        await super().async_will_remove_from_hass()
