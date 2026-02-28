# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Shared test fixtures for Akuvox integration tests."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pylocal_akuvox import (
    AccessSchedule,
    DeviceInfo,
    User,
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
    CONFIG_KEY_LOCATION,
    CONFIG_KEY_RELAY_HOLD_DELAY,
    CONFIG_KEY_RELAY_MODE_SUFFIX,
    CONFIG_KEY_RELAY_NAME,
    CONFIG_KEY_RELAY_PREFIX,
    CONFIG_KEY_RELAY_TYPE_SUFFIX,
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
def mock_device_config() -> Any:
    """Return a default mock DeviceConfig.

    Provides config for a two-relay device with typical values.
    Use mock_device_config_factory for customized configs.

    Returns:
        A DeviceConfig instance with default two-relay config.

    """
    from pylocal_akuvox import (  # type: ignore[attr-defined]
        DeviceConfig,
    )

    return DeviceConfig(
        data={
            CONFIG_KEY_LOCATION: "TestLab Intercom",
            f"{CONFIG_KEY_RELAY_NAME}A": "Front Gate",
            f"{CONFIG_KEY_RELAY_NAME}B": "Side Gate",
            f"{CONFIG_KEY_RELAY_HOLD_DELAY}A": "5",
            f"{CONFIG_KEY_RELAY_HOLD_DELAY}B": "5",
            f"{CONFIG_KEY_RELAY_PREFIX}A{CONFIG_KEY_RELAY_TYPE_SUFFIX}": "0",
            f"{CONFIG_KEY_RELAY_PREFIX}B{CONFIG_KEY_RELAY_TYPE_SUFFIX}": "0",
            f"{CONFIG_KEY_RELAY_PREFIX}A{CONFIG_KEY_RELAY_MODE_SUFFIX}": "0",
            f"{CONFIG_KEY_RELAY_PREFIX}B{CONFIG_KEY_RELAY_MODE_SUFFIX}": "0",
        },
    )


@pytest.fixture
def mock_device_config_factory() -> Any:
    """Return a factory for creating customized DeviceConfig objects.

    Returns:
        A callable that accepts keyword overrides for config keys.

    """
    from pylocal_akuvox import (  # type: ignore[attr-defined]
        DeviceConfig,
    )

    def _factory(**overrides: str) -> Any:
        """Create a DeviceConfig with optional key overrides.

        Args:
            **overrides: Key-value pairs to override default config.

        Returns:
            A DeviceConfig with the merged data.

        """
        base: dict[str, str] = {
            CONFIG_KEY_LOCATION: "TestLab Intercom",
            f"{CONFIG_KEY_RELAY_NAME}A": "Front Gate",
            f"{CONFIG_KEY_RELAY_NAME}B": "Side Gate",
            f"{CONFIG_KEY_RELAY_HOLD_DELAY}A": "5",
            f"{CONFIG_KEY_RELAY_HOLD_DELAY}B": "5",
            f"{CONFIG_KEY_RELAY_PREFIX}A{CONFIG_KEY_RELAY_TYPE_SUFFIX}": "0",
            f"{CONFIG_KEY_RELAY_PREFIX}B{CONFIG_KEY_RELAY_TYPE_SUFFIX}": "0",
            f"{CONFIG_KEY_RELAY_PREFIX}A{CONFIG_KEY_RELAY_MODE_SUFFIX}": "0",
            f"{CONFIG_KEY_RELAY_PREFIX}B{CONFIG_KEY_RELAY_MODE_SUFFIX}": "0",
        }
        base.update(overrides)
        return DeviceConfig(data=base)

    return _factory


@pytest.fixture
def mock_akuvox_device(
    mock_device_info: DeviceInfo,
    mock_relay_status: dict[str, Any],
    mock_device_config: Any,
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
        device.get_device_config = AsyncMock(
            return_value=mock_device_config,
        )
        device.trigger_relay = AsyncMock(return_value=None)
        device.__aenter__ = AsyncMock(return_value=device)
        device.__aexit__ = AsyncMock(return_value=None)
        # Schedule and user CRUD methods
        device.list_schedules = AsyncMock(return_value=[])
        device.add_schedule = AsyncMock(return_value=None)
        device.modify_schedule = AsyncMock(return_value=None)
        device.delete_schedule = AsyncMock(return_value=None)
        device.list_users = AsyncMock(return_value=[])
        device.add_user = AsyncMock(return_value=None)
        device.modify_user = AsyncMock(return_value=None)
        device.delete_user = AsyncMock(return_value=None)
        yield device


@pytest.fixture
def mock_schedule_list() -> list[AccessSchedule]:
    """Return a mock list of AccessSchedule objects.

    Includes one local and one cloud-provisioned schedule.
    """
    return [
        AccessSchedule(
            id="1",
            schedule_type="1",
            name="Weekday Access",
            week="12345",
            daily=None,
            date_start=None,
            date_end=None,
            time_start="08:00",
            time_end="18:00",
            display_id="1",
            source_type="1",
            mode=None,
            sun=None,
            mon="1",
            tue="1",
            wed="1",
            thur="1",
            fri="1",
            sat=None,
        ),
        AccessSchedule(
            id="2",
            schedule_type="2",
            name="Cloud Schedule",
            week=None,
            daily="00:00-23:59",
            date_start=None,
            date_end=None,
            time_start="00:00",
            time_end="23:59",
            display_id="2",
            source_type="2",
            mode=None,
            sun=None,
            mon=None,
            tue=None,
            wed=None,
            thur=None,
            fri=None,
            sat=None,
        ),
    ]


@pytest.fixture
def mock_user_list() -> list[User]:
    """Return a mock list of User objects.

    Includes one local and one cloud-provisioned user.
    """
    return [
        User(
            id="42",
            name="John Doe",
            user_id="john.doe",
            schedule_relay="1-1;",
            web_relay=None,
            private_pin="1234",
            card_code="ABC123",
            lift_floor_num="3",
            user_type=None,
            source=None,
            source_type="1",
        ),
        User(
            id="99",
            name="Cloud User",
            user_id="cloud.user",
            schedule_relay="2-1;",
            web_relay=None,
            private_pin="5678",
            card_code=None,
            lift_floor_num="1",
            user_type=None,
            source=None,
            source_type="2",
        ),
    ]


@pytest.fixture
def mock_empty_list() -> list[Any]:
    """Return an empty list for schedule/user mocks."""
    return []
