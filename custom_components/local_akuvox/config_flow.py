# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Config flow for the Akuvox integration."""

from __future__ import annotations

import logging
import secrets
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
    CONF_DEVICE_MODEL,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USE_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    CONF_WEBHOOK_ENABLED,
    CONF_WEBHOOK_ID,
    DOMAIN,
    get_auth_method_map,
)
from .webhook import build_action_urls

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
        except AkuvoxConnectionError as err:
            _LOGGER.warning(
                "Failed to connect to Akuvox device at %s "
                "(ssl=%s, auth=%s): %s",
                self._data[CONF_HOST],
                self._data.get(CONF_USE_SSL, False),
                self._data.get(CONF_AUTH_METHOD, AUTH_NONE),
                err,
            )
            errors["base"] = "cannot_connect"
        except AkuvoxAuthenticationError as err:
            _LOGGER.warning(
                "Authentication failed for Akuvox device at %s "
                "(auth=%s, user=%s): %s",
                self._data[CONF_HOST],
                self._data.get(CONF_AUTH_METHOD, AUTH_NONE),
                self._data.get(CONF_USERNAME, ""),
                err,
            )
            errors["base"] = "invalid_auth"
        except AkuvoxError as err:
            _LOGGER.warning(
                "Unexpected error connecting to Akuvox device at %s: %s",
                self._data[CONF_HOST],
                err,
                exc_info=True,
            )
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

        self._data["_device_model"] = info.model
        return await self.async_step_webhook()

    async def async_step_webhook(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> Any:
        """Handle the webhook configuration step.

        Args:
            user_input: User input from the form.

        Returns:
            Flow result for entry creation or form with errors.

        """
        errors: dict[str, str] = {}

        if user_input is not None:
            if user_input.get(CONF_WEBHOOK_ENABLED):
                webhook_id = secrets.token_hex(32)
                try:
                    await self._async_push_webhook_config(
                        webhook_id,
                        enable=True,
                    )
                except Exception:
                    errors["base"] = "webhook_push_failed"
                else:
                    self._data[CONF_WEBHOOK_ID] = webhook_id
                    self._data[CONF_WEBHOOK_ENABLED] = True
            else:
                self._data[CONF_WEBHOOK_ID] = None
                self._data[CONF_WEBHOOK_ENABLED] = False

            if not errors:
                model = self._data.pop("_device_model", "Device")
                self._data[CONF_DEVICE_MODEL] = model
                return await self.async_step_entities()

        if user_input is not None and CONF_WEBHOOK_ENABLED in user_input:
            default_enabled = bool(user_input[CONF_WEBHOOK_ENABLED])
        else:
            default_enabled = bool(self._data.get(CONF_WEBHOOK_ENABLED, False))

        return self.async_show_form(
            step_id="webhook",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_WEBHOOK_ENABLED,
                        default=default_enabled,
                    ): bool,
                }
            ),
            errors=errors or {},
        )

    async def _async_push_webhook_config(
        self,
        webhook_id: str,
        *,
        enable: bool,
    ) -> None:
        """Push webhook action URL config to the device.

        Args:
            webhook_id: The webhook ID for URL generation.
            enable: Whether to enable or disable webhooks.

        Raises:
            AkuvoxError: If the device config push fails.
            Exception: If webhook URL generation fails.

        """
        enable_payload, disable_payload = build_action_urls(
            self.hass,
            webhook_id,
            warn_http=enable,
        )
        payload = enable_payload if enable else disable_payload

        auth_method_str = self._data.get(
            CONF_AUTH_METHOD,
            AUTH_NONE,
        )
        auth_method = get_auth_method_map().get(
            auth_method_str,
            AuthMethod.NONE,
        )

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
        async with device:
            await device.set_device_config(payload)  # type: ignore[attr-defined]

    async def async_step_entities(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> Any:
        """Handle entity configuration during initial setup.

        Shows model-aware relay/input configuration fields so users
        can set custom names, lock behavior, and sensor types before
        the entry is created.

        Args:
            user_input: User input from the form.

        Returns:
            Flow result for entry creation or form.

        """
        from .const import (
            CONF_ENTITY_CONFIG,
            VALID_INPUT_DEVICE_CLASSES,
            get_model_capabilities,
        )

        model = self._data.get(CONF_DEVICE_MODEL, "")
        caps = get_model_capabilities(model) if model else None

        if user_input is not None:
            # Parse entity config from flat form fields
            new_config: dict[str, dict[str, Any]] = {}

            for letter in ["A", "B", "C", "D"]:
                relay_key = f"relay_{letter.lower()}"
                name_key = f"relay_{letter.lower()}_name"
                lock_key = f"relay_{letter.lower()}_lock"
                autolatch_key = f"relay_{letter.lower()}_autolatch"
                delay_key = f"relay_{letter.lower()}_delay"

                if name_key in user_input:
                    new_config[relay_key] = {
                        "name": user_input[name_key],
                        "create_lock": user_input.get(lock_key, True),
                        "autolatch": user_input.get(autolatch_key, True),
                        "hold_delay": user_input.get(delay_key, 5),
                    }

                input_key = f"input_{letter.lower()}"
                input_name_key = f"input_{letter.lower()}_name"
                input_class_key = f"input_{letter.lower()}_class"

                if input_name_key in user_input:
                    new_config[input_key] = {
                        "name": user_input[input_name_key],
                        "device_class": user_input.get(
                            input_class_key, "door"
                        ),
                    }

            self._data[CONF_ENTITY_CONFIG] = new_config

            return self.async_create_entry(
                title=f"Akuvox {model}",
                data=self._data,
            )

        # Determine relay/input counts from model
        relay_count = caps["relays"] if caps else 2
        input_count = caps["inputs"] if caps else 2

        relay_letters = [chr(ord("A") + i) for i in range(relay_count)]
        input_letters = [chr(ord("A") + i) for i in range(input_count)]

        schema_dict: dict[Any, Any] = {}

        for letter in relay_letters:
            schema_dict[
                vol.Optional(
                    f"relay_{letter.lower()}_name",
                    default="",
                )
            ] = str
            schema_dict[
                vol.Required(
                    f"relay_{letter.lower()}_lock",
                    default=True,
                )
            ] = bool
            schema_dict[
                vol.Required(
                    f"relay_{letter.lower()}_autolatch",
                    default=True,
                )
            ] = bool
            schema_dict[
                vol.Required(
                    f"relay_{letter.lower()}_delay",
                    default=5,
                )
            ] = vol.All(int, vol.Range(min=1, max=300))

        for letter in input_letters:
            schema_dict[
                vol.Optional(
                    f"input_{letter.lower()}_name",
                    default="",
                )
            ] = str
            schema_dict[
                vol.Required(
                    f"input_{letter.lower()}_class",
                    default="door",
                )
            ] = vol.In(VALID_INPUT_DEVICE_CLASSES)

        model_info = f" ({model})" if model else ""

        return self.async_show_form(
            step_id="entities",
            data_schema=vol.Schema(schema_dict),
            description_placeholders={"model": model_info},
        )

class AkuvoxOptionsFlow(OptionsFlow):
    """Handle options flow for Akuvox integration."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize the options flow.

        Args:
            config_entry: The config entry being configured.

        """
        self._config_entry = config_entry
        self._connection_data: dict[str, Any] = {}

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> Any:
        """Handle the init step of options flow (connection settings).

        Args:
            user_input: User input from the form.

        Returns:
            Flow result for next step or form.

        """
        if user_input is not None:
            errors: dict[str, str] = {}

            host = user_input.get(CONF_HOST, "")
            if not host or not host.strip():
                errors["base"] = "invalid_host"
            else:
                user_input[CONF_HOST] = host.strip()

            auth = user_input.get(CONF_AUTH_METHOD, AUTH_NONE)
            if auth in (AUTH_BASIC, AUTH_DIGEST):
                username = user_input.get(CONF_USERNAME, "")
                password = user_input.get(CONF_PASSWORD, "")
                if not username or not password:
                    errors.setdefault("base", "invalid_auth")

            if not errors:
                webhook_err = await self._async_handle_webhook_change(
                    user_input,
                )
                if webhook_err:
                    errors["base"] = webhook_err

            if errors:
                current = {
                    **self._config_entry.data,
                    **self._config_entry.options,
                    **user_input,
                }
                return self.async_show_form(
                    step_id="init",
                    data_schema=self._build_connection_schema(current),
                    errors=errors,
                )

            self._connection_data = user_input
            return await self.async_step_entities()

        current = {
            **self._config_entry.data,
            **self._config_entry.options,
        }

        return self.async_show_form(
            step_id="init",
            data_schema=self._build_connection_schema(current),
        )

    async def async_step_entities(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> Any:
        """Handle the entity configuration step.

        Allows users to set custom names, lock toggle, and device
        class for each relay and input discovered from the device.

        Args:
            user_input: User input from the form.

        Returns:
            Flow result for entry creation or form.

        """
        from .const import (
            CONF_DEVICE_MODEL,
            CONF_ENTITY_CONFIG,
            VALID_INPUT_DEVICE_CLASSES,
            get_model_capabilities,
        )

        current = {
            **self._config_entry.data,
            **self._config_entry.options,
        }
        entity_config = current.get(CONF_ENTITY_CONFIG, {})

        # Determine model capabilities
        model = current.get(CONF_DEVICE_MODEL, "")
        caps = get_model_capabilities(model) if model else None

        if user_input is not None:
            # Parse entity config from flat form fields
            new_config: dict[str, dict[str, Any]] = {}

            for letter in ["A", "B", "C", "D"]:
                relay_key = f"relay_{letter.lower()}"
                name_key = f"relay_{letter.lower()}_name"
                lock_key = f"relay_{letter.lower()}_lock"
                autolatch_key = f"relay_{letter.lower()}_autolatch"
                delay_key = f"relay_{letter.lower()}_delay"

                if name_key in user_input:
                    new_config[relay_key] = {
                        "name": user_input[name_key],
                        "create_lock": user_input.get(lock_key, True),
                        "autolatch": user_input.get(autolatch_key, True),
                        "hold_delay": user_input.get(delay_key, 5),
                    }

                input_key = f"input_{letter.lower()}"
                input_name_key = f"input_{letter.lower()}_name"
                input_class_key = f"input_{letter.lower()}_class"

                if input_name_key in user_input:
                    new_config[input_key] = {
                        "name": user_input[input_name_key],
                        "device_class": user_input.get(
                            input_class_key, "door"
                        ),
                    }

            # Merge connection data + entity config
            final_data = {**self._connection_data}
            final_data[CONF_ENTITY_CONFIG] = new_config

            return self.async_create_entry(
                title="",
                data=final_data,
            )

        # Determine how many relays/inputs to show
        # Priority: model capabilities > coordinator data > fallback
        relay_count = 2  # default
        input_count = 2  # default

        if caps:
            relay_count = caps["relays"]
            input_count = caps["inputs"]
        else:
            # Try to discover from coordinator
            coordinator = self.hass.data.get(DOMAIN, {}).get(
                self._config_entry.entry_id
            )
            if coordinator and coordinator.data:
                from .const import RELAY_KEY_RE

                discovered = 0
                for key in coordinator.data.relay_status:
                    if RELAY_KEY_RE.fullmatch(key):
                        discovered += 1
                if discovered:
                    relay_count = discovered

        relay_letters = [chr(ord("A") + i) for i in range(relay_count)]
        input_letters = [chr(ord("A") + i) for i in range(input_count)]

        schema_dict: dict[Any, Any] = {}

        # Build relay fields
        for letter in relay_letters:
            relay_key = f"relay_{letter.lower()}"
            cfg = entity_config.get(relay_key, {})

            schema_dict[
                vol.Optional(
                    f"relay_{letter.lower()}_name",
                    default=cfg.get("name", ""),
                )
            ] = str
            schema_dict[
                vol.Required(
                    f"relay_{letter.lower()}_lock",
                    default=cfg.get("create_lock", True),
                )
            ] = bool
            schema_dict[
                vol.Required(
                    f"relay_{letter.lower()}_autolatch",
                    default=cfg.get("autolatch", True),
                )
            ] = bool
            schema_dict[
                vol.Required(
                    f"relay_{letter.lower()}_delay",
                    default=cfg.get("hold_delay", 5),
                )
            ] = vol.All(int, vol.Range(min=1, max=300))

        # Build input fields (only for inputs this model has)
        for letter in input_letters:
            input_key = f"input_{letter.lower()}"
            cfg = entity_config.get(input_key, {})

            schema_dict[
                vol.Optional(
                    f"input_{letter.lower()}_name",
                    default=cfg.get("name", ""),
                )
            ] = str
            schema_dict[
                vol.Required(
                    f"input_{letter.lower()}_class",
                    default=cfg.get("device_class", "door"),
                )
            ] = vol.In(VALID_INPUT_DEVICE_CLASSES)

        # Add model info to description
        model_info = f" ({model})" if model else ""
        description_placeholders = {"model": model_info}

        return self.async_show_form(
            step_id="entities",
            data_schema=vol.Schema(schema_dict),
            description_placeholders=description_placeholders,
        )

    async def _async_handle_webhook_change(
        self,
        user_input: dict[str, Any],
    ) -> str | None:
        """Handle webhook enable/disable changes in options flow.

        Pushes action URL config to device when webhook state changes.

        Args:
            user_input: User input from the options form.

        Returns:
            Error string if push failed, None on success.

        """
        current = {
            **self._config_entry.data,
            **self._config_entry.options,
        }
        was_enabled = current.get(CONF_WEBHOOK_ENABLED, False)
        now_enabled = user_input.get(CONF_WEBHOOK_ENABLED, False)

        if was_enabled == now_enabled:
            # Preserve existing webhook fields unchanged
            if CONF_WEBHOOK_ID not in user_input:
                user_input[CONF_WEBHOOK_ID] = current.get(
                    CONF_WEBHOOK_ID,
                )
            user_input[CONF_WEBHOOK_ENABLED] = was_enabled
            return None

        # Resolve or generate webhook_id
        webhook_id = current.get(CONF_WEBHOOK_ID)
        if now_enabled and webhook_id is None:
            webhook_id = secrets.token_hex(32)

        if webhook_id is None:
            return None

        try:
            enable_payload, disable_payload = build_action_urls(
                self.hass,
                str(webhook_id),
                warn_http=now_enabled,
            )
        except Exception:
            return "webhook_push_failed"

        payload = enable_payload if now_enabled else disable_payload

        # Use merged settings for device connection
        effective = {**current, **user_input}
        auth_method_str = effective.get(
            CONF_AUTH_METHOD,
            AUTH_NONE,
        )
        auth_method = get_auth_method_map().get(
            auth_method_str,
            AuthMethod.NONE,
        )

        auth_config: AuthConfig | None = None
        if auth_method in (AuthMethod.BASIC, AuthMethod.DIGEST):
            auth_config = AuthConfig(
                method=auth_method,
                username=str(
                    effective.get(CONF_USERNAME, ""),
                ),
                password=str(
                    effective.get(CONF_PASSWORD, ""),
                ),
            )
        else:
            auth_config = AuthConfig(method=auth_method)

        device = AkuvoxDevice(
            host=str(effective.get(CONF_HOST, "")),
            auth=auth_config,
            use_ssl=bool(effective.get(CONF_USE_SSL, False)),
            verify_ssl=bool(
                effective.get(CONF_VERIFY_SSL, True),
            ),
        )

        try:
            async with device:
                await device.set_device_config(payload)  # type: ignore[attr-defined]
        except Exception:
            return "webhook_push_failed"

        user_input[CONF_WEBHOOK_ID] = str(webhook_id)
        user_input[CONF_WEBHOOK_ENABLED] = now_enabled
        return None

    @staticmethod
    def _build_connection_schema(
        current: dict[str, Any],
    ) -> vol.Schema:
        """Build the connection settings form schema.

        Args:
            current: Current configuration values.

        Returns:
            A voluptuous schema with pre-filled defaults.

        """
        return vol.Schema(
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
                vol.Required(
                    CONF_WEBHOOK_ENABLED,
                    default=current.get(CONF_WEBHOOK_ENABLED, False),
                ): bool,
            }
        )

