# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Tests for Akuvox schedule and user CRUD services."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from pylocal_akuvox import (
    AkuvoxAuthenticationError,
    AkuvoxConnectionError,
    AkuvoxDeviceError,
    AkuvoxParseError,
    AkuvoxRequestError,
    AkuvoxUnsupportedError,
    AkuvoxValidationError,
)
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.akuvox.const import DOMAIN


async def _setup_entry(
    hass: HomeAssistant,
    config_data: dict[str, Any],
    mock_device: AsyncMock,
) -> MockConfigEntry:
    """Set up a loaded config entry with a lock entity for service testing.

    Args:
        hass: The Home Assistant instance.
        config_data: Config entry data dict.
        mock_device: The mocked AkuvoxDevice.

    Returns:
        The loaded MockConfigEntry.

    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=config_data,
        unique_id="AA:BB:CC:DD:EE:FF",
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


# Library-to-HA exception mapping pairs:
# (library_exception, expected_ha_exception)
LIBRARY_TO_HA_ERROR_MAP: list[tuple[type[Exception], type[Exception]]] = [
    (AkuvoxConnectionError, HomeAssistantError),
    (AkuvoxAuthenticationError, HomeAssistantError),
    (AkuvoxDeviceError, HomeAssistantError),
    (AkuvoxRequestError, HomeAssistantError),
    (AkuvoxParseError, HomeAssistantError),
    (AkuvoxUnsupportedError, HomeAssistantError),
    (AkuvoxValidationError, ServiceValidationError),
]


def assert_library_error_maps_to_ha_error(
    library_exc: type[Exception],
) -> type[Exception]:
    """Return the expected HA exception for a given library exception.

    Args:
        library_exc: The library exception class.

    Returns:
        The expected Home Assistant exception class.

    Raises:
        ValueError: If the library exception is not in the mapping.

    """
    for lib_exc, ha_exc in LIBRARY_TO_HA_ERROR_MAP:
        if lib_exc is library_exc:
            return ha_exc
    msg = f"No mapping for {library_exc.__name__}"
    raise ValueError(msg)
