# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""The Akuvox integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from pylocal_akuvox import AkuvoxDevice, AuthConfig, AuthMethod

from .const import (
    CONF_AUTH_METHOD,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USE_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    DOMAIN,
    PLATFORMS,
    get_auth_method_map,
)
from .coordinator import AkuvoxDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


def _get_config_value(entry: ConfigEntry, key: str, default: object = None) -> object:
    """Get config value from options first, then data.

    Args:
        entry: The config entry.
        key: The configuration key.
        default: Default value if not found.

    Returns:
        The configuration value.

    """
    return entry.options.get(key, entry.data.get(key, default))


def _create_device(entry: ConfigEntry) -> AkuvoxDevice:
    """Create an AkuvoxDevice from a config entry.

    Args:
        entry: The config entry.

    Returns:
        Configured AkuvoxDevice instance.

    """
    host = str(_get_config_value(entry, CONF_HOST, ""))
    use_ssl = bool(_get_config_value(entry, CONF_USE_SSL, False))
    verify_ssl = bool(_get_config_value(entry, CONF_VERIFY_SSL, True))
    auth_method_str = str(_get_config_value(entry, CONF_AUTH_METHOD, "none"))
    auth_method = get_auth_method_map().get(auth_method_str, AuthMethod.NONE)

    auth_config: AuthConfig | None = None
    if auth_method in (AuthMethod.BASIC, AuthMethod.DIGEST):
        auth_config = AuthConfig(
            method=auth_method,
            username=str(_get_config_value(entry, CONF_USERNAME, "")),
            password=str(_get_config_value(entry, CONF_PASSWORD, "")),
        )
    else:
        auth_config = AuthConfig(method=auth_method)

    return AkuvoxDevice(
        host=host,
        auth=auth_config,
        use_ssl=use_ssl,
        verify_ssl=verify_ssl,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Set up Akuvox from a config entry.

    Args:
        hass: The Home Assistant instance.
        entry: The config entry.

    Returns:
        True if setup was successful.

    """
    device = _create_device(entry)
    await device.__aenter__()
    coordinator = AkuvoxDataUpdateCoordinator(hass=hass, device=device)

    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        await device.__aexit__(None, None, None)
        raise

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Unload an Akuvox config entry.

    Args:
        hass: The Home Assistant instance.
        entry: The config entry.

    Returns:
        True if unload was successful.

    """
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        coordinator: AkuvoxDataUpdateCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.device.__aexit__(None, None, None)
        _LOGGER.debug("Closed device session for %s", entry.title)

        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)

    return unload_ok
