# SPDX-License-Identifier: Apache-2.0
"""Binary sensor platform for Akuvox inputs, tamper, and break-in alarms."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, EVENT_WEBHOOK_RECEIVED
from .entity import AkuvoxEntity

_LOGGER = logging.getLogger(__name__)

# Map webhook event types to input entities
_INPUT_EVENT_MAP: dict[str, tuple[str, bool]] = {
    "input_a_triggered": ("A", True),
    "input_a_closed": ("A", False),
    "input_b_triggered": ("B", True),
    "input_b_closed": ("B", False),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Akuvox binary sensor entities from a config entry."""
    from .coordinator import AkuvoxDataUpdateCoordinator

    coordinator: AkuvoxDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    mac_clean = (
        coordinator.data.device_info.mac_address.lower().replace(":", "")
    )

    entities: list[BinarySensorEntity] = []

    # Create input sensors for Input A and Input B (based on webhook events)
    for letter in ["A", "B"]:
        entities.append(
            AkuvoxInputSensor(
                coordinator=coordinator,
                input_letter=letter,
                mac_clean=mac_clean,
            )
        )

    async_add_entities(entities)

    # Set up event listener for webhook events to update binary sensor state
    async def _handle_webhook_event(event: Any) -> None:
        """Handle incoming webhook events to update binary sensors."""
        data = event.data
        if data.get("config_entry_id") != entry.entry_id:
            return

        event_type = data.get("event_type", "")
        if event_type in _INPUT_EVENT_MAP:
            letter, state = _INPUT_EVENT_MAP[event_type]
            for entity in entities:
                if (
                    isinstance(entity, AkuvoxInputSensor)
                    and entity.input_letter == letter
                ):
                    entity.update_state(state)

    entry.async_on_unload(
        hass.bus.async_listen(EVENT_WEBHOOK_RECEIVED, _handle_webhook_event)
    )


class AkuvoxInputSensor(AkuvoxEntity, BinarySensorEntity):
    """Represents an Akuvox dry-contact input as a binary sensor."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.DOOR

    def __init__(
        self,
        coordinator: Any,
        input_letter: str,
        mac_clean: str,
    ) -> None:
        """Initialize the input sensor.

        Args:
            coordinator: The data update coordinator.
            input_letter: Input letter (A, B).
            mac_clean: Normalized MAC address.
        """
        super().__init__(coordinator)
        self._input_letter = input_letter
        self._mac_clean = mac_clean
        self._attr_name = f"Input {input_letter}"
        self._attr_unique_id = f"{mac_clean}_input_{input_letter.lower()}"
        self._attr_is_on = False

    @property
    def input_letter(self) -> str:
        """Return the input letter for event matching."""
        return self._input_letter

    @callback
    def update_state(self, is_on: bool) -> None:
        """Update the binary sensor state from a webhook event.

        Args:
            is_on: True if triggered, False if closed.
        """
        self._attr_is_on = is_on
        self.async_write_ha_state()
        _LOGGER.debug(
            "Input %s state updated to %s via webhook",
            self._input_letter,
            "ON" if is_on else "OFF",
        )
