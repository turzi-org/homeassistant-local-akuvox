# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Tests for the Akuvox config flow."""

from __future__ import annotations

import ssl
from typing import Any
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pylocal_akuvox import (
    AkuvoxAuthenticationError,
    AkuvoxConnectionError,
    AkuvoxError,
    DeviceInfo,
)
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.local_akuvox.config_flow import (
    _async_device_requires_https as _real_https_probe,
)
from custom_components.local_akuvox.config_flow import (
    _is_certificate_error,
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
    CONF_WEBHOOK_ENABLED,
    CONF_WEBHOOK_ID,
    DOMAIN,
)
from tests.conftest import MOCK_HOST, MOCK_MAC


async def test_user_step_shows_form(
    hass: HomeAssistant,
) -> None:
    """Test user step shows the host form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_user_step_rejects_empty_host(
    hass: HomeAssistant,
) -> None:
    """Test user step rejects empty host with invalid_host error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "   ", CONF_USE_SSL: False},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] is not None
    assert result["errors"]["base"] == "invalid_host"


async def test_ssl_step_appears_when_use_ssl_true(
    hass: HomeAssistant,
) -> None:
    """Test SSL step appears when use_ssl is True."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: MOCK_HOST, CONF_USE_SSL: True},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "ssl"


async def test_ssl_step_skipped_when_use_ssl_false(
    hass: HomeAssistant,
) -> None:
    """Test SSL step is skipped when use_ssl is False."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: MOCK_HOST, CONF_USE_SSL: False},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"


async def test_auth_step_shows_three_options(
    hass: HomeAssistant,
) -> None:
    """Test auth step shows 3 user-facing auth options."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: MOCK_HOST, CONF_USE_SSL: False},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"


async def test_credentials_step_appears_for_basic(
    hass: HomeAssistant,
) -> None:
    """Test credentials step appears for basic auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: MOCK_HOST, CONF_USE_SSL: False},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_AUTH_METHOD: AUTH_BASIC},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "credentials"


