# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Base entity for the Akuvox integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AkuvoxDataUpdateCoordinator


class AkuvoxEntity(CoordinatorEntity[AkuvoxDataUpdateCoordinator]):
    """Base class for Akuvox entities."""

    def __init__(
        self,
        coordinator: AkuvoxDataUpdateCoordinator,
    ) -> None:
        """Initialize the base entity.

        Args:
            coordinator: The data update coordinator.

        """
        super().__init__(coordinator)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for the Akuvox device.

        Converts the library's DeviceInfo to HA's DeviceInfo.

        Returns:
            HA DeviceInfo mapping.

        """
        lib_info = self.coordinator.data.device_info
        mac_clean = lib_info.mac_address.lower().replace(":", "")
        return DeviceInfo(
            identifiers={(DOMAIN, mac_clean)},
            name=f"Akuvox {lib_info.model}",
            manufacturer="Akuvox",
            model=lib_info.model,
            sw_version=lib_info.firmware_version,
            hw_version=lib_info.hardware_version,
        )
