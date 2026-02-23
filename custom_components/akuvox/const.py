# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Constants for the Akuvox integration."""

from typing import Final

DOMAIN: Final = "akuvox"
PLATFORMS: Final = ["lock"]

# Config keys
CONF_HOST: Final = "host"
CONF_USE_SSL: Final = "use_ssl"
CONF_VERIFY_SSL: Final = "verify_ssl"
CONF_AUTH_METHOD: Final = "auth_method"
CONF_USERNAME: Final = "username"
CONF_PASSWORD: Final = "password"  # noqa: S105

# Auth mode constants
AUTH_NONE: Final = "none"
AUTH_BASIC: Final = "basic"
AUTH_DIGEST: Final = "digest"

# Defaults
DEFAULT_SCAN_INTERVAL: Final = 30
