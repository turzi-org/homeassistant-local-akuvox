# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""DataUpdateCoordinator for the Akuvox integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
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

from .const import (
    CONFIG_KEY_LOCATION,
    CONFIG_KEY_RELAY_HOLD_DELAY,
    CONFIG_KEY_RELAY_MODE_SUFFIX,
    CONFIG_KEY_RELAY_NAME,
    CONFIG_KEY_RELAY_PREFIX,
    CONFIG_KEY_RELAY_TYPE_SUFFIX,
    DEFAULT_HOLD_DELAY_SECONDS,
    DEFAULT_RELAY_MODE,
    DEFAULT_RELAY_TYPE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class RelayConfig:
    """Per-relay configuration extracted from device config.

    Attributes:
        name: Display name from config (empty triggers fallback).
        hold_delay: Unlock duration in seconds.
        relay_type: 0=NO (normally-open), 1=NC (normally-closed).
        relay_mode: 0=Auto-close, 1=Manual.

    """

    name: str = ""
    hold_delay: int = DEFAULT_HOLD_DELAY_SECONDS
    relay_type: int = DEFAULT_RELAY_TYPE
    relay_mode: int = DEFAULT_RELAY_MODE


def _parse_config_int(
    value: str,
    *,
    default: int,
    min_val: int | None = None,
    max_val: int | None = None,
    allowed: set[int] | None = None,
    key: str = "",
) -> int:
    """Parse a string config value to an integer with validation.

    Args:
        value: The string value to parse.
        default: Default to return on parse/validation failure.
        min_val: Minimum acceptable value (inclusive).
        max_val: Maximum acceptable value (inclusive).
        allowed: Set of explicitly allowed values.
        key: Config key name for log messages.

    Returns:
        Parsed integer or default on failure.

    """
    try:
        result = int(value)
    except (ValueError, TypeError):
        if value != "":
            _LOGGER.warning(
                "Invalid integer value '%s' for config key '%s', using default %d",
                value,
                key,
                default,
            )
        return default

    if min_val is not None and result < min_val:
        _LOGGER.warning(
            "Value %d for '%s' below minimum %d, using default %d",
            result,
            key,
            min_val,
            default,
        )
        return default

    if max_val is not None and result > max_val:
        _LOGGER.warning(
            "Value %d for '%s' above maximum %d, using default %d",
            result,
            key,
            max_val,
            default,
        )
        return default

    if allowed is not None and result not in allowed:
        _LOGGER.warning(
            "Value %d for '%s' not in allowed set %s, using default %d",
            result,
            key,
            allowed,
            default,
        )
        return default

    return result


def _build_relay_config(config: Any, letter: str) -> RelayConfig:
    """Build a RelayConfig from a DeviceConfig for a given relay letter.

    Args:
        config: DeviceConfig instance with dict-like access.
        letter: Relay letter suffix (e.g., "A", "B").

    Returns:
        RelayConfig with parsed values or defaults for missing keys.

    """
    name = config.get(f"{CONFIG_KEY_RELAY_NAME}{letter}", "")
    hold_delay = _parse_config_int(
        config.get(
            f"{CONFIG_KEY_RELAY_HOLD_DELAY}{letter}",
            str(DEFAULT_HOLD_DELAY_SECONDS),
        ),
        default=DEFAULT_HOLD_DELAY_SECONDS,
        min_val=1,
        key=f"HoldDelay{letter}",
    )
    relay_type = _parse_config_int(
        config.get(
            f"{CONFIG_KEY_RELAY_PREFIX}{letter}{CONFIG_KEY_RELAY_TYPE_SUFFIX}",
            str(DEFAULT_RELAY_TYPE),
        ),
        default=DEFAULT_RELAY_TYPE,
        allowed={0, 1},
        key=f"Relay{letter}Type",
    )
    relay_mode = _parse_config_int(
        config.get(
            f"{CONFIG_KEY_RELAY_PREFIX}{letter}{CONFIG_KEY_RELAY_MODE_SUFFIX}",
            str(DEFAULT_RELAY_MODE),
        ),
        default=DEFAULT_RELAY_MODE,
        allowed={0, 1},
        key=f"Relay{letter}Mode",
    )
    return RelayConfig(
        name=name,
        hold_delay=hold_delay,
        relay_type=relay_type,
        relay_mode=relay_mode,
    )


@dataclass
class AkuvoxCoordinatorData:
    """Data class for coordinator update results."""

    device_info: DeviceInfo
    relay_status: dict[str, Any]
    device_name: str = ""
    relay_configs: dict[str, RelayConfig] = field(default_factory=dict)


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
        self._cached_device_name: str | None = None
        self._cached_relay_configs: dict[str, RelayConfig] | None = None
        self._was_unavailable: bool = False

    def _should_fetch_config(self) -> bool:
        """Determine whether device config should be fetched.

        Returns:
            True if config has never been fetched or device
            recovered from unavailable state.

        """
        if self._cached_device_name is None:
            return True
        return bool(self._was_unavailable)

    def _fetch_config_from_device_config(
        self,
        device_config: Any,
        relay_status: dict[str, Any],
    ) -> None:
        """Parse device config and update cached values.

        Args:
            device_config: DeviceConfig from the device.
            relay_status: Current relay status dict for
                discovering relay letters.

        """
        self._cached_device_name = device_config.get(
            CONFIG_KEY_LOCATION,
            "",
        )
        relay_configs: dict[str, RelayConfig] = {}
        for key in relay_status:
            if key.startswith("Relay") and len(key) == 6 and key[5].isupper():
                letter = key[5]
                relay_configs[letter] = _build_relay_config(
                    device_config,
                    letter,
                )
        self._cached_relay_configs = relay_configs

    def _apply_default_config(
        self,
        relay_status: dict[str, Any],
        model: str,
    ) -> None:
        """Apply default config values when fetch fails.

        Only overwrites cached values if none exist yet.

        Args:
            relay_status: Current relay status dict.
            model: Device model for fallback name.

        """
        if self._cached_device_name is None:
            self._cached_device_name = f"Akuvox {model}"
        if self._cached_relay_configs is None:
            relay_configs: dict[str, RelayConfig] = {}
            for key in relay_status:
                if key.startswith("Relay") and len(key) == 6 and key[5].isupper():
                    letter = key[5]
                    relay_configs[letter] = RelayConfig()
            self._cached_relay_configs = relay_configs

    async def _async_fetch_device_config(
        self,
        relay_status: dict[str, Any],
    ) -> None:
        """Fetch and parse device config if needed.

        Args:
            relay_status: Current relay status for letter discovery.

        Raises:
            ConfigEntryAuthFailed: On authentication errors.

        """
        if not self._should_fetch_config():
            return

        try:
            device_config = (
                await self.device.get_device_config()  # type: ignore[attr-defined]
            )
            self._fetch_config_from_device_config(
                device_config,
                relay_status,
            )
        except AkuvoxAuthenticationError as err:
            raise ConfigEntryAuthFailed(
                f"Authentication failed during config fetch: {err}",
            ) from err
        except (
            AkuvoxConnectionError,
            AkuvoxDeviceError,
            AkuvoxParseError,
        ):
            _LOGGER.warning(
                "Failed to fetch device config, using %s values",
                "cached" if self._cached_device_name is not None else "default",
            )
            self._apply_default_config(
                relay_status,
                self._cached_device_info.model
                if self._cached_device_info is not None
                else "Unknown",
            )
        self._was_unavailable = False

    async def _async_update_data(self) -> AkuvoxCoordinatorData:
        """Fetch data from the Akuvox device.

        Returns:
            AkuvoxCoordinatorData with device info, relay status,
            device name, and relay configs.

        Raises:
            UpdateFailed: On connection, device, or parse errors.
            ConfigEntryAuthFailed: On authentication errors.

        """
        try:
            relay_status = await self.device.get_relay_status()
        except AkuvoxAuthenticationError as err:
            self._was_unavailable = True
            raise ConfigEntryAuthFailed(
                f"Authentication failed: {err}",
            ) from err
        except AkuvoxConnectionError as err:
            self._was_unavailable = True
            raise UpdateFailed(
                f"Connection error: {err}",
            ) from err
        except AkuvoxDeviceError as err:
            self._was_unavailable = True
            raise UpdateFailed(
                f"Device error: {err}",
            ) from err
        except AkuvoxParseError as err:
            self._was_unavailable = True
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

        await self._async_fetch_device_config(relay_status)

        return AkuvoxCoordinatorData(
            device_info=self._cached_device_info,
            relay_status=relay_status,
            device_name=self._cached_device_name or "",
            relay_configs=self._cached_relay_configs or {},
        )