async def test_credentials_step_appears_for_digest(
    hass: HomeAssistant,
) -> None:
    """Test credentials step appears for digest auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: MOCK_HOST, CONF_USE_SSL: False},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_AUTH_METHOD: AUTH_DIGEST},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "credentials"


async def test_credentials_step_skipped_for_none(
    hass: HomeAssistant,
) -> None:
    """Test credentials step skipped for none/allowlist."""
    with (
        patch(
            "custom_components.local_akuvox.config_flow.create_device",
        ) as mock_cls,
        patch(
            "custom_components.local_akuvox._create_device",
        ) as mock_create,
    ):
        device = mock_cls.return_value
        device.get_info = AsyncMock(
            return_value=DeviceInfo(
                model="E21V",
                mac_address=MOCK_MAC,
                firmware_version="1.0.0",
                hardware_version="2.0.0",
            ),
        )

        setup_device = AsyncMock()
        setup_device.__aenter__ = AsyncMock(return_value=setup_device)
        setup_device.__aexit__ = AsyncMock(return_value=None)
        setup_device.get_info = AsyncMock(
            return_value=DeviceInfo(
                model="E21V",
                mac_address=MOCK_MAC,
                firmware_version="1.0.0",
                hardware_version="2.0.0",
            ),
        )
        setup_device.get_relay_status = AsyncMock(
            return_value={"RelayA": "closed"},
        )
        setup_device.get_device_config = AsyncMock(return_value={})
        mock_create.return_value = setup_device

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST, CONF_USE_SSL: False},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_AUTH_METHOD: AUTH_NONE},
        )
        # Now at webhook step
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "webhook"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_WEBHOOK_ENABLED: False},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "entities"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_successful_connection_creates_entry(
    hass: HomeAssistant,
) -> None:
    """Test successful connection creates config entry."""
    with (
        patch(
            "custom_components.local_akuvox.config_flow.create_device",
        ) as mock_cls,
        patch(
            "custom_components.local_akuvox._create_device",
        ) as mock_create,
    ):
        device = mock_cls.return_value
        device.get_info = AsyncMock(
            return_value=DeviceInfo(
                model="E21V",
                mac_address=MOCK_MAC,
                firmware_version="1.0.0",
                hardware_version="2.0.0",
            ),
        )

        setup_device = AsyncMock()
        setup_device.__aenter__ = AsyncMock(return_value=setup_device)
        setup_device.__aexit__ = AsyncMock(return_value=None)
        setup_device.get_info = AsyncMock(
            return_value=DeviceInfo(
                model="E21V",
                mac_address=MOCK_MAC,
                firmware_version="1.0.0",
                hardware_version="2.0.0",
            ),
        )
        setup_device.get_relay_status = AsyncMock(
            return_value={"RelayA": "closed"},
        )
        setup_device.get_device_config = AsyncMock(return_value={})
        mock_create.return_value = setup_device

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST, CONF_USE_SSL: False},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_AUTH_METHOD: AUTH_BASIC},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "admin", CONF_PASSWORD: "password"},
        )
        # Now at webhook step
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "webhook"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_WEBHOOK_ENABLED: False},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "entities"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "Akuvox E21V"
        assert result["data"][CONF_HOST] == MOCK_HOST
        assert result["data"][CONF_AUTH_METHOD] == AUTH_BASIC


async def test_cannot_connect_error(
    hass: HomeAssistant,
) -> None:
    """Test cannot_connect error on AkuvoxConnectionError."""
    with patch(
        "custom_components.local_akuvox.config_flow.create_device",
    ) as mock_cls:
        device = mock_cls.return_value
        device.get_info = AsyncMock(
            side_effect=AkuvoxConnectionError("Cannot connect"),
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST, CONF_USE_SSL: False},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_AUTH_METHOD: AUTH_NONE},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] is not None
        assert result["errors"]["base"] == "cannot_connect"


async def test_invalid_auth_error(
    hass: HomeAssistant,
) -> None:
    """Test invalid_auth error on AkuvoxAuthenticationError."""
    with patch(
        "custom_components.local_akuvox.config_flow.create_device",
    ) as mock_cls:
        device = mock_cls.return_value
        device.get_info = AsyncMock(
            side_effect=AkuvoxAuthenticationError("Bad auth"),
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST, CONF_USE_SSL: False},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_AUTH_METHOD: AUTH_BASIC},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "admin", CONF_PASSWORD: "wrong"},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] is not None
        assert result["errors"]["base"] == "invalid_auth"


async def test_already_configured_aborts(
    hass: HomeAssistant,
) -> None:
    """Test already_configured aborts on duplicate MAC."""
    existing = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.200"},
        unique_id=MOCK_MAC.lower().replace(":", ""),
    )
    existing.add_to_hass(hass)

    with patch(
        "custom_components.local_akuvox.config_flow.create_device",
    ) as mock_cls:
        device = mock_cls.return_value
        device.get_info = AsyncMock(
            return_value=DeviceInfo(
                model="E21V",
                mac_address=MOCK_MAC,
                firmware_version="1.0.0",
                hardware_version="2.0.0",
            ),
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST, CONF_USE_SSL: False},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_AUTH_METHOD: AUTH_NONE},
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"


async def test_unknown_error(
    hass: HomeAssistant,
) -> None:
    """Test unknown error on generic AkuvoxError."""
    with patch(
        "custom_components.local_akuvox.config_flow.create_device",
    ) as mock_cls:
        device = mock_cls.return_value
        device.get_info = AsyncMock(
            side_effect=AkuvoxError("Something went wrong"),
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST, CONF_USE_SSL: False},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_AUTH_METHOD: AUTH_NONE},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] is not None
        assert result["errors"]["base"] == "unknown"


# --- Options Flow Tests ---


async def test_options_flow_shows_current_values(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_device_config: Any,
) -> None:
    """Test options flow init step shows form with current values."""
    with patch(
        "custom_components.local_akuvox.create_device",
        autospec=True,
    ) as mock_cls:
        device = mock_cls.return_value
        device.get_info = AsyncMock(
            return_value=DeviceInfo(
                model="E21V",
                mac_address=MOCK_MAC,
                firmware_version="1.0.0",
                hardware_version="2.0.0",
            ),
        )
        device.get_relay_status = AsyncMock(
            return_value={"RelayA": 0},
        )
        device.trigger_relay = AsyncMock(return_value=None)
        device.get_device_config = AsyncMock(
            return_value=mock_device_config,
        )
        device.__aenter__ = AsyncMock(return_value=device)
        device.__aexit__ = AsyncMock(return_value=None)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data=mock_config_entry_data_none,
            unique_id=MOCK_MAC.lower().replace(":", ""),
        )
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(
            entry.entry_id,
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "init"

        schema = result["data_schema"]
        assert schema is not None
        validated = schema({})
        assert validated[CONF_HOST] == mock_config_entry_data_none[CONF_HOST]
        assert validated[CONF_USE_SSL] == mock_config_entry_data_none[CONF_USE_SSL]
        assert (
            validated[CONF_VERIFY_SSL] == mock_config_entry_data_none[CONF_VERIFY_SSL]
        )
        assert (
            validated[CONF_AUTH_METHOD] == mock_config_entry_data_none[CONF_AUTH_METHOD]
        )


async def test_options_flow_updates_entry(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_device_config: Any,
) -> None:
    """Test options flow saves updated values to entry.options."""
    with patch(
        "custom_components.local_akuvox.create_device",
        autospec=True,
    ) as mock_cls:
        device = mock_cls.return_value
        device.get_info = AsyncMock(
            return_value=DeviceInfo(
                model="E21V",
                mac_address=MOCK_MAC,
                firmware_version="1.0.0",
                hardware_version="2.0.0",
            ),
        )
        device.get_relay_status = AsyncMock(
            return_value={"RelayA": 0},
        )
        device.trigger_relay = AsyncMock(return_value=None)
        device.get_device_config = AsyncMock(
            return_value=mock_device_config,
        )
        device.__aenter__ = AsyncMock(return_value=device)
        device.__aexit__ = AsyncMock(return_value=None)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data=mock_config_entry_data_none,
            unique_id=MOCK_MAC.lower().replace(":", ""),
        )
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(
            entry.entry_id,
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "192.168.1.200",
                CONF_USE_SSL: True,
                CONF_VERIFY_SSL: False,
                CONF_AUTH_METHOD: AUTH_NONE,
                CONF_USERNAME: "",
                CONF_PASSWORD: "",
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "entities"
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {},
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert entry.options[CONF_HOST] == "192.168.1.200"
        assert entry.options[CONF_USE_SSL] is True
        assert entry.options[CONF_VERIFY_SSL] is False


async def test_options_flow_triggers_reload(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_device_config: Any,
) -> None:
    """Test integration reloads after options change."""
    with patch(
        "custom_components.local_akuvox.create_device",
        autospec=True,
    ) as mock_cls:
        device = mock_cls.return_value
        device.get_info = AsyncMock(
            return_value=DeviceInfo(
                model="E21V",
                mac_address=MOCK_MAC,
                firmware_version="1.0.0",
                hardware_version="2.0.0",
            ),
        )
        device.get_relay_status = AsyncMock(
            return_value={"RelayA": 0},
        )
        device.trigger_relay = AsyncMock(return_value=None)
        device.get_device_config = AsyncMock(
            return_value=mock_device_config,
        )
        device.__aenter__ = AsyncMock(return_value=device)
        device.__aexit__ = AsyncMock(return_value=None)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data=mock_config_entry_data_none,
            unique_id=MOCK_MAC.lower().replace(":", ""),
        )
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        with patch.object(
            hass.config_entries,
            "async_reload",
        ) as mock_reload:
            result = await hass.config_entries.options.async_init(
                entry.entry_id,
            )
            result = await hass.config_entries.options.async_configure(
                result["flow_id"],
                user_input={
                    CONF_HOST: MOCK_HOST,
                    CONF_USE_SSL: False,
                    CONF_VERIFY_SSL: True,
                    CONF_AUTH_METHOD: AUTH_NONE,
                    CONF_USERNAME: "",
                    CONF_PASSWORD: "",
                },
            )
            assert result["type"] is FlowResultType.FORM
            assert result["step_id"] == "entities"
            result = await hass.config_entries.options.async_configure(
                result["flow_id"],
                {},
            )
            await hass.async_block_till_done()
            mock_reload.assert_awaited_once_with(entry.entry_id)


async def test_options_flow_rejects_empty_host(
    hass: HomeAssistant,
    mock_relay_status: dict[str, Any],
    mock_device_info: DeviceInfo,
    mock_config_entry_data_none: dict[str, Any],
    mock_device_config: Any,
) -> None:
    """Test options flow rejects empty host with invalid_host error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_entry_data_none,
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "custom_components.local_akuvox.create_device",
            autospec=True,
        ) as mock_cls,
    ):
        instance = mock_cls.return_value
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        instance.get_relay_status = AsyncMock(return_value=mock_relay_status)
        instance.get_info = AsyncMock(return_value=mock_device_info)
        instance.get_device_config = AsyncMock(
            return_value=mock_device_config,
        )
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "",
            CONF_USE_SSL: False,
            CONF_VERIFY_SSL: True,
            CONF_AUTH_METHOD: AUTH_NONE,
            CONF_USERNAME: "",
            CONF_PASSWORD: "",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_host"}


