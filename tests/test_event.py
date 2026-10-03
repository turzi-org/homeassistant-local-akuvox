# SPDX-FileCopyrightText: 2026 Turzi
# SPDX-License-Identifier: Apache-2.0

"""Tests for the Akuvox access event entity."""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.local_akuvox.event import AkuvoxAccessEvent


def test_access_event_is_not_a_doorbell() -> None:
    """Access events must not claim the doorbell device class.

    Home Assistant requires a doorbell event entity to support the
    "ring" event type and warns otherwise; credential events never ring.
    """
    entity = AkuvoxAccessEvent(coordinator=MagicMock(), mac_clean="0c1105aabbcc")

    assert entity.device_class is None
    assert "ring" not in entity.event_types
