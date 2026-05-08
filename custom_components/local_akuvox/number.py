# SPDX-License-Identifier: Apache-2.0
"""Number platform for Akuvox relay hold delay configuration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.number import (
    NumberDeviceClass,
    RestoreNumber,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, RELAY_KEY_RE
from .coordinator import AkuvoxDataUpdateCoordinator
from .entity import AkuvoxEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Akuvox number entities from a config entry."""
    coordinator: AkuvoxDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[AkuvoxHoldDelayNumber] = []
    if coordinator.data and coordinator.data.relay_status:
        for key in sorted(coordinator.data.relay_status):
            match = RELAY_KEY_RE.fullmatch(key)
            if match:
                letter = match.group(1)
                entities.append(
                    AkuvoxHoldDelayNumber(
                        coordinator=coordinator,
                        relay_letter=letter,
                    )
                )

    async_add_entities(entities)


class AkuvoxHoldDelayNumber(AkuvoxEntity, RestoreNumber):
    """Represents a configuration number for relay hold delay."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_device_class = NumberDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_native_min_value = 1
    _attr_native_max_value = 60
    _attr_native_step = 1

    def __init__(
        self,
        coordinator: AkuvoxDataUpdateCoordinator,
        relay_letter: str,
    ) -> None:
        """Initialize the hold delay number entity.

        Args:
            coordinator: The data update coordinator.
            relay_letter: Relay letter (A, B, C, D).
        """
        super().__init__(coordinator)
        self._relay_letter = relay_letter
        
        # Priority: Relay name if fetched from device, else Relay letter
        relay_cfg = coordinator.data.relay_configs.get(relay_letter)
        name = relay_cfg.name.strip() if relay_cfg and relay_cfg.name else ""
        self._attr_name = f"Hold Delay ({name})" if name else f"Hold Delay (Relay {relay_letter})"
        
        mac_clean = (
            coordinator.data.device_info.mac_address.lower().replace(":", "")
        )
        self._attr_unique_id = f"{mac_clean}_hold_delay_{relay_letter.lower()}"
        
        # Initialize default state inside coordinator settings
        if self._relay_letter not in self.coordinator.relay_settings:
            self.coordinator.relay_settings[self._relay_letter] = {}
        
        # Start with None until restored or defaults applied
        self._attr_native_value = None

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        
        # Restore previous state
        last_number_data = await self.async_get_last_number_data()
        
        if last_number_data and last_number_data.native_value is not None:
            self._attr_native_value = last_number_data.native_value
        else:
            # Fallback to device config if never configured in HA
            relay_cfg = self.coordinator.data.relay_configs.get(self._relay_letter)
            if relay_cfg:
                self._attr_native_value = relay_cfg.hold_delay
            else:
                self._attr_native_value = 5.0
                
        # Push to coordinator
        self.coordinator.relay_settings[self._relay_letter]["hold_delay"] = int(self._attr_native_value)

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        self._attr_native_value = value
        self.coordinator.relay_settings[self._relay_letter]["hold_delay"] = int(value)
        self.async_write_ha_state()
