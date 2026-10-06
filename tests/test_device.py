# SPDX-FileCopyrightText: 2026 Turzi
# SPDX-License-Identifier: Apache-2.0

"""Tests for device construction and capability policy."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pylocal_akuvox import (
    AuthMethod,
    Capability,
    CapabilityStatus,
    DeviceCapabilities,
)

from custom_components.local_akuvox.const import (
    AUTH_BASIC,
    AUTH_DIGEST,
    AUTH_NONE,
    CONF_AUTH_METHOD,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USE_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from custom_components.local_akuvox.device import (
    async_get_input_status,
    async_trigger_relay,
    build_auth_config,
    create_device,
    relay_trigger_adapter,
)

S535_CONFIG: dict[str, Any] = {
    CONF_HOST: "10.0.15.20",
    CONF_USE_SSL: True,
    CONF_VERIFY_SSL: False,
    CONF_AUTH_METHOD: AUTH_NONE,
    CONF_USERNAME: "",
    CONF_PASSWORD: "",
}


def _profile(
    statuses: dict[Capability, CapabilityStatus] | None = None,
    *,
    in_matrix: bool = True,
) -> DeviceCapabilities:
    """Build a capability profile like the ones the library produces."""
    notes = {} if in_matrix else {"device_not_in_matrix": "not in matrix"}
    return DeviceCapabilities(
        device_class="S535",
        firmware_version="535.30.10.245",
        capabilities=statuses or {},
        field_aliases={},
        schema_shapes={},
        notes=notes,
    )


def _device_with(capabilities: Any) -> MagicMock:
    """Return a device mock exposing ``capabilities``."""
    device = MagicMock()
    device.capabilities = capabilities
    device.trigger_relay = AsyncMock(return_value=None)
    return device


def test_build_auth_config_none_has_no_credentials() -> None:
    """No-auth settings must not carry credentials into the library."""
    auth = build_auth_config({**S535_CONFIG, CONF_USERNAME: "ignored"})
    assert auth.method is AuthMethod.NONE
    assert auth.username is None
    assert auth.password is None


@pytest.mark.parametrize(
    ("method", "expected"),
    [(AUTH_BASIC, AuthMethod.BASIC), (AUTH_DIGEST, AuthMethod.DIGEST)],
)
def test_build_auth_config_with_credentials(
    method: str,
    expected: AuthMethod,
) -> None:
    """Basic and digest settings carry the username and password."""
    auth = build_auth_config(
        {
            **S535_CONFIG,
            CONF_AUTH_METHOD: method,
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "secret",
        }
    )
    assert auth.method is expected
    assert auth.username == "admin"
    assert auth.password == "secret"  # noqa: S105


def test_create_device_opts_in_to_unknown_capabilities() -> None:
    """Every device must attempt capabilities the matrix does not list."""
    device = create_device(S535_CONFIG)
    assert device.attempt_unknown_capability is True


def test_create_device_passes_connection_settings() -> None:
    """Host and SSL settings reach the library constructor unchanged."""
    with patch(
        "custom_components.local_akuvox.device.AkuvoxDevice",
    ) as mock_cls:
        device = create_device(S535_CONFIG)

    mock_cls.assert_called_once()
    kwargs = mock_cls.call_args.kwargs
    assert kwargs["host"] == "10.0.15.20"
    assert kwargs["use_ssl"] is True
    assert kwargs["verify_ssl"] is False
    assert kwargs["auth"].method is AuthMethod.NONE
    assert device is mock_cls.return_value
    assert device.attempt_unknown_capability is True


def test_relay_trigger_adapter_for_model_outside_matrix() -> None:
    """A model the matrix does not know gets the door-phone API adapter."""
    device = _device_with(_profile(in_matrix=False))
    assert relay_trigger_adapter(device) is Capability.RELAY_TRIGGER_API


@pytest.mark.parametrize(
    "statuses",
    [
        {Capability.RELAY_TRIGGER_API: CapabilityStatus.SUPPORTED},
        {
            Capability.RELAY_TRIGGER_API: CapabilityStatus.UNSUPPORTED,
            Capability.RELAY_TRIGGER_FCGI: CapabilityStatus.SUPPORTED,
        },
    ],
)
def test_relay_trigger_adapter_defers_to_supported_variant(
    statuses: dict[Capability, CapabilityStatus],
) -> None:
    """When a variant is confirmed supported, the library chooses."""
    device = _device_with(_profile(statuses))
    assert relay_trigger_adapter(device) is None


def test_relay_trigger_adapter_respects_confirmed_unsupported_api() -> None:
    """An API variant confirmed unsupported is never forced."""
    device = _device_with(
        _profile({Capability.RELAY_TRIGGER_API: CapabilityStatus.UNSUPPORTED}),
    )
    assert relay_trigger_adapter(device) is None


@pytest.mark.parametrize("capabilities", [None, MagicMock()])
def test_relay_trigger_adapter_without_profile(capabilities: Any) -> None:
    """Without a real capability profile the library keeps control."""
    device = _device_with(capabilities)
    assert relay_trigger_adapter(device) is None


async def test_async_trigger_relay_adds_adapter_for_unknown_model() -> None:
    """Relay triggers on an unlisted model name the API adapter."""
    device = _device_with(_profile(in_matrix=False))
    await async_trigger_relay(device, num=1, mode=0, level=0, delay=5)
    device.trigger_relay.assert_awaited_once_with(
        num=1,
        mode=0,
        level=0,
        delay=5,
        adapter=Capability.RELAY_TRIGGER_API,
    )


async def test_async_trigger_relay_passes_through_when_supported() -> None:
    """Relay triggers on a listed model leave adapter selection alone."""
    device = _device_with(
        _profile({Capability.RELAY_TRIGGER_API: CapabilityStatus.SUPPORTED}),
    )
    await async_trigger_relay(device, num=2, mode=1, level=1, delay=3)
    device.trigger_relay.assert_awaited_once_with(num=2, mode=1, level=1, delay=3)


# ── async_get_input_status ───────────────────────────────────


async def test_get_input_status_parses_levels() -> None:
    """Input levels are keyed by letter; other keys and junk are ignored."""
    device = MagicMock()
    device._http.get = AsyncMock(
        return_value={
            "InputA": 0,
            "InputB": "1",
            "InputC": "x",
            "InputD": 2,
            "Other": 1,
        }
    )

    assert await async_get_input_status(device) == {"A": 0, "B": 1}
    device._http.get.assert_awaited_once_with("/api/input/status")


async def test_get_input_status_empty_response() -> None:
    """An empty envelope yields no levels."""
    device = MagicMock()
    device._http.get = AsyncMock(return_value=None)

    assert await async_get_input_status(device) == {}
