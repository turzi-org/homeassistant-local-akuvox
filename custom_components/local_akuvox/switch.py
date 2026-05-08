# SPDX-License-Identifier: Apache-2.0
"""Switch platform for Akuvox relays."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, RELAY_KEY_RE
from .coordinator import AkuvoxDataUpdateCoordinator, RelayConfig
from .entity import AkuvoxEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Akuvox switch entities from a config entry."""
    coordinator: AkuvoxDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    from .const import CONF_ENTITY_CONFIG

    effective = {**entry.data, **entry.options}
    entity_config = effective.get(CONF_ENTITY_CONFIG, {})

    entities: list[AkuvoxRelaySwitch] = []
    if coordinator.data and coordinator.data.relay_status:
        for key in sorted(coordinator.data.relay_status):
            match = RELAY_KEY_RE.fullmatch(key)
            if match:
                letter = match.group(1)
                relay_config = coordinator.data.relay_configs.get(
                    letter, RelayConfig()
                )
                relay_opts = entity_config.get(f"relay_{letter.lower()}", {})
                entities.append(
                    AkuvoxRelaySwitch(
                        coordinator=coordinator,
                        relay_letter=letter,
                        relay_config=relay_config,
                        custom_name=relay_opts.get("name", ""),
                    )
                )

    async_add_entities(entities)


class AkuvoxRelaySwitch(AkuvoxEntity, SwitchEntity):
    """Represents an Akuvox relay as a switch entity.

    Unlike the lock entity, the switch provides simple on/off control
    using manual mode (mode=1), suitable for relays controlling gates,
    lights, or other non-lock devices.
    """

    _attr_has_entity_name = True
    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(
        self,
        coordinator: AkuvoxDataUpdateCoordinator,
        relay_letter: str,
        relay_config: RelayConfig,
        custom_name: str = "",
    ) -> None:
        """Initialize the relay switch.

        Args:
            coordinator: The data update coordinator.
            relay_letter: Relay letter (A, B, C, D).
            relay_config: Configuration for this relay.
            custom_name: User-configured custom name (overrides device).
        """
        super().__init__(coordinator)
        self._relay_letter = relay_letter
        self._relay_key = f"Relay{relay_letter}"
        self._relay_config = relay_config

        # Priority: user config name > device config name > default label
        if custom_name.strip():
            self._attr_name = f"{custom_name.strip()} Switch"
        else:
            name = relay_config.name.strip() if relay_config.name else ""
            self._attr_name = f"{name} Switch" if name else f"Relay {relay_letter} Switch"

        mac_clean = (
            coordinator.data.device_info.mac_address.lower().replace(":", "")
        )
        self._attr_unique_id = f"{mac_clean}_switch_{relay_letter.lower()}"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.data and self.coordinator.data.relay_status:
            status = self.coordinator.data.relay_status.get(self._relay_key)
            if status is not None:
                # Status is typically a dict with 'status' key or an int
                if isinstance(status, dict):
                    self._attr_is_on = status.get("status", 0) == 1
                else:
                    self._attr_is_on = int(status) == 1
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the relay on (manual mode, stays on)."""
        relay_num = ord(self._relay_letter) - ord("A") + 1
        await self.coordinator.device.trigger_relay(
            num=relay_num,
            mode=1,  # Manual mode — stays on
            level=self._relay_config.relay_type,
            delay=self._relay_config.hold_delay,
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the relay off (manual mode, toggle back)."""
        relay_num = ord(self._relay_letter) - ord("A") + 1
        await self.coordinator.device.trigger_relay(
            num=relay_num,
            mode=1,  # Manual mode — toggle
            level=self._relay_config.relay_type,
            delay=self._relay_config.hold_delay,
        )
        await self.coordinator.async_request_refresh()
