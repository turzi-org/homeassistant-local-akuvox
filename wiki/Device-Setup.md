<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Device Setup

Before adding this integration to Home Assistant, you must enable and
configure the HTTP API on your Akuvox device. This page walks through
the required device-side setup.

> **Official documentation:**
> [Akuvox Knowledge Base — Configure HTTP API](https://knowledge.akuvox.com/docs/configure-http-api)

## Prerequisites

- An Akuvox intercom or access control device (e.g., E21V, R29, or
  similar) connected to your local network.
- The device's IP address (check your router's DHCP client list or
  the device's display).
- Admin access to the device's web interface.

## Step 1 — Access the Device Web Interface

1. Open a web browser on a computer connected to the same network as
   the device.
2. Enter the device's IP address in the address bar
   (e.g., `http://192.168.1.100`).
3. Log in with the admin credentials. The factory defaults are
   typically `admin` / `admin`.

> **Tip:** Change the default password immediately if you have not
> already done so. An unsecured device is a security risk.

## Step 2 — Enable the HTTP API

1. Navigate to **Intercom** → **HTTP API** (the exact menu path may
   vary slightly by model and firmware version).
2. Set the **HTTP API** toggle to **Enabled**.

Without this step the device will reject all API requests with
HTTP 403 Forbidden, and the integration will not be able to
communicate with it.

## Step 3 — Choose an Authentication Method

On the same HTTP API settings page you will find an
**Authentication Mode** selector. The integration supports the
following modes:

| Mode               | Description                                |
| ------------------ | ------------------------------------------ |
| **None/AllowList** | No credentials required. Optionally limit  |
|                    | access by IP address (see Step 4).         |
| **Basic**          | Username and password sent Base64-encoded. |
| **Digest**         | Username and password with MD5 hashing.    |

Choose the mode that fits your security requirements:

- **None / AllowList** is the simplest option for an isolated LAN.
  Pair it with IP-based allowlisting for basic protection.
- **Basic** is easy to set up but transmits credentials in a
  reversible encoding. Use SSL/TLS if possible.
- **Digest** is more secure than Basic and is recommended when SSL
  is not available.

> **Important:** Remember the mode, username, and password you
> configure here — you will enter the same values in the Home
> Assistant integration setup wizard.

## Step 4 — Configure the IP AllowList (Optional)

If you selected **None / AllowList** or want an extra layer of
protection regardless of mode:

1. Still on the HTTP API settings page, find the **AllowList** (or
   **Whitelist**) section.
2. Add the IP address of your Home Assistant instance.
3. Save the settings.

When an allowlist is configured, the device only accepts API requests
from the listed IP addresses. Requests from all other addresses are
refused.

> **Note:** Up to 5 IP addresses can typically be added to the
> allowlist. Check your device's documentation for the exact limit.

## Step 5 — Enable SSL/TLS (Recommended)

If your device supports HTTPS:

1. Navigate to the SSL/TLS or certificate settings in the device's
   web interface.
2. Enable HTTPS and install a certificate if required.
3. Note whether the device uses a self-signed certificate — you will
   need this information during integration setup (the wizard will
   ask whether to verify the SSL certificate).

Using HTTPS is especially important when:

- The device is on a shared or untrusted network.
- You use **Basic** authentication (credentials are only
  Base64-encoded, not encrypted).
- You plan to enable webhooks (PIN codes appear in webhook query
  strings).

## Step 6 — Note Connection Details

Before switching to Home Assistant, record the following:

| Detail               | Example                            |
| -------------------- | ---------------------------------- |
| Device IP / hostname | `192.168.1.100`                    |
| SSL enabled?         | Yes / No                           |
| Auth mode            | None / AllowList, Basic, or Digest |
| Username             | *(if Basic or Digest)*             |
| Password             | *(if Basic or Digest)*             |

You will enter these in the integration's configuration wizard.

## Next Steps

- [Install the integration](Installation) in Home Assistant.
- [Configure the integration](Configuration) using the setup wizard.
- Optionally [enable webhooks](Webhook-Events) for real-time event
  notifications.

## Reference

- [Akuvox Knowledge Base](https://knowledge.akuvox.com/docs)
- [Configure HTTP API](https://knowledge.akuvox.com/docs/configure-http-api)
- [Integration with Third Party Devices](https://knowledge.akuvox.com/docs/integration-with-third-party-device-14)