async def test_options_flow_rejects_whitespace_host(
    hass: HomeAssistant,
    mock_relay_status: dict[str, Any],
    mock_device_info: DeviceInfo,
    mock_config_entry_data_none: dict[str, Any],
    mock_device_config: Any,
) -> None:
    """Test options flow rejects whitespace-only host."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_entry_data_none,
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "custom_components.local_akuvox.create_device",
            autospec=True,
        ) as mock_cls,
    ):
        instance = mock_cls.return_value
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        instance.get_relay_status = AsyncMock(return_value=mock_relay_status)
        instance.get_info = AsyncMock(return_value=mock_device_info)
        instance.get_device_config = AsyncMock(
            return_value=mock_device_config,
        )
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "   ",
            CONF_USE_SSL: False,
            CONF_VERIFY_SSL: True,
            CONF_AUTH_METHOD: AUTH_NONE,
            CONF_USERNAME: "",
            CONF_PASSWORD: "",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_host"}


async def test_options_flow_rejects_missing_credentials(
    hass: HomeAssistant,
    mock_relay_status: dict[str, Any],
    mock_device_info: DeviceInfo,
    mock_config_entry_data_none: dict[str, Any],
    mock_device_config: Any,
) -> None:
    """Test options flow rejects auth methods without credentials."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_entry_data_none,
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "custom_components.local_akuvox.create_device",
            autospec=True,
        ) as mock_cls,
    ):
        instance = mock_cls.return_value
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        instance.get_relay_status = AsyncMock(return_value=mock_relay_status)
        instance.get_info = AsyncMock(return_value=mock_device_info)
        instance.get_device_config = AsyncMock(
            return_value=mock_device_config,
        )
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: MOCK_HOST,
            CONF_USE_SSL: False,
            CONF_VERIFY_SSL: True,
            CONF_AUTH_METHOD: AUTH_BASIC,
            CONF_USERNAME: "",
            CONF_PASSWORD: "",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_options_flow_host_error_takes_precedence(
    hass: HomeAssistant,
    mock_relay_status: dict[str, Any],
    mock_device_info: DeviceInfo,
    mock_config_entry_data_none: dict[str, Any],
    mock_device_config: Any,
) -> None:
    """Test invalid_host error is not overwritten by invalid_auth."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_entry_data_none,
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "custom_components.local_akuvox.create_device",
            autospec=True,
        ) as mock_cls,
    ):
        instance = mock_cls.return_value
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        instance.get_relay_status = AsyncMock(return_value=mock_relay_status)
        instance.get_info = AsyncMock(return_value=mock_device_info)
        instance.get_device_config = AsyncMock(
            return_value=mock_device_config,
        )
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "   ",
            CONF_USE_SSL: False,
            CONF_VERIFY_SSL: True,
            CONF_AUTH_METHOD: AUTH_BASIC,
            CONF_USERNAME: "",
            CONF_PASSWORD: "",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_host"}


# --- Config Flow Webhook Step Tests ---


async def test_webhook_step_shows_form(
    hass: HomeAssistant,
) -> None:
    """Test webhook step shows form after connection test."""
    with patch(
        "custom_components.local_akuvox.config_flow.create_device",
    ) as mock_cls:
        device = mock_cls.return_value
        device.get_info = AsyncMock(
            return_value=DeviceInfo(
                model="E21V",
                mac_address=MOCK_MAC,
                firmware_version="1.0.0",
                hardware_version="2.0.0",
            ),
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST, CONF_USE_SSL: False},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_AUTH_METHOD: AUTH_NONE},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "webhook"


async def test_webhook_disabled_creates_entry(
    hass: HomeAssistant,
) -> None:
    """Test disabling webhook creates entry with no webhook config."""
    with (
        patch(
            "custom_components.local_akuvox.config_flow.create_device",
        ) as mock_cls,
        patch(
            "custom_components.local_akuvox._create_device",
        ) as mock_create,
    ):
        device = mock_cls.return_value
        device.get_info = AsyncMock(
            return_value=DeviceInfo(
                model="E21V",
                mac_address=MOCK_MAC,
                firmware_version="1.0.0",
                hardware_version="2.0.0",
            ),
        )

        setup_device = AsyncMock()
        setup_device.__aenter__ = AsyncMock(return_value=setup_device)
        setup_device.__aexit__ = AsyncMock(return_value=None)
        setup_device.get_info = AsyncMock(
            return_value=DeviceInfo(
                model="E21V",
                mac_address=MOCK_MAC,
                firmware_version="1.0.0",
                hardware_version="2.0.0",
            ),
        )
        setup_device.get_relay_status = AsyncMock(
            return_value={"RelayA": "closed"},
        )
        setup_device.get_device_config = AsyncMock(return_value={})
        mock_create.return_value = setup_device

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST, CONF_USE_SSL: False},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_AUTH_METHOD: AUTH_NONE},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_WEBHOOK_ENABLED: False},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "entities"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_WEBHOOK_ID] is None
    assert result["data"][CONF_WEBHOOK_ENABLED] is False


async def test_webhook_enabled_pushes_config(
    hass: HomeAssistant,
) -> None:
    """Test enabling webhook pushes action URLs to device."""
    with (
        patch(
            "custom_components.local_akuvox.config_flow.create_device",
        ) as mock_cls,
        patch(
            "custom_components.local_akuvox._create_device",
        ) as mock_create,
    ):
        device = mock_cls.return_value
        device.get_info = AsyncMock(
            return_value=DeviceInfo(
                model="E21V",
                mac_address=MOCK_MAC,
                firmware_version="1.0.0",
                hardware_version="2.0.0",
            ),
        )
        device.set_device_config = AsyncMock(return_value=None)
        device.__aenter__ = AsyncMock(return_value=device)
        device.__aexit__ = AsyncMock(return_value=None)

        setup_device = AsyncMock()
        setup_device.__aenter__ = AsyncMock(return_value=setup_device)
        setup_device.__aexit__ = AsyncMock(return_value=None)
        setup_device.get_info = AsyncMock(
            return_value=DeviceInfo(
                model="E21V",
                mac_address=MOCK_MAC,
                firmware_version="1.0.0",
                hardware_version="2.0.0",
            ),
        )
        setup_device.get_relay_status = AsyncMock(
            return_value={"RelayA": "closed"},
        )
        setup_device.get_device_config = AsyncMock(return_value={})
        mock_create.return_value = setup_device

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST, CONF_USE_SSL: False},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_AUTH_METHOD: AUTH_NONE},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_WEBHOOK_ENABLED: True},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "entities"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_WEBHOOK_ENABLED] is True
    assert result["data"][CONF_WEBHOOK_ID] is not None
    assert len(result["data"][CONF_WEBHOOK_ID]) == 64
    device.set_device_config.assert_awaited_once()


async def test_webhook_push_fails_shows_error(
    hass: HomeAssistant,
) -> None:
    """Test failed webhook push shows error and allows retry."""
    with patch(
        "custom_components.local_akuvox.config_flow.create_device",
    ) as mock_cls:
        device = mock_cls.return_value
        device.get_info = AsyncMock(
            return_value=DeviceInfo(
                model="E21V",
                mac_address=MOCK_MAC,
                firmware_version="1.0.0",
                hardware_version="2.0.0",
            ),
        )
        device.set_device_config = AsyncMock(
            side_effect=AkuvoxError("Push failed"),
        )
        device.__aenter__ = AsyncMock(return_value=device)
        device.__aexit__ = AsyncMock(return_value=None)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST, CONF_USE_SSL: False},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_AUTH_METHOD: AUTH_NONE},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_WEBHOOK_ENABLED: True},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "webhook"
    assert result["errors"] == {"base": "webhook_push_failed"}


async def test_webhook_push_fails_then_skip(
    hass: HomeAssistant,
) -> None:
    """Test user can skip webhook after push failure."""
    with (
        patch(
            "custom_components.local_akuvox.config_flow.create_device",
        ) as mock_cls,
        patch(
            "custom_components.local_akuvox._create_device",
        ) as mock_create,
    ):
        device = mock_cls.return_value
        device.get_info = AsyncMock(
            return_value=DeviceInfo(
                model="E21V",
                mac_address=MOCK_MAC,
                firmware_version="1.0.0",
                hardware_version="2.0.0",
            ),
        )
        device.set_device_config = AsyncMock(
            side_effect=AkuvoxError("Push failed"),
        )
        device.__aenter__ = AsyncMock(return_value=device)
        device.__aexit__ = AsyncMock(return_value=None)

        setup_device = AsyncMock()
        setup_device.__aenter__ = AsyncMock(return_value=setup_device)
        setup_device.__aexit__ = AsyncMock(return_value=None)
        setup_device.get_info = AsyncMock(
            return_value=DeviceInfo(
                model="E21V",
                mac_address=MOCK_MAC,
                firmware_version="1.0.0",
                hardware_version="2.0.0",
            ),
        )
        setup_device.get_relay_status = AsyncMock(
            return_value={"RelayA": "closed"},
        )
        setup_device.get_device_config = AsyncMock(return_value={})
        mock_create.return_value = setup_device

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST, CONF_USE_SSL: False},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_AUTH_METHOD: AUTH_NONE},
        )
        # First attempt fails
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_WEBHOOK_ENABLED: True},
        )
        assert result["errors"] == {"base": "webhook_push_failed"}

        # User skips
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_WEBHOOK_ENABLED: False},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "entities"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_WEBHOOK_ENABLED] is False
    assert result["data"][CONF_WEBHOOK_ID] is None


# --- Options Flow Webhook Tests ---


async def test_options_webhook_enable(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_device_config: Any,
) -> None:
    """Test options flow enables webhook and pushes config."""
    with patch(
        "custom_components.local_akuvox.create_device",
        autospec=True,
    ) as mock_cls:
        device = mock_cls.return_value
        device.get_info = AsyncMock(
            return_value=DeviceInfo(
                model="E21V",
                mac_address=MOCK_MAC,
                firmware_version="1.0.0",
                hardware_version="2.0.0",
            ),
        )
        device.get_relay_status = AsyncMock(
            return_value={"RelayA": 0},
        )
        device.trigger_relay = AsyncMock(return_value=None)
        device.get_device_config = AsyncMock(
            return_value=mock_device_config,
        )
        device.set_device_config = AsyncMock(return_value=None)
        device.__aenter__ = AsyncMock(return_value=device)
        device.__aexit__ = AsyncMock(return_value=None)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data=mock_config_entry_data_none,
            unique_id=MOCK_MAC.lower().replace(":", ""),
        )
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    with (
        patch(
            "custom_components.local_akuvox.config_flow.create_device",
        ) as mock_flow_cls,
        patch(
            "custom_components.local_akuvox._create_device",
        ) as mock_create,
    ):
        flow_dev = mock_flow_cls.return_value
        flow_dev.set_device_config = AsyncMock(return_value=None)
        flow_dev.__aenter__ = AsyncMock(return_value=flow_dev)
        flow_dev.__aexit__ = AsyncMock(return_value=None)

        setup_device = AsyncMock()
        setup_device.__aenter__ = AsyncMock(return_value=setup_device)
        setup_device.__aexit__ = AsyncMock(return_value=None)
        setup_device.get_info = AsyncMock(
            return_value=DeviceInfo(
                model="E21V",
                mac_address=MOCK_MAC,
                firmware_version="1.0.0",
                hardware_version="2.0.0",
            ),
        )
        setup_device.get_relay_status = AsyncMock(
            return_value={"RelayA": "closed"},
        )
        setup_device.get_device_config = AsyncMock(return_value={})
        mock_create.return_value = setup_device

        result = await hass.config_entries.options.async_init(
            entry.entry_id,
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: MOCK_HOST,
                CONF_USE_SSL: False,
                CONF_VERIFY_SSL: True,
                CONF_AUTH_METHOD: AUTH_NONE,
                CONF_USERNAME: "",
                CONF_PASSWORD: "",
                CONF_WEBHOOK_ENABLED: True,
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "entities"
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {},
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_WEBHOOK_ENABLED] is True
    assert entry.options[CONF_WEBHOOK_ID] is not None


async def test_options_webhook_disable(
    hass: HomeAssistant,
    mock_config_entry_data_webhook: dict[str, Any],
    mock_device_config: Any,
) -> None:
    """Test options flow disables webhook and pushes clear config."""
    with patch(
        "custom_components.local_akuvox.create_device",
        autospec=True,
    ) as mock_cls:
        device = mock_cls.return_value
        device.get_info = AsyncMock(
            return_value=DeviceInfo(
                model="E21V",
                mac_address=MOCK_MAC,
                firmware_version="1.0.0",
                hardware_version="2.0.0",
            ),
        )
        device.get_relay_status = AsyncMock(
            return_value={"RelayA": 0},
        )
        device.trigger_relay = AsyncMock(return_value=None)
        device.get_device_config = AsyncMock(
            return_value=mock_device_config,
        )
        device.set_device_config = AsyncMock(return_value=None)
        device.__aenter__ = AsyncMock(return_value=device)
        device.__aexit__ = AsyncMock(return_value=None)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data=mock_config_entry_data_webhook,
            unique_id=MOCK_MAC.lower().replace(":", ""),
        )
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    with (
        patch(
            "custom_components.local_akuvox.config_flow.create_device",
        ) as mock_flow_cls,
        patch(
            "custom_components.local_akuvox._create_device",
        ) as mock_create,
    ):
        flow_dev = mock_flow_cls.return_value
        flow_dev.set_device_config = AsyncMock(return_value=None)
        flow_dev.__aenter__ = AsyncMock(return_value=flow_dev)
        flow_dev.__aexit__ = AsyncMock(return_value=None)

        setup_device = AsyncMock()
        setup_device.__aenter__ = AsyncMock(return_value=setup_device)
        setup_device.__aexit__ = AsyncMock(return_value=None)
        setup_device.get_info = AsyncMock(
            return_value=DeviceInfo(
                model="E21V",
                mac_address=MOCK_MAC,
                firmware_version="1.0.0",
                hardware_version="2.0.0",
            ),
        )
        setup_device.get_relay_status = AsyncMock(
            return_value={"RelayA": "closed"},
        )
        setup_device.get_device_config = AsyncMock(return_value={})
        mock_create.return_value = setup_device

        result = await hass.config_entries.options.async_init(
            entry.entry_id,
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: MOCK_HOST,
                CONF_USE_SSL: False,
                CONF_VERIFY_SSL: True,
                CONF_AUTH_METHOD: AUTH_NONE,
                CONF_USERNAME: "",
                CONF_PASSWORD: "",
                CONF_WEBHOOK_ENABLED: False,
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "entities"
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {},
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_WEBHOOK_ENABLED] is False


async def test_options_webhook_push_fails(
    hass: HomeAssistant,
    mock_config_entry_data_none: dict[str, Any],
    mock_device_config: Any,
) -> None:
    """Test options flow shows error on webhook push failure."""
    with patch(
        "custom_components.local_akuvox.create_device",
        autospec=True,
    ) as mock_cls:
        device = mock_cls.return_value
        device.get_info = AsyncMock(
            return_value=DeviceInfo(
                model="E21V",
                mac_address=MOCK_MAC,
                firmware_version="1.0.0",
                hardware_version="2.0.0",
            ),
        )
        device.get_relay_status = AsyncMock(
            return_value={"RelayA": 0},
        )
        device.trigger_relay = AsyncMock(return_value=None)
        device.get_device_config = AsyncMock(
            return_value=mock_device_config,
        )
        device.__aenter__ = AsyncMock(return_value=device)
        device.__aexit__ = AsyncMock(return_value=None)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data=mock_config_entry_data_none,
            unique_id=MOCK_MAC.lower().replace(":", ""),
        )
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    with patch(
        "custom_components.local_akuvox.config_flow.create_device",
    ) as mock_flow_cls:
        flow_dev = mock_flow_cls.return_value
        flow_dev.set_device_config = AsyncMock(
            side_effect=AkuvoxError("Push failed"),
        )
        flow_dev.__aenter__ = AsyncMock(return_value=flow_dev)
        flow_dev.__aexit__ = AsyncMock(return_value=None)

        result = await hass.config_entries.options.async_init(
            entry.entry_id,
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: MOCK_HOST,
                CONF_USE_SSL: False,
                CONF_VERIFY_SSL: True,
                CONF_AUTH_METHOD: AUTH_NONE,
                CONF_USERNAME: "",
                CONF_PASSWORD: "",
                CONF_WEBHOOK_ENABLED: True,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "webhook_push_failed"}


# ── Forced HTTPS and certificate handling ─────────────────────────

S535_INFO = DeviceInfo(
    model="S535",
    mac_address=MOCK_MAC,
    firmware_version="535.30.10.245",
    hardware_version="535.0",
)
PROBE_URL = f"http://{MOCK_HOST}/api/system/info"


def _certificate_error() -> AkuvoxConnectionError:
    """Build the error pylocal-akuvox raises for an untrusted certificate."""
    err = AkuvoxConnectionError(
        "Connection to https://10.0.15.20 failed: certificate verify failed",
    )
    err.__cause__ = ssl.SSLCertVerificationError(
        1,
        "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: "
        "self-signed certificate",
    )
    return err


def _flow_device(enter_error: Exception | None = None) -> AsyncMock:
    """Return a device mock for the config flow's connection test."""
    device = AsyncMock()
    device.__aenter__ = AsyncMock(return_value=device, side_effect=enter_error)
    device.__aexit__ = AsyncMock(return_value=None)
    device.get_info = AsyncMock(return_value=S535_INFO)
    device.set_device_config = AsyncMock(return_value=None)
    return device


