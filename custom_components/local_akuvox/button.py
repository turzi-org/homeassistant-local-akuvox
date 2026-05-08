# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Button platform for Akuvox integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pylocal_akuvox import AkuvoxError

from .const import DOMAIN
from .coordinator import AkuvoxDataUpdateCoordinator
from .entity import AkuvoxEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Akuvox button platform."""
    coordinator: AkuvoxDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([AkuvoxRebootButton(coordinator)])


class AkuvoxRebootButton(AkuvoxEntity, ButtonEntity):
    """Represents a button to reboot the Akuvox device."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_name = "Reboot"

    def __init__(self, coordinator: AkuvoxDataUpdateCoordinator) -> None:
        """Initialize the reboot button."""
        super().__init__(coordinator)
        mac_clean = (
            coordinator.data.device_info.mac_address.lower().replace(":", "")
        )
        self._attr_unique_id = f"{mac_clean}_reboot"

    async def async_press(self) -> None:
        """Handle the button press."""
        try:
            await self.coordinator.device._http.post(
                "/api/system/reboot",
                data={"target": "system", "action": "reboot"},
            )
        except AkuvoxError as err:
            raise HomeAssistantError(f"Failed to reboot device: {err}") from err
