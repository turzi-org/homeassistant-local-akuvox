# SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
# SPDX-License-Identifier: Apache-2.0

"""Constants for the Akuvox integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from pylocal_akuvox import AuthMethod

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

# Lazy import: AuthMethod lives in pylocal_akuvox and is imported at
# runtime to avoid a top-level heavy dependency in const.py.  The map
# is built once on first call and cached.
_AUTH_METHOD_MAP: dict[str, AuthMethod] | None = None


def get_auth_method_map() -> dict[str, AuthMethod]:
    """Return the AUTH_METHOD_MAP, importing AuthMethod on first use.

    Returns:
        Mapping from string auth constants to AuthMethod enum values.

    """
    global _AUTH_METHOD_MAP  # noqa: PLW0603
    if _AUTH_METHOD_MAP is None:
        from pylocal_akuvox import AuthMethod as _AuthMethod

        _AUTH_METHOD_MAP = {
            AUTH_NONE: _AuthMethod.NONE,
            AUTH_BASIC: _AuthMethod.BASIC,
            AUTH_DIGEST: _AuthMethod.DIGEST,
        }
    return _AUTH_METHOD_MAP
