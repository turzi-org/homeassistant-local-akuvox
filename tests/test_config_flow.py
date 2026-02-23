# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Tests for the Akuvox config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pylocal_akuvox import (
    AkuvoxAuthenticationError,
    AkuvoxConnectionError,
    AkuvoxError,
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
    with patch(
        "custom_components.akuvox.config_flow.AkuvoxDevice",
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
        assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_successful_connection_creates_entry(
    hass: HomeAssistant,
) -> None:
    """Test successful connection creates config entry."""
    with patch(
        "custom_components.akuvox.config_flow.AkuvoxDevice",
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
            {CONF_AUTH_METHOD: AUTH_BASIC},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "admin", CONF_PASSWORD: "password"},
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
        "custom_components.akuvox.config_flow.AkuvoxDevice",
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
        "custom_components.akuvox.config_flow.AkuvoxDevice",
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
    from pytest_homeassistant_custom_component.common import (
        MockConfigEntry,
    )

    existing = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.200"},
        unique_id=MOCK_MAC.lower().replace(":", ""),
    )
    existing.add_to_hass(hass)

    with patch(
        "custom_components.akuvox.config_flow.AkuvoxDevice",
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
        "custom_components.akuvox.config_flow.AkuvoxDevice",
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
