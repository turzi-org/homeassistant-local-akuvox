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

# Map webhook event types to input entities (letter, is_on)
_INPUT_EVENT_MAP: dict[str, tuple[str, bool]] = {
    "input_a_triggered": ("A", True),
    "input_a_closed": ("A", False),
    "input_b_triggered": ("B", True),
    "input_b_closed": ("B", False),
    "input_c_triggered": ("C", True),
    "input_c_closed": ("C", False),
    "input_d_triggered": ("D", True),
    "input_d_closed": ("D", False),
}

# Map break-in alarm events to input letters
_BREAKIN_EVENT_MAP: dict[str, tuple[str, bool]] = {
    "break_in_alarm_a": ("A", True),
    "break_in_alarm_b": ("B", True),
    "break_in_alarm_c": ("C", True),
    "break_in_alarm_d": ("D", True),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Akuvox binary sensor entities from a config entry."""
    from .coordinator import AkuvoxDataUpdateCoordinator
    from .const import CONF_ENTITY_CONFIG

    coordinator: AkuvoxDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    mac_clean = (
        coordinator.data.device_info.mac_address.lower().replace(":", "")
    )

    effective = {**entry.data, **entry.options}
    entity_config = effective.get(CONF_ENTITY_CONFIG, {})

    # Map string device class to enum
    _DEVICE_CLASS_MAP: dict[str, BinarySensorDeviceClass | None] = {
        "door": BinarySensorDeviceClass.DOOR,
        "garage_door": BinarySensorDeviceClass.GARAGE_DOOR,
        "gate": BinarySensorDeviceClass.DOOR,  # No gate class, use door
        "window": BinarySensorDeviceClass.WINDOW,
        "motion": BinarySensorDeviceClass.MOTION,
        "opening": BinarySensorDeviceClass.OPENING,
        "tamper": BinarySensorDeviceClass.TAMPER,
        "safety": BinarySensorDeviceClass.SAFETY,
        "none": None,
    }

    entities: list[BinarySensorEntity] = []

    # Create input sensors for all 4 possible inputs (A-D)
    for letter in ["A", "B", "C", "D"]:
        input_key = f"input_{letter.lower()}"
        input_opts = entity_config.get(input_key, {})
        custom_name = input_opts.get("name", "")
        device_class_str = input_opts.get("device_class", "door")
        device_class = _DEVICE_CLASS_MAP.get(
            device_class_str, BinarySensorDeviceClass.DOOR
        )
        entities.append(
            AkuvoxInputSensor(
                coordinator=coordinator,
                input_letter=letter,
                mac_clean=mac_clean,
                custom_name=custom_name,
                device_class_override=device_class,
            )
        )

    # Add tamper alarm sensor
    entities.append(
        AkuvoxTamperSensor(
            coordinator=coordinator,
            mac_clean=mac_clean,
        )
    )

    # Add break-in alarm sensors for all 4 possible inputs (A-D)
    for letter in ["A", "B", "C", "D"]:
        entities.append(
            AkuvoxBreakInSensor(
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

        # Update input sensors
        if event_type in _INPUT_EVENT_MAP:
            letter, state = _INPUT_EVENT_MAP[event_type]
            for entity in entities:
                if (
                    isinstance(entity, AkuvoxInputSensor)
                    and entity.input_letter == letter
                ):
                    entity.update_state(state)

        # Update tamper sensor
        if event_type == "tamper_alarm_triggered":
            for entity in entities:
                if isinstance(entity, AkuvoxTamperSensor):
                    entity.update_state(True)

        # Update break-in sensors
        if event_type in _BREAKIN_EVENT_MAP:
            letter, state = _BREAKIN_EVENT_MAP[event_type]
            for entity in entities:
                if (
                    isinstance(entity, AkuvoxBreakInSensor)
                    and entity.input_letter == letter
                ):
                    entity.update_state(state)

    entry.async_on_unload(
        hass.bus.async_listen(EVENT_WEBHOOK_RECEIVED, _handle_webhook_event)
    )


class AkuvoxInputSensor(AkuvoxEntity, BinarySensorEntity):
    """Represents an Akuvox dry-contact input as a binary sensor."""

    _attr_has_entity_name = True
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: Any,
        input_letter: str,
        mac_clean: str,
        custom_name: str = "",
        device_class_override: BinarySensorDeviceClass | None = BinarySensorDeviceClass.DOOR,
    ) -> None:
        """Initialize the input sensor.

        Args:
            coordinator: The data update coordinator.
            input_letter: Input letter (A, B, C, D).
            mac_clean: Normalized MAC address.
            custom_name: User-configured name (overrides default).
            device_class_override: Configurable device class.
        """
        super().__init__(coordinator)
        self._input_letter = input_letter
        self._mac_clean = mac_clean
        self._attr_name = custom_name.strip() if custom_name.strip() else f"Input {input_letter}"
        self._attr_unique_id = f"{mac_clean}_input_{input_letter.lower()}"
        self._attr_device_class = device_class_override
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


class AkuvoxTamperSensor(AkuvoxEntity, BinarySensorEntity):
    """Represents an Akuvox tamper alarm as a binary sensor."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.TAMPER
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: Any,
        mac_clean: str,
    ) -> None:
        """Initialize the tamper sensor.

        Args:
            coordinator: The data update coordinator.
            mac_clean: Normalized MAC address.
        """
        super().__init__(coordinator)
        self._mac_clean = mac_clean
        self._attr_name = "Tamper Alarm"
        self._attr_unique_id = f"{mac_clean}_tamper"
        self._attr_is_on = False

    @callback
    def update_state(self, is_on: bool) -> None:
        """Update the tamper sensor state from a webhook event.

        Args:
            is_on: True if tamper detected.
        """
        self._attr_is_on = is_on
        self.async_write_ha_state()
        _LOGGER.debug(
            "Tamper alarm state updated to %s via webhook",
            "ON" if is_on else "OFF",
        )


class AkuvoxBreakInSensor(AkuvoxEntity, BinarySensorEntity):
    """Represents an Akuvox break-in alarm as a binary sensor."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.TAMPER
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: Any,
        input_letter: str,
        mac_clean: str,
    ) -> None:
        """Initialize the break-in alarm sensor.

        Args:
            coordinator: The data update coordinator.
            input_letter: Input letter (A, B, C, D).
            mac_clean: Normalized MAC address.
        """
        super().__init__(coordinator)
        self._input_letter = input_letter
        self._mac_clean = mac_clean
        self._attr_name = f"Break-in Alarm {input_letter}"
        self._attr_unique_id = f"{mac_clean}_breakin_{input_letter.lower()}"
        self._attr_is_on = False

    @property
    def input_letter(self) -> str:
        """Return the input letter for event matching."""
        return self._input_letter

    @callback
    def update_state(self, is_on: bool) -> None:
        """Update the break-in sensor state from a webhook event.

        Args:
            is_on: True if break-in detected.
        """
        self._attr_is_on = is_on
        self.async_write_ha_state()
        _LOGGER.debug(
            "Break-in alarm %s state updated to %s via webhook",
            self._input_letter,
            "ON" if is_on else "OFF",
        )
