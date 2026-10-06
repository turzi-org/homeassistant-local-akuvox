# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Config flow for the Akuvox integration."""

from __future__ import annotations

import logging
import secrets
import ssl
from typing import TYPE_CHECKING, Any

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pylocal_akuvox import (
    AkuvoxAuthenticationError,
    AkuvoxConnectionError,
    AkuvoxError,
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
)
from .device import create_device
from .webhook import build_action_urls

if TYPE_CHECKING:
    from pylocal_akuvox import DeviceInfo

_LOGGER = logging.getLogger(__name__)

# Path probed over plain HTTP to learn whether the device enforces HTTPS.
_HTTPS_PROBE_PATH = "/api/system/info"
_HTTPS_PROBE_TIMEOUT = aiohttp.ClientTimeout(total=10)
_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
# Upper bound when walking an exception's cause chain.
_MAX_CAUSE_DEPTH = 10

_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USE_SSL, default=False): bool,
    }
)
_AUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_AUTH_METHOD, default=AUTH_NONE): vol.In(
            [AUTH_NONE, AUTH_BASIC, AUTH_DIGEST]
        ),
    }
)
_CREDENTIALS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


def _ssl_schema(verify_ssl: bool) -> vol.Schema:
    """Build the SSL options schema with the given verification default.

    Args:
        verify_ssl: Default for the certificate verification toggle.

    Returns:
        The voluptuous schema for the SSL step.

    """
    return vol.Schema({vol.Required(CONF_VERIFY_SSL, default=verify_ssl): bool})


async def _async_device_requires_https(hass: HomeAssistant, host: str) -> bool:
    """Return True when the device redirects plain HTTP to HTTPS.

    Akuvox firmware that enforces HTTPS answers every HTTP request with
    a permanent redirect to the same path on port 443. Following that
    redirect blindly fails on the factory self-signed certificate, so
    the flow detects the redirect up front and switches to HTTPS
    itself. Any transport failure returns False so the regular
    connection attempt can report the real problem.

    Args:
        hass: The Home Assistant instance.
        host: Device host name or IP address, optionally with a port.

    Returns:
        Whether the device answered with a redirect to an HTTPS URL.

    """
    session = async_get_clientsession(hass)
    try:
        async with session.get(
            f"http://{host}{_HTTPS_PROBE_PATH}",
            allow_redirects=False,
            timeout=_HTTPS_PROBE_TIMEOUT,
        ) as resp:
            location = resp.headers.get("Location", "")
            return (
                resp.status in _REDIRECT_STATUSES
                and location.lower().startswith("https://")
            )
    except (aiohttp.ClientError, TimeoutError):
        return False


