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

from .const import CONF_INPUT_INVERT, DOMAIN, EVENT_WEBHOOK_RECEIVED
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
    from .const import CONF_ENTITY_CONFIG, get_model_capabilities

    coordinator: AkuvoxDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    mac_clean = (
        coordinator.data.device_info.mac_address.lower().replace(":", "")
    )

    effective = {**entry.data, **entry.options}
    entity_config = effective.get(CONF_ENTITY_CONFIG, {})

    # Get device capabilities
    capabilities = get_model_capabilities(coordinator.data.device_info.model)
    num_inputs = capabilities.get("inputs", 2)
    has_tamper = capabilities.get("tamper", False)

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

    # Create input sensors for all supported inputs
    for i in range(num_inputs):
        letter = chr(ord("A") + i)
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
                invert=bool(input_opts.get(CONF_INPUT_INVERT, False)),
            )
        )

    # Add tamper alarm sensor if supported
    if has_tamper:
        entities.append(
            AkuvoxTamperSensor(
                coordinator=coordinator,
                mac_clean=mac_clean,
            )
        )

    # Add break-in alarm sensors for all supported inputs
    for i in range(num_inputs):
        letter = chr(ord("A") + i)
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
            status = (data.get("payload") or {}).get("status")
            for entity in entities:
                if (
                    isinstance(entity, AkuvoxInputSensor)
                    and entity.input_letter == letter
                ):
                    entity.update_state(state, status=status)

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


def _parse_level(status: Any) -> int | None:
    """Parse an input level reported by the device.

    Args:
        status: Raw value, such as the webhook's ``status`` parameter.

    Returns:
        0 (low), 1 (high), or None when the value is not recognised.

    """
    text = str(status).strip().lower() if status is not None else ""
    if text in ("1", "high"):
        return 1
    if text in ("0", "low"):
        return 0
    return None


class AkuvoxInputSensor(AkuvoxEntity, BinarySensorEntity):
    """Represents an Akuvox dry-contact input as a binary sensor.

    The device decides when an input is "triggered": its level equals the
    trigger level configured on the device (high or low).  The sensor is
    on while the input is triggered, flipped when ``invert`` is set.  The
    coordinator reads the real level on every refresh, which is the
    source of truth; webhooks update the state in between.
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: Any,
        input_letter: str,
        mac_clean: str,
        custom_name: str = "",
        device_class_override: BinarySensorDeviceClass | None = BinarySensorDeviceClass.DOOR,
        invert: bool = False,
    ) -> None:
        """Initialize the input sensor.

        Args:
            coordinator: The data update coordinator.
            input_letter: Input letter (A, B, C, D).
            mac_clean: Normalized MAC address.
            custom_name: User-configured name (overrides default).
            device_class_override: Configurable device class.
            invert: Report the opposite of the device's triggered state.
        """
        super().__init__(coordinator)
        self._input_letter = input_letter
        self._mac_clean = mac_clean
        self._invert = invert
        self._attr_name = custom_name.strip() if custom_name.strip() else f"Input {input_letter}"
        self._attr_unique_id = f"{mac_clean}_input_{input_letter.lower()}"
        self._attr_device_class = device_class_override
        self._triggered = False
        self._sync_from_coordinator()
        self._attr_is_on = self._triggered != self._invert

    @property
    def input_letter(self) -> str:
        """Return the input letter for event matching."""
        return self._input_letter

    def _sync_from_coordinator(self) -> None:
        """Take the triggered state from the device's reported level.

        Does nothing when the device did not report this input's level or
        its trigger level, so the last webhook-derived state stands.
        """
        data = getattr(self.coordinator, "data", None)
        if data is None:
            return
        level = data.input_status.get(self._input_letter)
        trigger = data.input_triggers.get(self._input_letter)
        if level is None or trigger is None:
            return
        self._triggered = level == trigger

    @callback
    def _handle_coordinator_update(self) -> None:
        """Re-read the polled level and publish it."""
        self._sync_from_coordinator()
        self._attr_is_on = self._triggered != self._invert
        super()._handle_coordinator_update()

    @callback
    def update_state(self, is_on: bool, status: Any = None) -> None:
        """Update the binary sensor state from a webhook event.

        Args:
            is_on: True if the device reported the input as triggered,
                False if it reported it closed.
            status: The webhook's ``status`` value, used only to flag a
                report that disagrees with the device's trigger level.
        """
        self._triggered = is_on
        self._attr_is_on = is_on != self._invert
        self.async_write_ha_state()
        _LOGGER.debug(
            "Input %s %s via webhook (sensor %s)",
            self._input_letter,
            "triggered" if is_on else "closed",
            "ON" if self._attr_is_on else "OFF",
        )
        level = _parse_level(status)
        trigger = self.coordinator.data.input_triggers.get(self._input_letter)
        if level is not None and trigger is not None and (level == trigger) != is_on:
            _LOGGER.debug(
                "Input %s webhook status %s disagrees with event; "
                "the coordinator refresh that follows will correct it",
                self._input_letter,
                status,
            )


class AkuvoxTamperSensor(AkuvoxEntity, BinarySensorEntity):
    """Represents an Akuvox tamper alarm as a binary sensor."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.TAMPER

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
