# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Lock platform for the Akuvox integration."""

from __future__ import annotations

import logging
from typing import Any, cast

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, ServiceResponse, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later
from pylocal_akuvox import (
    AkuvoxError,
    AkuvoxValidationError,
)

from .const import (
    DEFAULT_HOLD_DELAY_SECONDS,
    DEFAULT_RELAY_MODE,
    DEFAULT_RELAY_TYPE,
    DOMAIN,
    RELAY_KEY_RE,
)
from .coordinator import AkuvoxDataUpdateCoordinator
from .entity import AkuvoxEntity

_LOGGER = logging.getLogger(__name__)

# Extra seconds added to the unlock delay before polling the device,
# giving the relay time to re-lock after the window expires.
_RELAY_REFRESH_BUFFER_SECONDS = 1

# Akuvox devices expose relays as "RelayA", "RelayB", etc.
# with a single uppercase letter A-Z suffix.


def _relay_key_to_number(relay_key: str) -> int | None:
    """Convert a relay key like 'RelayA' to a relay number (1-based).

    Args:
        relay_key: The relay key from the device (e.g., "RelayA").

    Returns:
        The 1-based relay number, or None if format is unrecognized.

    """
    match = RELAY_KEY_RE.fullmatch(relay_key)
    if match:
        return ord(match.group(1)) - ord("A") + 1
    _LOGGER.warning(
        "Unexpected relay key format '%s'; skipping",
        relay_key,
    )
    return None


def _relay_key_to_label(relay_key: str) -> str:
    """Convert a relay key like 'RelayA' to a display label.

    Args:
        relay_key: The relay key from the device.

    Returns:
        A human-readable label (e.g., "Relay A").

    """
    match = RELAY_KEY_RE.fullmatch(relay_key)
    if match:
        return f"Relay {match.group(1)}"
    _LOGGER.warning(
        "Unexpected relay key format '%s'; using raw key as label",
        relay_key,
    )
    return relay_key


def _parse_relay_state(
    relay_key: str,
    state: object,
    relay_type: int = DEFAULT_RELAY_TYPE,
) -> bool | None:
    """Parse a relay state value into a locked boolean.

    Args:
        relay_key: The relay key for logging context.
        state: The raw state value from the device.
        relay_type: 0 for NO (normal-open), 1 for NC (normal-closed).

    Returns:
        True if locked, False if unlocked, None if unknown.

    """
    if isinstance(state, int):
        return _parse_int_state(relay_key, state, relay_type)

    if isinstance(state, str):
        return _parse_str_state(relay_key, state)

    if isinstance(state, dict):
        inner = state.get("state")
        if isinstance(inner, int):
            return _parse_int_state(relay_key, inner, relay_type)
        if isinstance(inner, str):
            return _parse_str_state(relay_key, inner)
        _LOGGER.debug(
            "Unrecognized dict relay state for %s: %r",
            relay_key,
            state,
        )
        return None

    _LOGGER.debug(
        "Unexpected relay state type for %s: %r (type=%s)",
        relay_key,
        state,
        type(state).__name__,
    )
    return None


def _parse_int_state(
    relay_key: str,
    state: int,
    relay_type: int = DEFAULT_RELAY_TYPE,
) -> bool | None:
    """Parse an integer relay state value.

    Args:
        relay_key: The relay key for logging context.
        state: The integer state value.
        relay_type: 0 for NO (0=locked, 1=unlocked),
                    1 for NC (0=unlocked, 1=locked).

    Returns:
        True if locked, False if unlocked, None if unknown.

    """
    if state == 0:
        return relay_type != 1
    if state == 1:
        return relay_type == 1
    _LOGGER.debug(
        "Unexpected integer relay state %d for %s",
        state,
        relay_key,
    )
    return None