def _setup_device() -> AsyncMock:
    """Return a device mock for the entry setup that follows the flow."""
    device = AsyncMock()
    device.__aenter__ = AsyncMock(return_value=device)
    device.__aexit__ = AsyncMock(return_value=None)
    device.get_info = AsyncMock(return_value=S535_INFO)
    device.get_relay_status = AsyncMock(return_value={"RelayA": 0})
    device.get_device_config = AsyncMock(return_value={})
    device.list_users = AsyncMock(return_value=[])
    return device


def _ssl_settings(mock_create: Any) -> list[tuple[bool, bool]]:
    """Return the SSL settings of every device the flow created, in order."""
    return [
        (call.args[0][CONF_USE_SSL], call.args[0][CONF_VERIFY_SSL])
        for call in mock_create.call_args_list
    ]


async def _start_flow(
    hass: HomeAssistant,
    *,
    use_ssl: bool = False,
    verify_ssl: bool = True,
) -> Any:
    """Drive the flow through the host and SSL steps up to the auth form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: MOCK_HOST, CONF_USE_SSL: use_ssl},
    )
    if use_ssl:
        assert result["step_id"] == "ssl"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_VERIFY_SSL: verify_ssl},
        )
    assert result["step_id"] == "auth"
    return result


async def _submit_no_auth(hass: HomeAssistant, result: Any) -> Any:
    """Submit the auth step without credentials, running the connection test."""
    return await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_AUTH_METHOD: AUTH_NONE},
    )


async def _finish_flow(
    hass: HomeAssistant,
    result: Any,
    *,
    webhook: bool = False,
) -> Any:
    """Complete the webhook and entities steps and create the entry."""
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "webhook"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_WEBHOOK_ENABLED: webhook},
    )
    assert result["step_id"] == "entities"
    return await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )


async def test_forced_https_disables_verification_for_self_signed_cert(
    hass: HomeAssistant,
    mock_https_probe: AsyncMock,
) -> None:
    """A device that redirects to HTTPS with a factory certificate connects."""
    mock_https_probe.return_value = True
    with (
        patch(
            "custom_components.local_akuvox.config_flow.create_device",
            side_effect=[_flow_device(_certificate_error()), _flow_device()],
        ) as mock_create,
        patch(
            "custom_components.local_akuvox._create_device",
            return_value=_setup_device(),
        ),
    ):
        result = await _start_flow(hass)
        result = await _submit_no_auth(hass, result)
        result = await _finish_flow(hass, result)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_USE_SSL] is True
    assert result["data"][CONF_VERIFY_SSL] is False
    assert _ssl_settings(mock_create) == [(True, True), (True, False)]
    mock_https_probe.assert_awaited_once_with(hass, MOCK_HOST)


async def test_forced_https_keeps_verification_for_trusted_cert(
    hass: HomeAssistant,
    mock_https_probe: AsyncMock,
) -> None:
    """A redirecting device with a trusted certificate stays verified."""
    mock_https_probe.return_value = True
    with (
        patch(
            "custom_components.local_akuvox.config_flow.create_device",
            side_effect=[_flow_device()],
        ) as mock_create,
        patch(
            "custom_components.local_akuvox._create_device",
            return_value=_setup_device(),
        ),
    ):
        result = await _start_flow(hass)
        result = await _submit_no_auth(hass, result)
        result = await _finish_flow(hass, result)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_USE_SSL] is True
    assert result["data"][CONF_VERIFY_SSL] is True
    assert _ssl_settings(mock_create) == [(True, True)]


async def test_forced_https_other_connection_error_reports_cannot_connect(
    hass: HomeAssistant,
    mock_https_probe: AsyncMock,
) -> None:
    """Only certificate failures trigger the unverified retry."""
    mock_https_probe.return_value = True
    with patch(
        "custom_components.local_akuvox.config_flow.create_device",
        side_effect=[_flow_device(AkuvoxConnectionError("Connection refused"))],
    ) as mock_create:
        result = await _start_flow(hass)
        result = await _submit_no_auth(hass, result)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert result["errors"] == {"base": "cannot_connect"}
    assert _ssl_settings(mock_create) == [(True, True)]


async def test_explicit_ssl_certificate_error_returns_to_ssl_step(
    hass: HomeAssistant,
    mock_https_probe: AsyncMock,
) -> None:
    """An explicit verified-SSL choice is respected and explained."""
    with (
        patch(
            "custom_components.local_akuvox.config_flow.create_device",
            side_effect=[_flow_device(_certificate_error()), _flow_device()],
        ) as mock_create,
        patch(
            "custom_components.local_akuvox._create_device",
            return_value=_setup_device(),
        ),
    ):
        result = await _start_flow(hass, use_ssl=True, verify_ssl=True)
        result = await _submit_no_auth(hass, result)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "ssl"
        assert result["errors"] == {"base": "ssl_verify_failed"}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_VERIFY_SSL: False},
        )
        assert result["step_id"] == "auth"
        result = await _submit_no_auth(hass, result)
        result = await _finish_flow(hass, result)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_USE_SSL] is True
    assert result["data"][CONF_VERIFY_SSL] is False
    assert _ssl_settings(mock_create) == [(True, True), (True, False)]
    mock_https_probe.assert_not_awaited()


async def test_plain_http_device_keeps_http(
    hass: HomeAssistant,
    mock_https_probe: AsyncMock,
) -> None:
    """A device that answers plain HTTP is configured without SSL."""
    with (
        patch(
            "custom_components.local_akuvox.config_flow.create_device",
            side_effect=[_flow_device()],
        ) as mock_create,
        patch(
            "custom_components.local_akuvox._create_device",
            return_value=_setup_device(),
        ),
    ):
        result = await _start_flow(hass)
        result = await _submit_no_auth(hass, result)
        result = await _finish_flow(hass, result)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_USE_SSL] is False
    assert result["data"][CONF_VERIFY_SSL] is True
    assert _ssl_settings(mock_create) == [(False, True)]
    mock_https_probe.assert_awaited_once_with(hass, MOCK_HOST)


async def test_webhook_push_uses_detected_ssl_settings(
    hass: HomeAssistant,
    mock_https_probe: AsyncMock,
) -> None:
    """The webhook push connects with the SSL settings that worked."""
    mock_https_probe.return_value = True
    push_device = _flow_device()
    with (
        patch(
            "custom_components.local_akuvox.config_flow.create_device",
            side_effect=[
                _flow_device(_certificate_error()),
                _flow_device(),
                push_device,
            ],
        ) as mock_create,
        patch(
            "custom_components.local_akuvox._create_device",
            return_value=_setup_device(),
        ),
    ):
        result = await _start_flow(hass)
        result = await _submit_no_auth(hass, result)
        result = await _finish_flow(hass, result, webhook=True)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_WEBHOOK_ENABLED] is True
    assert _ssl_settings(mock_create)[-1] == (True, False)
    push_device.set_device_config.assert_awaited_once()


@pytest.mark.parametrize(
    ("status", "location", "expected"),
    [
        (308, "https://192.168.1.100:443/api/system/info", True),
        (301, "https://192.168.1.100/api/system/info", True),
        (302, "http://192.168.1.100/login", False),
        (200, None, False),
    ],
)
async def test_https_probe_detects_redirect_to_https(
    hass: HomeAssistant,
    aioclient_mock: Any,
    status: int,
    location: str | None,
    expected: bool,
) -> None:
    """The probe reports only redirects that point at an HTTPS URL."""
    headers = {"Location": location} if location else {}
    aioclient_mock.get(PROBE_URL, status=status, headers=headers)

    assert await _real_https_probe(hass, MOCK_HOST) is expected
    assert aioclient_mock.call_count == 1


async def test_https_probe_returns_false_when_unreachable(
    hass: HomeAssistant,
    aioclient_mock: Any,
) -> None:
    """Transport failures leave the regular connection test to report them."""
    aioclient_mock.get(PROBE_URL, exc=aiohttp.ClientConnectionError("refused"))

    assert await _real_https_probe(hass, MOCK_HOST) is False


def test_is_certificate_error_walks_cause_chain() -> None:
    """A wrapped certificate verification failure is recognised."""
    assert _is_certificate_error(_certificate_error()) is True


def test_is_certificate_error_follows_implicit_context() -> None:
    """Implicit exception chaining is followed as well."""
    err = AkuvoxConnectionError("wrapped")
    err.__context__ = ssl.SSLCertVerificationError(1, "verify failed")
    assert _is_certificate_error(err) is True


def test_is_certificate_error_ignores_other_failures() -> None:
    """A plain connection failure is not a certificate problem."""
    assert _is_certificate_error(AkuvoxConnectionError("refused")) is False
