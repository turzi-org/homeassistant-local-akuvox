# SPDX-License-Identifier: Apache-2.0
"""Event platform for Akuvox access events (card, code, face, QR)."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, EVENT_WEBHOOK_RECEIVED
from .entity import AkuvoxEntity

_LOGGER = logging.getLogger(__name__)

# Map webhook event types to our event entity event types
_WEBHOOK_TO_ACCESS_EVENT: dict[str, str] = {
    "valid_code_entered": "valid_code",
    "invalid_code_entered": "invalid_code",
}

# All supported access event types
ALL_ACCESS_EVENT_TYPES = [
    "valid_code",
    "invalid_code",
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Akuvox event entities from a config entry."""
    from .coordinator import AkuvoxDataUpdateCoordinator

    coordinator: AkuvoxDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    mac_clean = (
        coordinator.data.device_info.mac_address.lower().replace(":", "")
    )

    access_event = AkuvoxAccessEvent(
        coordinator=coordinator,
        mac_clean=mac_clean,
    )
    async_add_entities([access_event])

    # Listen for webhook events and fire access events
    async def _handle_webhook_event(event: Any) -> None:
        """Handle incoming webhook events for access events."""
        data = event.data
        if data.get("config_entry_id") != entry.entry_id:
            return

        event_type = data.get("event_type", "")
        if event_type in _WEBHOOK_TO_ACCESS_EVENT:
            access_type = _WEBHOOK_TO_ACCESS_EVENT[event_type]
            payload = data.get("payload", {})
            access_event.fire_access_event(access_type, payload)

    entry.async_on_unload(
        hass.bus.async_listen(EVENT_WEBHOOK_RECEIVED, _handle_webhook_event)
    )


class AkuvoxAccessEvent(AkuvoxEntity, EventEntity):
    """Represents access events from an Akuvox device.

    Fires events for valid/invalid code entry, card swipes, face
    recognition, and QR scans. Data includes user identity when
    resolved from the device's user cache.
    """

    _attr_has_entity_name = True
    _attr_device_class = EventDeviceClass.DOORBELL
    _attr_name = "Access Event"
    _attr_event_types = ALL_ACCESS_EVENT_TYPES

    def __init__(
        self,
        coordinator: Any,
        mac_clean: str,
    ) -> None:
        """Initialize the access event entity.

        Args:
            coordinator: The data update coordinator.
            mac_clean: Normalized MAC address.
        """
        super().__init__(coordinator)
        self._mac_clean = mac_clean
        self._attr_unique_id = f"{mac_clean}_access_event"

    @callback
    def fire_access_event(
        self, access_type: str, payload: dict[str, Any]
    ) -> None:
        """Fire an access event.

        Args:
            access_type: The type of access event (e.g., 'valid_code').
            payload: The webhook payload with user identity data.
        """
        event_data: dict[str, Any] = {}

        # Extract user identity if available
        if payload.get("username"):
            event_data["username"] = payload["username"]
        if payload.get("user_id"):
            event_data["user_id"] = payload["user_id"]
        if payload.get("device_user_id"):
            event_data["device_user_id"] = payload["device_user_id"]

        self._trigger_event(access_type, event_data)
        self.async_write_ha_state()
        _LOGGER.debug(
            "Access event fired: type=%s, data=%s", access_type, event_data
        )
