# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Shared test fixtures for Akuvox integration tests."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pylocal_akuvox import (
    DeviceInfo,
)

from custom_components.akuvox.const import (
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

MOCK_HOST = "192.168.1.100"
MOCK_MAC = "AA:BB:CC:DD:EE:FF"
MOCK_MODEL = "E21V"
MOCK_FW_VERSION = "1.0.0"
MOCK_HW_VERSION = "2.0.0"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    enable_custom_integrations: None,
) -> None:
    """Enable custom integrations for all tests."""


@pytest.fixture
def mock_device_info() -> DeviceInfo:
    """Return a mock DeviceInfo object."""
    return DeviceInfo(
        model=MOCK_MODEL,
        mac_address=MOCK_MAC,
        firmware_version=MOCK_FW_VERSION,
        hardware_version=MOCK_HW_VERSION,
    )


@pytest.fixture
def mock_relay_status() -> dict[str, Any]:
    """Return a mock relay status response with one relay."""
    return {
        "RelayA": "closed",
    }


@pytest.fixture
def mock_relay_status_multi() -> dict[str, Any]:
    """Return a mock relay status response with two relays."""
    return {
        "RelayA": "closed",
        "RelayB": "open",
    }


@pytest.fixture
def mock_config_entry_data_none() -> dict[str, Any]:
    """Return mock config entry data with no auth."""
    return {
        CONF_HOST: MOCK_HOST,
        CONF_USE_SSL: False,
        CONF_VERIFY_SSL: True,
        CONF_AUTH_METHOD: AUTH_NONE,
        CONF_USERNAME: "",
        CONF_PASSWORD: "",
    }


@pytest.fixture
def mock_config_entry_data_basic() -> dict[str, Any]:
    """Return mock config entry data with basic auth."""
    return {
        CONF_HOST: MOCK_HOST,
        CONF_USE_SSL: False,
        CONF_VERIFY_SSL: True,
        CONF_AUTH_METHOD: AUTH_BASIC,
        CONF_USERNAME: "admin",
        CONF_PASSWORD: "password",
    }


@pytest.fixture
def mock_config_entry_data_digest() -> dict[str, Any]:
    """Return mock config entry data with digest auth."""
    return {
        CONF_HOST: MOCK_HOST,
        CONF_USE_SSL: True,
        CONF_VERIFY_SSL: False,
        CONF_AUTH_METHOD: AUTH_DIGEST,
        CONF_USERNAME: "admin",
        CONF_PASSWORD: "secret",
    }


@pytest.fixture
def mock_akuvox_device(
    mock_device_info: DeviceInfo,
    mock_relay_status: dict[str, Any],
) -> Generator[AsyncMock]:
    """Return a mocked AkuvoxDevice."""
    with patch(
        "custom_components.akuvox.AkuvoxDevice",
        autospec=True,
    ) as mock_cls:
        device = mock_cls.return_value
        device.get_info = AsyncMock(return_value=mock_device_info)
        device.get_relay_status = AsyncMock(
            return_value=mock_relay_status,
        )
        device.trigger_relay = AsyncMock(return_value=None)
        device.__aenter__ = AsyncMock(return_value=device)
        device.__aexit__ = AsyncMock(return_value=None)
        yield device