def _parse_str_state(relay_key: str, state: str) -> bool | None:
    """Parse a string relay state value.

    Args:
        relay_key: The relay key for logging context.
        state: The string state value.

    Returns:
        True if locked, False if unlocked, None if unknown.

    """
    if state in ("closed", "inactive"):
        return True
    if state in ("open", "active"):
        return False
    _LOGGER.debug(
        "Unrecognized relay state '%s' for %s",
        state,
        relay_key,
    )
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Akuvox lock entities from a config entry.

    Args:
        hass: The Home Assistant instance.
        entry: The config entry.
        async_add_entities: Callback to add entities.

    """
    coordinator: AkuvoxDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    if coordinator.data is None:
        _LOGGER.warning("No data available for %s", entry.title)
        return

    relay_status = coordinator.data.relay_status
    entities: list[AkuvoxLockEntity] = []

    for relay_key in relay_status:
        if _relay_key_to_number(relay_key) is None:
            continue
        entities.append(
            AkuvoxLockEntity(
                coordinator=coordinator,
                relay_key=relay_key,
            ),
        )

    async_add_entities(entities)


class AkuvoxLockEntity(AkuvoxEntity, LockEntity):
    """Represents an Akuvox relay as a lock entity."""

    def __init__(
        self,
        coordinator: AkuvoxDataUpdateCoordinator,
        relay_key: str,
    ) -> None:
        """Initialize the lock entity.

        Args:
            coordinator: The data update coordinator.
            relay_key: The relay key from the device (e.g., "RelayA").

        """
        super().__init__(coordinator)
        self._relay_key = relay_key
        relay_number = _relay_key_to_number(relay_key)
        if relay_number is None:
            msg = f"Invalid relay key: {relay_key}"
            raise ValueError(msg)
        self._relay_number = relay_number
        mac_clean = coordinator.data.device_info.mac_address.lower().replace(
            ":",
            "",
        )
        self._attr_unique_id = f"{mac_clean}_relay_{self._relay_number}"
        self._attr_has_entity_name = True
        # Use config-sourced name if available, fallback to label
        letter = chr(ord("A") + self._relay_number - 1)
        relay_cfg = coordinator.data.relay_configs.get(letter)
        config_name = (relay_cfg.name if relay_cfg else "").strip()
        self._attr_name = config_name if config_name else _relay_key_to_label(relay_key)
        self._optimistic_locked: bool | None = None
        self._delayed_refresh_cancel: CALLBACK_TYPE | None = None

    @property
    def is_locked(self) -> bool | None:
        """Return true if the relay is closed/inactive/0 (locked).

        Returns:
            True if locked (closed/inactive/0), False if unlocked
            (open/active/1), None if unknown.

        """
        if self._optimistic_locked is not None:
            return self._optimistic_locked

        relay_status = self.coordinator.data.relay_status
        state = relay_status.get(self._relay_key)

        if state is None:
            return None

        letter = chr(ord("A") + self._relay_number - 1)
        relay_cfg = self.coordinator.data.relay_configs.get(letter)
        relay_type = relay_cfg.relay_type if relay_cfg else DEFAULT_RELAY_TYPE

        return _parse_relay_state(self._relay_key, state, relay_type)

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the door (not supported — auto-locks via hardware).

        Raises:
            HomeAssistantError: Always, as locking is not supported.

        """
        raise HomeAssistantError(
            "Lock operation not supported; door auto-locks via hardware."
        )

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the door by triggering the relay.

        If trigger_relay fails, the optimistic state and timer are not
        touched.  Any pending timer from a previous successful unlock
        is left in place so it can still clear the earlier optimistic
        override as expected.

        Raises:
            HomeAssistantError: If the device communication fails.

        """
        letter = chr(ord("A") + self._relay_number - 1)
        relay_cfg = self.coordinator.data.relay_configs.get(letter)
        hold_delay = relay_cfg.hold_delay if relay_cfg else DEFAULT_HOLD_DELAY_SECONDS
        relay_type = relay_cfg.relay_type if relay_cfg else DEFAULT_RELAY_TYPE
        relay_mode = relay_cfg.relay_mode if relay_cfg else DEFAULT_RELAY_MODE
        try:
            await self.coordinator.device.trigger_relay(
                num=self._relay_number,
                delay=hold_delay,
                level=relay_type,
                mode=relay_mode,
            )
        except AkuvoxError as err:
            raise HomeAssistantError(
                f"Failed to unlock relay {self._relay_number}: {err}"
            ) from err
        self._optimistic_locked = False
        self.async_write_ha_state()
        self._schedule_delayed_refresh(hold_delay)

    def _schedule_delayed_refresh(self, hold_delay: int) -> None:
        """Schedule a coordinator refresh after the unlock delay expires.

        If called while a previous timer is pending (e.g. rapid unlock
        calls), the earlier timer is cancelled and only the latest
        unlock window is tracked.

        Args:
            hold_delay: The hold delay in seconds from relay config.

        """
        if self._delayed_refresh_cancel is not None:
            self._delayed_refresh_cancel()

        @callback
        def _refresh(_now: Any) -> None:
            """Kick off async refresh after unlock window expires."""
            self._delayed_refresh_cancel = None
            self.hass.async_create_task(
                self._async_finish_optimistic_unlock(),
            )

        self._delayed_refresh_cancel = async_call_later(
            self.hass,
            hold_delay + _RELAY_REFRESH_BUFFER_SECONDS,
            _refresh,
        )

    async def _async_finish_optimistic_unlock(self) -> None:
        """Refresh coordinator then clear optimistic state.

        The optimistic override is kept until the refresh completes so
        that any coordinator update triggered during the refresh does
        not write stale device state to Home Assistant. A finally
        block ensures the override is always cleared even if the
        refresh fails.
        """
        try:
            await self.coordinator.async_refresh()
        except Exception:  # noqa: BLE001
            _LOGGER.exception(
                "Error refreshing coordinator after optimistic unlock for relay %s",
                self._relay_key,
            )
        finally:
            self._optimistic_locked = None
            self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        """Cancel pending timers on entity removal."""
        if self._delayed_refresh_cancel is not None:
            self._delayed_refresh_cancel()
            self._delayed_refresh_cancel = None
        await super().async_will_remove_from_hass()

    async def list_schedules(self, **kwargs: Any) -> ServiceResponse:
        """Return all access schedules from the device.

        Args:
            **kwargs: Service call data (optional ``page`` key).

        Returns:
            Dict with ``schedules`` list of schedule dicts.

        Raises:
            HomeAssistantError: On device communication errors.
            ServiceValidationError: On validation errors.

        """
        page = kwargs.get("page")
        try:
            schedules = await self.coordinator.device.list_schedules(
                page=page,
            )
        except AkuvoxValidationError as err:
            raise ServiceValidationError(
                f"list_schedules: {err}",
            ) from err
        except AkuvoxError as err:
            raise HomeAssistantError(
                f"list_schedules failed: {err}",
            ) from err
        return cast(
            ServiceResponse,
            {"schedules": [dict(vars(s)) for s in schedules]},
        )

    async def list_users(self, **kwargs: Any) -> ServiceResponse:
        """Return all users from the device with plain-text credentials.

        Sensitive fields (``private_pin``, ``card_code``) are returned
        in plain text for automation consumption but masked in log
        output.

        Args:
            **kwargs: Service call data (optional ``page`` key).

        Returns:
            Dict with ``users`` list of user dicts.

        Raises:
            HomeAssistantError: On device communication errors.
            ServiceValidationError: On validation errors.

        """
        page = kwargs.get("page")
        try:
            users = await self.coordinator.device.list_users(
                page=page,
            )
        except AkuvoxValidationError as err:
            raise ServiceValidationError(
                f"list_users: {err}",
            ) from err
        except AkuvoxError as err:
            raise HomeAssistantError(
                f"list_users failed: {err}",
            ) from err

        user_dicts = [dict(vars(u)) for u in users]
        if _LOGGER.isEnabledFor(logging.DEBUG):
            masked = []
            for ud in user_dicts:
                masked_copy = dict(ud)
                if masked_copy.get("private_pin"):
                    masked_copy["private_pin"] = "****"
                if masked_copy.get("card_code"):
                    masked_copy["card_code"] = "****"
                masked.append(masked_copy)
            _LOGGER.debug("list_users result: %s", masked)
        return cast(ServiceResponse, {"users": user_dicts})
