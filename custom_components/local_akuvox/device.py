# SPDX-FileCopyrightText: 2026 Turzi
# SPDX-License-Identifier: Apache-2.0

"""Device construction and capability policy for the Akuvox integration."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from pylocal_akuvox import (
    AkuvoxDevice,
    AuthConfig,
    AuthMethod,
    Capability,
    CapabilityStatus,
    DeviceCapabilities,
)

from .const import (
    AUTH_NONE,
    CONF_AUTH_METHOD,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USE_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    INPUT_KEY_RE,
    INPUT_STATUS_PATH,
    get_auth_method_map,
)

_LOGGER = logging.getLogger(__name__)

# Relay-trigger transports pylocal-akuvox can dispatch to. The API
# variant (``/api/relay/trig``) is the one every door phone exposes.
_RELAY_TRIGGER_VARIANTS: tuple[Capability, ...] = (
    Capability.RELAY_TRIGGER_API,
    Capability.RELAY_TRIGGER_FCGI,
)


def build_auth_config(config: Mapping[str, Any]) -> AuthConfig:
    """Build the library authentication config from integration settings.

    Args:
        config: Any mapping carrying the ``CONF_*`` connection keys.

    Returns:
        An ``AuthConfig`` for the selected authentication method.

    """
    auth_method_str = str(config.get(CONF_AUTH_METHOD, AUTH_NONE))
    auth_method = get_auth_method_map().get(auth_method_str, AuthMethod.NONE)
    if auth_method in (AuthMethod.BASIC, AuthMethod.DIGEST):
        return AuthConfig(
            method=auth_method,
            username=str(config.get(CONF_USERNAME, "")),
            password=str(config.get(CONF_PASSWORD, "")),
        )
    return AuthConfig(method=auth_method)


def create_device(config: Mapping[str, Any]) -> AkuvoxDevice:
    """Create an ``AkuvoxDevice`` from integration connection settings.

    pylocal-akuvox ships a capability matrix that covers a handful of
    models and refuses every gated call (relay status, configuration
    reads and writes, user management) for any other model before a
    request is sent. Door phones such as the S535 are not in that
    matrix, so every device this integration creates opts in to
    attempting unknown capabilities; the device's own error envelope
    then reports anything it really does not support.

    Args:
        config: Any mapping carrying the ``CONF_*`` connection keys:
            config-flow data, merged entry data and options, or
            options-flow input.

    Returns:
        A configured, not yet connected, ``AkuvoxDevice``.

    """
    device = AkuvoxDevice(
        host=str(config.get(CONF_HOST, "")),
        auth=build_auth_config(config),
        use_ssl=bool(config.get(CONF_USE_SSL, False)),
        verify_ssl=bool(config.get(CONF_VERIFY_SSL, True)),
    )
    device.attempt_unknown_capability = True
    return device


def relay_trigger_adapter(device: AkuvoxDevice) -> Capability | None:
    """Pick the relay-trigger adapter to request for ``device``.

    The library only auto-selects a transport whose status is confirmed
    SUPPORTED. For a model outside its matrix every transport is
    UNKNOWN and it refuses to choose, even with unknown capabilities
    allowed. This integration targets door phones, whose relay endpoint
    is ``/api/relay/trig``, so the API variant is requested explicitly
    in that case.

    Args:
        device: A connected device.

    Returns:
        The adapter to pass to ``trigger_relay``, or ``None`` to let the
        library choose.

    """
    capabilities = device.capabilities
    if not isinstance(capabilities, DeviceCapabilities):
        return None
    statuses = {
        variant: capabilities.status_of(variant)
        for variant in _RELAY_TRIGGER_VARIANTS
    }
    if CapabilityStatus.SUPPORTED in statuses.values():
        return None
    if statuses[Capability.RELAY_TRIGGER_API] is CapabilityStatus.UNKNOWN:
        _LOGGER.debug(
            "Model %s is not in the pylocal-akuvox capability matrix; "
            "triggering relays through /api/relay/trig",
            capabilities.device_class,
        )
        return Capability.RELAY_TRIGGER_API
    return None


async def async_trigger_relay(
    device: AkuvoxDevice,
    *,
    num: int,
    mode: int = 0,
    level: int = 0,
    delay: int = 0,
) -> None:
    """Trigger a relay, choosing a transport for models outside the matrix.

    Args:
        device: A connected device.
        num: Relay number, starting at 1.
        mode: Trigger mode as defined by the device API.
        level: Relay level as defined by the device API.
        delay: Hold delay in seconds.

    """
    adapter = relay_trigger_adapter(device)
    if adapter is None:
        await device.trigger_relay(num=num, mode=mode, level=level, delay=delay)
        return
    await device.trigger_relay(
        num=num,
        mode=mode,
        level=level,
        delay=delay,
        adapter=adapter,
    )


async def async_get_input_status(device: AkuvoxDevice) -> dict[str, int]:
    """Read the current level of every input from the device.

    pylocal-akuvox has no wrapper for ``/api/input/status``, so this
    goes through the library's HTTP client, which carries the
    connection's authentication and TLS settings.

    Args:
        device: The connected device.

    Returns:
        Input letter to level (0 = low, 1 = high), for example
        ``{"A": 0, "B": 1}``. Empty when the device reports no inputs.

    Raises:
        AkuvoxError: When the request fails or the device refuses it.

    """
    http = getattr(device, "_http", None)
    if http is None:
        return {}
    data = await http.get(INPUT_STATUS_PATH)
    levels: dict[str, int] = {}
    for key, value in (data or {}).items():
        match = INPUT_KEY_RE.fullmatch(key)
        if match is None:
            continue
        try:
            level = int(value)
        except (TypeError, ValueError):
            continue
        if level in (0, 1):
            levels[match.group(1)] = level
    return levels
