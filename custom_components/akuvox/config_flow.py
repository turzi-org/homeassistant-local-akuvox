# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Config flow for the Akuvox integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from pylocal_akuvox import (
    AkuvoxAuthenticationError,
    AkuvoxConnectionError,
    AkuvoxDevice,
    AkuvoxError,
    AuthConfig,
    AuthMethod,
)

from .const import (
    AUTH_BASIC,
    AUTH_DIGEST,
    AUTH_NONE,
    CONF_AUTH_METHOD,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USE_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    DOMAIN,
    get_auth_method_map,
)

_LOGGER = logging.getLogger(__name__)


class AkuvoxConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Akuvox."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> AkuvoxOptionsFlow:
        """Get the options flow handler.

        Args:
            config_entry: The config entry to configure.

        Returns:
            The options flow handler.

        """
        return AkuvoxOptionsFlow(config_entry)

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._data: dict[str, Any] = {}

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> Any:
        """Handle the user step for host configuration.

        Args:
            user_input: User input from the form.

        Returns:
            Flow result for next step or form with errors.

        """
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_HOST): str,
                        vol.Required(CONF_USE_SSL, default=False): bool,
                    }
                ),
            )

        host = user_input.get(CONF_HOST, "")
        if not host or not host.strip():
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_HOST): str,
                        vol.Required(CONF_USE_SSL, default=False): bool,
                    }
                ),
                errors={"base": "invalid_host"},
            )

        user_input[CONF_HOST] = host.strip()
        self._data.update(user_input)

        if user_input.get(CONF_USE_SSL):
            return await self.async_step_ssl()

        self._data[CONF_VERIFY_SSL] = True
        return await self.async_step_auth()

    async def async_step_ssl(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> Any:
        """Handle the SSL options step.

        Args:
            user_input: User input from the form.

        Returns:
            Flow result for next step or form.

        """
        if user_input is None:
            return self.async_show_form(
                step_id="ssl",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_VERIFY_SSL, default=True): bool,
                    }
                ),
            )

        self._data.update(user_input)
        return await self.async_step_auth()

    async def async_step_auth(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> Any:
        """Handle the authentication method selection step.

        Args:
            user_input: User input from the form.

        Returns:
            Flow result for next step or form.

        """
        if user_input is None:
            return self.async_show_form(
                step_id="auth",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_AUTH_METHOD, default=AUTH_NONE): vol.In(
                            [AUTH_NONE, AUTH_BASIC, AUTH_DIGEST]
                        ),
                    }
                ),
            )

        self._data.update(user_input)

        if user_input[CONF_AUTH_METHOD] in (AUTH_BASIC, AUTH_DIGEST):
            return await self.async_step_credentials()

        self._data[CONF_USERNAME] = ""
        self._data[CONF_PASSWORD] = ""
        return await self._async_test_connection()

    async def async_step_credentials(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> Any:
        """Handle the credentials input step.

        Args:
            user_input: User input from the form.

        Returns:
            Flow result for entry creation or form with errors.

        """
        if user_input is None:
            return self.async_show_form(
                step_id="credentials",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_USERNAME): str,
                        vol.Required(CONF_PASSWORD): str,
                    }
                ),
            )

        self._data.update(user_input)
        return await self._async_test_connection()

    async def _async_test_connection(self) -> Any:
        """Test connection to the Akuvox device.

        Returns:
            Flow result for entry creation, abort, or form with errors.

        """
        errors: dict[str, str] = {}

        auth_method_str = self._data.get(CONF_AUTH_METHOD, AUTH_NONE)
        auth_method = get_auth_method_map().get(auth_method_str, AuthMethod.NONE)

        auth_config: AuthConfig | None = None
        if auth_method in (AuthMethod.BASIC, AuthMethod.DIGEST):
            auth_config = AuthConfig(
                method=auth_method,
                username=self._data.get(CONF_USERNAME, ""),
                password=self._data.get(CONF_PASSWORD, ""),
            )
        else:
            auth_config = AuthConfig(method=auth_method)

        device = AkuvoxDevice(
            host=self._data[CONF_HOST],
            auth=auth_config,
            use_ssl=self._data.get(CONF_USE_SSL, False),
            verify_ssl=self._data.get(CONF_VERIFY_SSL, True),
        )

        try:
            async with device:
                info = await device.get_info()
        except AkuvoxConnectionError:
            _LOGGER.debug("Connection failed to %s", self._data[CONF_HOST])
            errors["base"] = "cannot_connect"
        except AkuvoxAuthenticationError:
            _LOGGER.debug("Auth failed for %s", self._data[CONF_HOST])
            errors["base"] = "invalid_auth"
        except AkuvoxError:
            _LOGGER.debug("Unknown error for %s", self._data[CONF_HOST])
            errors["base"] = "unknown"

        if errors:
            # Go back to the appropriate step
            if self._data.get(CONF_AUTH_METHOD) in (
                AUTH_BASIC,
                AUTH_DIGEST,
            ):
                return self.async_show_form(
                    step_id="credentials",
                    data_schema=vol.Schema(
                        {
                            vol.Required(CONF_USERNAME): str,
                            vol.Required(CONF_PASSWORD): str,
                        }
                    ),
                    errors=errors,
                )
            return self.async_show_form(
                step_id="auth",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_AUTH_METHOD, default=AUTH_NONE): vol.In(
                            [AUTH_NONE, AUTH_BASIC, AUTH_DIGEST]
                        ),
                    }
                ),
                errors=errors,
            )

        mac_clean = info.mac_address.lower().replace(":", "")
        await self.async_set_unique_id(mac_clean)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=f"Akuvox {info.model}",
            data=self._data,
        )


class AkuvoxOptionsFlow(OptionsFlow):
    """Handle options flow for Akuvox integration."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize the options flow.

        Args:
            config_entry: The config entry being configured.

        """
        self._config_entry = config_entry

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> Any:
        """Handle the init step of options flow.

        Presents all connection parameters pre-filled with current
        values. On submit, saves to entry.options and triggers
        integration reload.

        Args:
            user_input: User input from the form.

        Returns:
            Flow result for entry creation or form.

        """
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data=user_input,
            )

        current = {
            **self._config_entry.data,
            **self._config_entry.options,
        }

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST,
                        default=current.get(CONF_HOST, ""),
                    ): str,
                    vol.Required(
                        CONF_USE_SSL,
                        default=current.get(CONF_USE_SSL, False),
                    ): bool,
                    vol.Required(
                        CONF_VERIFY_SSL,
                        default=current.get(CONF_VERIFY_SSL, True),
                    ): bool,
                    vol.Required(
                        CONF_AUTH_METHOD,
                        default=current.get(CONF_AUTH_METHOD, AUTH_NONE),
                    ): vol.In([AUTH_NONE, AUTH_BASIC, AUTH_DIGEST]),
                    vol.Optional(
                        CONF_USERNAME,
                        default=current.get(CONF_USERNAME, ""),
                    ): str,
                    vol.Optional(
                        CONF_PASSWORD,
                        default=current.get(CONF_PASSWORD, ""),
                    ): str,
                }
            ),
        )
