# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""The Akuvox integration."""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, SupportsResponse
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import service
from homeassistant.helpers.typing import ConfigType
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
    SERVICE_ADD_SCHEDULE,
    SERVICE_ADD_USER,
    SERVICE_ADD_USER_SCHEDULE_RELAY,
    SERVICE_DELETE_SCHEDULE,
    SERVICE_DELETE_USER,
    SERVICE_LIST_SCHEDULES,
    SERVICE_LIST_USERS,
    SERVICE_MODIFY_SCHEDULE,
    SERVICE_MODIFY_USER,
    SERVICE_REMOVE_USER_SCHEDULE_RELAY,
    get_auth_method_map,
)
from .coordinator import AkuvoxDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register platform entity services for Akuvox.

    Args:
        hass: The Home Assistant instance.
        config: The configuration.

    Returns:
        True after all services are registered.

    """
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_LIST_SCHEDULES,
        entity_domain=Platform.LOCK,
        schema={
            vol.Optional("page"): cv.positive_int,
        },
        func=SERVICE_LIST_SCHEDULES,
        supports_response=SupportsResponse.ONLY,
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_LIST_USERS,
        entity_domain=Platform.LOCK,
        schema={
            vol.Optional("page"): cv.positive_int,
        },
        func=SERVICE_LIST_USERS,
        supports_response=SupportsResponse.ONLY,
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_ADD_SCHEDULE,
        entity_domain=Platform.LOCK,
        schema={
            vol.Required("schedule_type"): vol.In(["0", "1", "2"]),
            vol.Required("name"): cv.string,
            vol.Optional("week"): vol.All(
                cv.ensure_list,
                [
                    vol.In(
                        [
                            "sun",
                            "mon",
                            "tue",
                            "wed",
                            "thu",
                            "fri",
                            "sat",
                        ],
                    ),
                ],
            ),
            vol.Optional("date_start"): cv.date,
            vol.Optional("date_end"): cv.date,
            vol.Required("time_start"): cv.time,
            vol.Required("time_end"): cv.time,
        },
        func=SERVICE_ADD_SCHEDULE,
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_MODIFY_SCHEDULE,
        entity_domain=Platform.LOCK,
        schema={
            vol.Required("id"): cv.string,
            vol.Optional("schedule_type"): vol.In(["0", "1", "2"]),
            vol.Optional("name"): cv.string,
            vol.Optional("week"): vol.All(
                cv.ensure_list,
                [
                    vol.In(
                        [
                            "sun",
                            "mon",
                            "tue",
                            "wed",
                            "thu",
                            "fri",
                            "sat",
                        ],
                    ),
                ],
            ),
            vol.Optional("date_start"): cv.date,
            vol.Optional("date_end"): cv.date,
            vol.Optional("time_start"): cv.time,
            vol.Optional("time_end"): cv.time,
        },
        func=SERVICE_MODIFY_SCHEDULE,
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_DELETE_SCHEDULE,
        entity_domain=Platform.LOCK,
        schema={
            vol.Required("id"): cv.string,
        },
        func=SERVICE_DELETE_SCHEDULE,
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_ADD_USER,
        entity_domain=Platform.LOCK,
        schema={
            vol.Required("name"): cv.string,
            vol.Required("user_id"): cv.string,
            vol.Required("schedule_relay"): cv.string,
            vol.Required("lift_floor_num"): cv.string,
            vol.Optional("web_relay"): cv.string,
            vol.Optional("private_pin"): cv.string,
            vol.Optional("card_code"): cv.string,
        },
        func=SERVICE_ADD_USER,
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_MODIFY_USER,
        entity_domain=Platform.LOCK,
        schema={
            vol.Required("id"): cv.string,
            vol.Optional("name"): cv.string,
            vol.Optional("user_id"): cv.string,
            vol.Optional("schedule_relay"): cv.string,
            vol.Optional("lift_floor_num"): cv.string,
            vol.Optional("web_relay"): cv.string,
            vol.Optional("private_pin"): cv.string,
            vol.Optional("card_code"): cv.string,
        },
        func=SERVICE_MODIFY_USER,
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_DELETE_USER,
        entity_domain=Platform.LOCK,
        schema={
            vol.Required("id"): cv.string,
        },
        func=SERVICE_DELETE_USER,
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_ADD_USER_SCHEDULE_RELAY,
        entity_domain=Platform.LOCK,
        schema={
            vol.Required("id"): cv.string,
            vol.Required("schedule_id"): cv.string,
            vol.Required("relay_id"): cv.string,
        },
        func=SERVICE_ADD_USER_SCHEDULE_RELAY,
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_REMOVE_USER_SCHEDULE_RELAY,
        entity_domain=Platform.LOCK,
        schema={
            vol.Required("id"): cv.string,
            vol.Required("schedule_id"): cv.string,
            vol.Required("relay_id"): cv.string,
        },
        func=SERVICE_REMOVE_USER_SCHEDULE_RELAY,
    )

    return True


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

    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN, None)
        await device.__aexit__(None, None, None)
        raise

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> None:
    """Reload integration when options change.

    Args:
        hass: The Home Assistant instance.
        entry: The config entry that was updated.

    """
    await hass.config_entries.async_reload(entry.entry_id)


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
