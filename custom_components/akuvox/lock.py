# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Lock platform for the Akuvox integration."""

from __future__ import annotations

import datetime as dt
import logging
import re
from typing import Any, cast

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, ServiceResponse, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later
from pylocal_akuvox import (
    AccessSchedule,
    AkuvoxError,
    AkuvoxValidationError,
)

from .const import (
    DAY_NAME_TO_DIGIT,
    DEFAULT_HOLD_DELAY_SECONDS,
    DEFAULT_RELAY_MODE,
    DEFAULT_RELAY_TYPE,
    DOMAIN,
    EVENT_SCHEDULE_CHANGED,
    EVENT_USER_CHANGED,
    RELAY_KEY_RE,
)
from .coordinator import AkuvoxDataUpdateCoordinator
from .entity import AkuvoxEntity

_LOGGER = logging.getLogger(__name__)

# Extra seconds added to the unlock delay before polling the device,
# giving the relay time to re-lock after the window expires.
_RELAY_REFRESH_BUFFER_SECONDS = 1

# Required fields per schedule_type (0=date-range, 1=weekly, 2=daily)
_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "0": ("week", "date_start", "date_end"),
    "1": ("week",),
    "2": (),
}

# Pattern for schedule_relay: one or more "<number>-<number>;" pairs
_SCHEDULE_RELAY_RE: re.Pattern[str] = re.compile(r"^([0-9]+-[0-9]+;)+\Z")

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

    @staticmethod
    def _convert_week(days: list[str]) -> str:
        """Convert day-name list to device digit string.

        Args:
            days: List of day abbreviations (e.g. ["mon", "fri"]).

        Returns:
            Sorted digit string for the device (e.g. "15").

        """
        digits = sorted(DAY_NAME_TO_DIGIT[d] for d in days)
        return "".join(digits)

    @staticmethod
    def _convert_date(value: dt.date) -> str:
        """Convert a date object to YYYYMMDD string.

        Args:
            value: The date to convert.

        Returns:
            Date formatted as YYYYMMDD for the device.

        """
        return value.strftime("%Y%m%d")

    @staticmethod
    def _convert_time(value: dt.time) -> str:
        """Convert a time object to HH:MM string.

        Args:
            value: The time to convert.

        Returns:
            Time formatted as HH:MM for the device.

        """
        return value.strftime("%H:%M")

    def _check_required_schedule_fields(
        self,
        schedule_type: str,
        **kwargs: Any,
    ) -> None:
        """Validate required fields are present for the schedule type.

        Type 0 (date range) requires week, date_start, date_end.
        Type 1 (weekly) requires week.
        Type 2 (daily) has no extra required fields.
        time_start and time_end are enforced by the schema.

        Args:
            schedule_type: The schedule type ("0", "1", "2").
            **kwargs: Service call data.

        Raises:
            ServiceValidationError: If a required field is missing.

        """
        for field in _REQUIRED_FIELDS.get(schedule_type, ()):
            if kwargs.get(field) is None:
                raise ServiceValidationError(
                    f"Field '{field}' is required for schedule type {schedule_type}",
                )

    async def add_schedule(self, **kwargs: Any) -> None:
        """Create a new access schedule on the device.

        Converts user-friendly inputs (day names, date/time
        objects) to the device's expected string formats before
        forwarding the call.

        Args:
            **kwargs: Service call data with schedule fields.

        Raises:
            ServiceValidationError: On input validation errors.
            HomeAssistantError: On device communication errors.

        """
        stype = kwargs["schedule_type"]
        self._check_required_schedule_fields(
            stype, **{k: v for k, v in kwargs.items() if k != "schedule_type"}
        )

        week_list: list[str] | None = kwargs.get("week")
        week_str = self._convert_week(week_list) if week_list else None

        date_start: dt.date | None = kwargs.get("date_start")
        date_end: dt.date | None = kwargs.get("date_end")
        time_start: dt.time = kwargs["time_start"]
        time_end: dt.time = kwargs["time_end"]

        try:
            await self.coordinator.device.add_schedule(
                schedule_type=stype,
                name=kwargs.get("name"),
                week=week_str,
                daily=None,
                date_start=(self._convert_date(date_start) if date_start else None),
                date_end=(self._convert_date(date_end) if date_end else None),
                time_start=self._convert_time(time_start),
                time_end=self._convert_time(time_end),
            )
        except AkuvoxValidationError as err:
            raise ServiceValidationError(
                f"add_schedule: {err}",
            ) from err
        except AkuvoxError as err:
            raise HomeAssistantError(
                f"add_schedule failed: {err}",
            ) from err
        event_data: dict[str, str] = {"action": "add"}
        config_entry = self.coordinator.config_entry
        if config_entry is not None and hasattr(config_entry, "entry_id"):
            event_data["config_entry_id"] = config_entry.entry_id
        self.hass.bus.async_fire(EVENT_SCHEDULE_CHANGED, event_data)

    async def _fetch_local_schedule(
        self,
        schedule_id: str,
        *,
        action: str = "modify",
    ) -> AccessSchedule:
        """Fetch a schedule by ID and verify it is locally managed.

        Args:
            schedule_id: The ID of the schedule to look up.
            action: Action label for error messages.

        Returns:
            The matching AccessSchedule.

        Raises:
            ServiceValidationError: If schedule is cloud-provisioned.
            HomeAssistantError: If schedule not found or fetch fails.

        """
        try:
            schedules = await self.coordinator.device.list_schedules(
                page=None,
            )
        except AkuvoxValidationError as err:
            raise ServiceValidationError(
                f"{action}_schedule: {err}",
            ) from err
        except AkuvoxError as err:
            raise HomeAssistantError(
                f"{action}_schedule: failed to fetch schedules: {err}",
            ) from err

        target = None
        for s in schedules:
            if s.id == schedule_id:
                target = s
                break

        if target is None:
            raise HomeAssistantError(
                f"Schedule '{schedule_id}' not found",
            )

        if target.source_type == "2":
            raise ServiceValidationError(
                f"Cannot {action} cloud-provisioned schedule",
            )

        return target

    async def modify_schedule(self, **kwargs: Any) -> None:
        """Modify an existing access schedule on the device.

        Fetches the current schedule list to verify the schedule
        exists and is not cloud-provisioned before forwarding the
        update.

        Args:
            **kwargs: Service call data (``id`` required, other
                schedule fields optional).

        Raises:
            ServiceValidationError: If schedule is cloud-provisioned
                or input validation fails.
            HomeAssistantError: If schedule not found or device error.

        """
        schedule_id: str = kwargs["id"]
        await self._fetch_local_schedule(schedule_id)

        # Validate type-specific fields when schedule_type changes
        stype: str | None = kwargs.get("schedule_type")
        if stype is not None:
            self._check_required_schedule_fields(
                stype,
                **{k: v for k, v in kwargs.items() if k != "schedule_type"},
            )

        # Convert optional fields
        week_list: list[str] | None = kwargs.get("week")
        week_str = self._convert_week(week_list) if week_list else None

        date_start: dt.date | None = kwargs.get("date_start")
        date_end: dt.date | None = kwargs.get("date_end")
        time_start: dt.time | None = kwargs.get("time_start")
        time_end: dt.time | None = kwargs.get("time_end")

        try:
            await self.coordinator.device.modify_schedule(
                id=schedule_id,
                schedule_type=kwargs.get("schedule_type"),
                name=kwargs.get("name"),
                week=week_str,
                daily=None,
                date_start=(self._convert_date(date_start) if date_start else None),
                date_end=(self._convert_date(date_end) if date_end else None),
                time_start=(self._convert_time(time_start) if time_start else None),
                time_end=(self._convert_time(time_end) if time_end else None),
            )
        except AkuvoxValidationError as err:
            raise ServiceValidationError(
                f"modify_schedule: {err}",
            ) from err
        except AkuvoxError as err:
            raise HomeAssistantError(
                f"modify_schedule failed: {err}",
            ) from err

        event_data: dict[str, str] = {
            "action": "modify",
            "schedule_id": schedule_id,
        }
        config_entry = self.coordinator.config_entry
        if config_entry is not None and hasattr(config_entry, "entry_id"):
            event_data["config_entry_id"] = config_entry.entry_id
        self.hass.bus.async_fire(EVENT_SCHEDULE_CHANGED, event_data)

    async def delete_schedule(self, **kwargs: Any) -> None:
        """Delete an access schedule from the device.

        Fetches the schedule list to verify the target exists and
        is not cloud-provisioned, deletes it, then checks for
        orphaned user-schedule assignments.

        Args:
            **kwargs: Service call data (``id`` required).

        Raises:
            ServiceValidationError: If schedule is cloud-provisioned.
            HomeAssistantError: If schedule not found or device error.

        """
        schedule_id: str = kwargs["id"]
        await self._fetch_local_schedule(schedule_id, action="delete")

        try:
            await self.coordinator.device.delete_schedule(id=schedule_id)
        except AkuvoxValidationError as err:
            raise ServiceValidationError(
                f"delete_schedule: {err}",
            ) from err
        except AkuvoxError as err:
            raise HomeAssistantError(
                f"delete_schedule failed: {err}",
            ) from err

        # Check for orphaned user-schedule assignments
        try:
            users = await self.coordinator.device.list_users(page=None)
            for user in users:
                relay = getattr(user, "schedule_relay", "") or ""
                for pair in relay.split(";"):
                    if pair and pair.split("-")[0] == schedule_id:
                        _LOGGER.warning(
                            "Orphaned schedule-relay assignment: "
                            "user '%s' (id=%s) still references "
                            "deleted schedule %s",
                            user.name,
                            user.id,
                            schedule_id,
                        )
                        break
        except AkuvoxError:
            _LOGGER.debug(
                "Could not check for orphaned assignments after deleting schedule %s",
                schedule_id,
            )

        event_data: dict[str, str] = {
            "action": "delete",
            "schedule_id": schedule_id,
        }
        config_entry = self.coordinator.config_entry
        if config_entry is not None and hasattr(config_entry, "entry_id"):
            event_data["config_entry_id"] = config_entry.entry_id
        self.hass.bus.async_fire(EVENT_SCHEDULE_CHANGED, event_data)

    def _validate_schedule_relay(self, schedule_relay: str) -> None:
        """Validate schedule_relay format matches ``<N>-<N>;`` pairs.

        Args:
            schedule_relay: The schedule-relay string to validate.

        Raises:
            ServiceValidationError: If format is invalid.

        """
        if not _SCHEDULE_RELAY_RE.match(schedule_relay):
            raise ServiceValidationError(
                "Invalid schedule_relay format; "
                "expected '<schedule_id>-<relay_id>;' pairs",
            )

    def _validate_pin(self, pin: str | None) -> None:
        """Validate private_pin is 4-8 digits if provided.

        Args:
            pin: The PIN string to validate, or None.

        Raises:
            ServiceValidationError: If PIN is not 4-8 decimal digits.

        """
        if pin is not None and (len(pin) < 4 or len(pin) > 8 or not pin.isdigit()):
            raise ServiceValidationError(
                "PIN must be 4-8 digits",
            )

    async def _check_cloud_schedules(
        self,
        schedule_relay: str,
    ) -> None:
        """Verify no referenced schedules are cloud-provisioned.

        Args:
            schedule_relay: The schedule-relay string to check.

        Raises:
            ServiceValidationError: If any referenced schedule is
                cloud-provisioned or does not exist on the device.
            HomeAssistantError: If schedule list fetch fails.

        """
        schedule_ids = {
            pair.split("-")[0] for pair in schedule_relay.rstrip(";").split(";") if pair
        }
        try:
            schedules = await self.coordinator.device.list_schedules(
                page=None,
            )
        except AkuvoxError as err:
            raise HomeAssistantError(
                f"Failed to verify schedules: {err}",
            ) from err

        schedule_map = {s.id: s for s in schedules}
        for sid in schedule_ids:
            sched = schedule_map.get(sid)
            if sched is None:
                # ServiceValidationError (not HomeAssistantError) because
                # the caller supplied an invalid schedule_relay reference —
                # this is an input-validation failure, not a device error.
                raise ServiceValidationError(
                    f"Schedule '{sid}' not found on device",
                )
            if sched.source_type == "2":
                raise ServiceValidationError(
                    "Cannot assign cloud-provisioned schedule",
                )

    async def add_user(self, **kwargs: Any) -> None:
        """Create a new user on the device.

        Validates input fields, checks that referenced schedules
        are not cloud-provisioned, then forwards the call.

        Args:
            **kwargs: Service call data with user fields.

        Raises:
            ServiceValidationError: On input validation errors.
            HomeAssistantError: On device communication errors.

        """
        schedule_relay: str = kwargs["schedule_relay"]
        self._validate_schedule_relay(schedule_relay)
        self._validate_pin(kwargs.get("private_pin"))
        await self._check_cloud_schedules(schedule_relay)

        try:
            await self.coordinator.device.add_user(
                name=kwargs["name"],
                user_id=kwargs["user_id"],
                schedule_relay=schedule_relay,
                lift_floor_num=kwargs["lift_floor_num"],
                web_relay=kwargs.get("web_relay"),
                private_pin=kwargs.get("private_pin"),
                card_code=kwargs.get("card_code"),
            )
        except AkuvoxValidationError as err:
            raise ServiceValidationError(
                f"add_user: {err}",
            ) from err
        except AkuvoxError as err:
            raise HomeAssistantError(
                f"add_user failed: {err}",
            ) from err

        event_data: dict[str, str] = {"action": "add"}
        config_entry = self.coordinator.config_entry
        if config_entry is not None and hasattr(config_entry, "entry_id"):
            event_data["config_entry_id"] = config_entry.entry_id
        self.hass.bus.async_fire(EVENT_USER_CHANGED, event_data)
