# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Lock platform for the Akuvox integration."""

from __future__ import annotations

import logging
import re

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import AkuvoxDataUpdateCoordinator
from .entity import AkuvoxEntity

_LOGGER = logging.getLogger(__name__)

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

    @property
    def is_locked(self) -> bool | None:
        """Return true if the relay is closed/inactive (locked).

        Returns:
            True if locked (closed/inactive), False if unlocked
            (open/active), None if unknown.

        """
        relay_status = self.coordinator.data.relay_status
        state = relay_status.get(self._relay_key)

        if state is None:
            return None

        if isinstance(state, str):
            if state in ("closed", "inactive"):
                return True
            if state in ("open", "active"):
                return False
            _LOGGER.debug(
                "Unrecognized relay state '%s' for %s",
                state,
                self._relay_key,
            )
            return None

        if isinstance(state, dict):
            inner = state.get("state")
            if isinstance(inner, str):
                if inner in ("closed", "inactive"):
                    return True
                if inner in ("open", "active"):
                    return False
            _LOGGER.debug(
                "Unrecognized dict relay state for %s: %r",
                self._relay_key,
                state,
            )
            return None

        _LOGGER.debug(
            "Unexpected relay state type for %s: %r (type=%s)",
            self._relay_key,
            state,
            type(state).__name__,
        )
        return None