def _is_certificate_error(err: BaseException) -> bool:
    """Return True when a connection error stems from certificate checks.

    Args:
        err: The exception raised by the library.

    Returns:
        Whether a TLS certificate verification failure is in its
        cause chain.

    """
    current: BaseException | None = err
    for _ in range(_MAX_CAUSE_DEPTH):
        if current is None:
            return False
        if isinstance(
            current,
            (ssl.SSLCertVerificationError, aiohttp.ClientConnectorCertificateError),
        ):
            return True
        current = current.__cause__ or current.__context__
    return False


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
            return self.async_show_form(step_id="user", data_schema=_USER_SCHEMA)

        host = user_input.get(CONF_HOST, "")
        if not host or not host.strip():
            return self.async_show_form(
                step_id="user",
                data_schema=_USER_SCHEMA,
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
            return self.async_show_form(step_id="ssl", data_schema=_ssl_schema(True))

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
            return self.async_show_form(step_id="auth", data_schema=_AUTH_SCHEMA)

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
                data_schema=_CREDENTIALS_SCHEMA,
            )

        self._data.update(user_input)
        return await self._async_test_connection()

    async def _async_connection_attempts(self) -> list[tuple[bool, bool]]:
        """Return the ``(use_ssl, verify_ssl)`` combinations to try, in order.

        The user's own choice is always honoured as-is. When SSL is off
        but the device turns out to enforce HTTPS, the flow tries HTTPS
        with certificate verification first and without it second:
        Akuvox devices ship a factory self-signed certificate that no
        trust store accepts, so a verified handshake only succeeds when
        the owner installed their own certificate on the device.

        Returns:
            The SSL settings to attempt, most secure first.

        """
        use_ssl = bool(self._data.get(CONF_USE_SSL, False))
        verify_ssl = bool(self._data.get(CONF_VERIFY_SSL, True))
        if use_ssl:
            return [(True, verify_ssl)]
        if await _async_device_requires_https(self.hass, self._data[CONF_HOST]):
            return [(True, True), (True, False)]
        return [(False, verify_ssl)]

    async def _async_fetch_info(
        self,
        *,
        use_ssl: bool,
        verify_ssl: bool,
    ) -> DeviceInfo:
        """Open a session with the given SSL settings and read device info.

        Args:
            use_ssl: Whether to connect over HTTPS.
            verify_ssl: Whether to verify the device certificate.

        Returns:
            The device identification data.

        """
        settings = {
            **self._data,
            CONF_USE_SSL: use_ssl,
            CONF_VERIFY_SSL: verify_ssl,
        }
        device = create_device(settings)
        async with device:
            return await device.get_info()

    def _log_connection_failure(self, err: Exception, error_key: str) -> None:
        """Log a failed connection test with the settings that were used.

        Args:
            err: The exception raised by the library.
            error_key: The form error that will be shown to the user.

        """
        _LOGGER.warning(
            "Connection test for Akuvox device at %s failed with %s "
            "(ssl=%s, verify_ssl=%s, auth=%s, user=%s): %s",
            self._data[CONF_HOST],
            error_key,
            self._data.get(CONF_USE_SSL, False),
            self._data.get(CONF_VERIFY_SSL, True),
            self._data.get(CONF_AUTH_METHOD, AUTH_NONE),
            self._data.get(CONF_USERNAME, ""),
            err,
            exc_info=error_key == "unknown",
        )

    def _connection_error_key(
        self,
        err: AkuvoxConnectionError,
        *,
        retry_allowed: bool,
    ) -> str | None:
        """Map a connection error to a form error, or ``None`` to retry.

        Args:
            err: The connection error raised by the library.
            retry_allowed: Whether a less strict attempt is still queued.

        Returns:
            The form error to show, or ``None`` when the next attempt
            should run instead.

        """
        if not _is_certificate_error(err):
            self._log_connection_failure(err, "cannot_connect")
            return "cannot_connect"
        if retry_allowed:
            _LOGGER.debug(
                "Certificate of Akuvox device at %s failed verification; "
                "retrying without verification",
                self._data[CONF_HOST],
            )
            return None
        self._log_connection_failure(err, "ssl_verify_failed")
        return "ssl_verify_failed"

    def _apply_ssl_settings(self, *, use_ssl: bool, verify_ssl: bool) -> None:
        """Store the SSL settings that worked, noting any automatic change.

        Args:
            use_ssl: Whether the successful attempt used HTTPS.
            verify_ssl: Whether it verified the device certificate.

        """
        if use_ssl and not self._data.get(CONF_USE_SSL, False):
            if verify_ssl:
                _LOGGER.info(
                    "Akuvox device at %s enforces HTTPS; the connection was "
                    "switched to SSL",
                    self._data[CONF_HOST],
                )
            else:
                _LOGGER.warning(
                    "Akuvox device at %s enforces HTTPS with a certificate "
                    "that cannot be verified; SSL certificate verification "
                    "was disabled for this device",
                    self._data[CONF_HOST],
                )
        self._data[CONF_USE_SSL] = use_ssl
        self._data[CONF_VERIFY_SSL] = verify_ssl

    async def _async_probe_device(self) -> tuple[DeviceInfo | None, str | None]:
        """Try each SSL combination in turn until one connects.

        Returns:
            ``(info, None)`` on success, or ``(None, error_key)`` naming
            the form error to show.

        """
        attempts = await self._async_connection_attempts()
        last_index = len(attempts) - 1
        for index, (use_ssl, verify_ssl) in enumerate(attempts):
            try:
                info = await self._async_fetch_info(
                    use_ssl=use_ssl,
                    verify_ssl=verify_ssl,
                )
            except AkuvoxConnectionError as err:
                error_key = self._connection_error_key(
                    err,
                    retry_allowed=index < last_index,
                )
                if error_key is None:
                    continue
                return None, error_key
            except AkuvoxAuthenticationError as err:
                self._log_connection_failure(err, "invalid_auth")
                return None, "invalid_auth"
            except AkuvoxError as err:
                self._log_connection_failure(err, "unknown")
                return None, "unknown"
            self._apply_ssl_settings(use_ssl=use_ssl, verify_ssl=verify_ssl)
            return info, None
        return None, "cannot_connect"

    def _show_connection_error(self, error_key: str) -> Any:
        """Show the step that can fix a failed connection test.

        Args:
            error_key: The form error to display.

        Returns:
            Flow result for the form to show again.

        """
        errors = {"base": error_key}
        if error_key == "ssl_verify_failed":
            return self.async_show_form(
                step_id="ssl",
                data_schema=_ssl_schema(bool(self._data.get(CONF_VERIFY_SSL, True))),
                errors=errors,
            )
        if self._data.get(CONF_AUTH_METHOD) in (AUTH_BASIC, AUTH_DIGEST):
            return self.async_show_form(
                step_id="credentials",
                data_schema=_CREDENTIALS_SCHEMA,
                errors=errors,
            )
        return self.async_show_form(
            step_id="auth",
            data_schema=_AUTH_SCHEMA,
            errors=errors,
        )

    async def _async_test_connection(self) -> Any:
        """Test connection to the Akuvox device.

        Returns:
            Flow result for the webhook step, an abort, or a form with
            errors.

        """
        info, error_key = await self._async_probe_device()
        if info is None:
            return self._show_connection_error(error_key or "cannot_connect")

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

        device = create_device(self._data)
        async with device:
            await device.set_device_config(payload)

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
            CONF_INPUT_INVERT,
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

                if name_key in user_input:
                    new_config[relay_key] = {
                        "name": user_input[name_key],
                        "create_lock": user_input.get(lock_key, True),
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
                        CONF_INPUT_INVERT: user_input.get(
                            f"input_{letter.lower()}_invert", False
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
            schema_dict[
                vol.Required(
                    f"input_{letter.lower()}_invert",
                    default=False,
                )
            ] = bool

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
            CONF_INPUT_INVERT,
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

                if name_key in user_input:
                    new_config[relay_key] = {
                        "name": user_input[name_key],
                        "create_lock": user_input.get(lock_key, True),
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
                        CONF_INPUT_INVERT: user_input.get(
                            f"input_{letter.lower()}_invert", False
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
            schema_dict[
                vol.Required(
                    f"input_{letter.lower()}_invert",
                    default=cfg.get(CONF_INPUT_INVERT, False),
                )
            ] = bool

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
        try:
            device = create_device(effective)
            async with device:
                await device.set_device_config(payload)
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

