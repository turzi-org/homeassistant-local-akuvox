# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Lock platform for the Akuvox integration."""

from __future__ import annotations

import logging

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import AkuvoxDataUpdateCoordinator
from .entity import AkuvoxEntity

_LOGGER = logging.getLogger(__name__)


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

    relay_status = coordinator.data.relay_status
    entities: list[AkuvoxLockEntity] = []

    for relay_key in relay_status:
        relay_number = int(relay_key)
        entities.append(
            AkuvoxLockEntity(
                coordinator=coordinator,
                relay_number=relay_number,
            ),
        )

    async_add_entities(entities)


class AkuvoxLockEntity(AkuvoxEntity, LockEntity):
    """Represents an Akuvox relay as a lock entity."""

    def __init__(
        self,
        coordinator: AkuvoxDataUpdateCoordinator,
        relay_number: int,
    ) -> None:
        """Initialize the lock entity.

        Args:
            coordinator: The data update coordinator.
            relay_number: The relay number on the device.

        """
        super().__init__(coordinator)
        self._relay_number = relay_number
        mac_clean = coordinator.data.device_info.mac_address.lower().replace(
            ":",
            "",
        )
        self._attr_unique_id = f"{mac_clean}_relay_{relay_number}"
        self._attr_has_entity_name = True
        self._attr_translation_key = None
        self._attr_name = f"Relay {relay_number}"

    @property
    def is_locked(self) -> bool | None:
        """Return true if the relay is closed/inactive (locked).

        Returns:
            True if locked, False if unlocked, None if unknown.

        """
        relay_status = self.coordinator.data.relay_status
        relay_key = str(self._relay_number)
        relay_data = relay_status.get(relay_key)

        if relay_data is None:
            return None

        state = relay_data.get("state")
        if state is None:
            return None

        if state in ("closed", "inactive"):
            return True
        if state in ("open", "active"):
            return False

        return None
