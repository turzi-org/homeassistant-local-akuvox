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

from .const import DEFAULT_HOLD_DELAY_SECONDS, DOMAIN, RELAY_KEY_RE
from .coordinator import AkuvoxDataUpdateCoordinator
from .entity import AkuvoxEntity

_LOGGER = logging.getLogger(__name__)

ATTR_SOURCE = "source"
SOURCE_DEVICE = "device"
SOURCE_HA = "home_assistant"


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
        self._attr_name = (
            f"Hold Delay ({name})" if name else f"Hold Delay (Relay {relay_letter})"
        )

        mac_clean = coordinator.data.device_info.mac_address.lower().replace(":", "")
        self._attr_unique_id = f"{mac_clean}_hold_delay_{relay_letter.lower()}"

        # Initialize default state inside coordinator settings
        if self._relay_letter not in self.coordinator.relay_settings:
            self.coordinator.relay_settings[self._relay_letter] = {}

        # Value set in HA by a user. None means "follow the device": the
        # lock then reads HoldDelay from the device config on every unlock,
        # so a change made on the device is picked up after a refresh.
        self._override: float | None = None

    @property
    def native_value(self) -> float:
        """Return the HA override, or the device's current hold delay."""
        if self._override is not None:
            return self._override
        relay_cfg = self.coordinator.data.relay_configs.get(self._relay_letter)
        if relay_cfg:
            return float(relay_cfg.hold_delay)
        return float(DEFAULT_HOLD_DELAY_SECONDS)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose where the value comes from, and persist it across restarts."""
        return {ATTR_SOURCE: SOURCE_HA if self._override is not None else SOURCE_DEVICE}

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()

        last_number_data = await self.async_get_last_number_data()
        last_state = await self.async_get_last_state()
        restored = last_number_data.native_value if last_number_data else None
        source = last_state.attributes.get(ATTR_SOURCE) if last_state else None

        if restored is not None:
            if source == SOURCE_HA:
                self._set_override(restored)
            elif source is None and restored != self.native_value:
                # State saved before the source attribute existed: the
                # entity then copied the device value at startup, so only
                # a value that differs from the device was chosen in HA.
                self._set_override(restored)

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        self._set_override(value)
        self.async_write_ha_state()

    def _set_override(self, value: float) -> None:
        """Store a user-chosen hold delay and hand it to the lock."""
        self._override = value
        self.coordinator.relay_settings[self._relay_letter]["hold_delay"] = int(value)
