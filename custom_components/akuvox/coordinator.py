# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""DataUpdateCoordinator for the Akuvox integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from pylocal_akuvox import (
    AkuvoxAuthenticationError,
    AkuvoxConnectionError,
    AkuvoxDevice,
    AkuvoxDeviceError,
    AkuvoxParseError,
    DeviceInfo,
)

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class AkuvoxCoordinatorData:
    """Data class for coordinator update results."""

    device_info: DeviceInfo
    relay_status: dict[str, Any]


class AkuvoxDataUpdateCoordinator(
    DataUpdateCoordinator[AkuvoxCoordinatorData],
):
    """Coordinator to manage Akuvox device data updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        device: AkuvoxDevice,
    ) -> None:
        """Initialize the coordinator.

        Args:
            hass: The Home Assistant instance.
            device: The AkuvoxDevice instance for API calls.

        """
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.device = device
        self._cached_device_info: DeviceInfo | None = None

    async def _async_update_data(self) -> AkuvoxCoordinatorData:
        """Fetch data from the Akuvox device.

        Returns:
            AkuvoxCoordinatorData with device info and relay status.

        Raises:
            UpdateFailed: On connection, device, or parse errors.
            ConfigEntryAuthFailed: On authentication errors.

        """
        try:
            relay_status = await self.device.get_relay_status()
        except AkuvoxAuthenticationError as err:
            raise ConfigEntryAuthFailed(
                f"Authentication failed: {err}",
            ) from err
        except AkuvoxConnectionError as err:
            raise UpdateFailed(
                f"Connection error: {err}",
            ) from err
        except AkuvoxDeviceError as err:
            raise UpdateFailed(
                f"Device error: {err}",
            ) from err
        except AkuvoxParseError as err:
            raise UpdateFailed(
                f"Parse error: {err}",
            ) from err

        if self._cached_device_info is None:
            try:
                self._cached_device_info = await self.device.get_info()
            except AkuvoxAuthenticationError as err:
                raise ConfigEntryAuthFailed(
                    f"Authentication failed: {err}",
                ) from err
            except (
                AkuvoxConnectionError,
                AkuvoxDeviceError,
                AkuvoxParseError,
            ) as err:
                raise UpdateFailed(
                    f"Failed to get device info: {err}",
                ) from err

        return AkuvoxCoordinatorData(
            device_info=self._cached_device_info,
            relay_status=relay_status,
        )
