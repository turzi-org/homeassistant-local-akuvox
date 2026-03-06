<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Configuration

## Adding the Integration

1. Go to **Settings** → **Devices & Services** → **Add Integration**.
2. Search for **Local Akuvox**.
3. Follow the setup wizard:

| Step                   | Description                                     |
| ---------------------- | ----------------------------------------------- |
| **Device Connection**  | Enter the IP/hostname and whether to use SSL.   |
| **SSL Options**        | Choose whether to verify the SSL certificate.   |
| **Authentication**     | Select: None / AllowList, Basic, or Digest.     |
| **Credentials**        | Enter username and password (if required).      |
| **Webhook Events**     | Optionally enable webhook event delivery.       |

> **Tip:** Make sure you have completed
> [Device Setup](Device-Setup) before starting the wizard. You will
> need the IP address, authentication mode, and credentials from your
> device's HTTP API configuration.

## Setup Wizard Details

### Device Connection

Enter the IP address or hostname of your Akuvox device. Enable
**Use SSL** if the device is configured with HTTPS.

### SSL Options

This step only appears when SSL is enabled. Choose whether to
verify the device's SSL certificate. Disable verification if the
device uses a self-signed certificate.

### Authentication

Select the authentication method that matches your device's HTTP
API configuration:

- **None / AllowList** — No credentials needed. The device either
  has no authentication or uses IP-based allowlisting.
- **Basic** — HTTP Basic authentication with username and password.
- **Digest** — HTTP Digest authentication with username and
  password (more secure than Basic).

### Credentials

This step only appears when Basic or Digest authentication is
selected. Enter the username and password configured on the device.

### Webhook Events

Optionally enable webhook event delivery. When enabled, the
integration configures the device to send real-time event
notifications to Home Assistant. See
[Webhook Events](Webhook-Events) for details.

## Reconfiguration

Go to **Settings** → **Devices & Services** → **Local Akuvox** →
**Configure** to update connection settings, authentication, or
webhook configuration at any time.

## Entities Created

### Lock Entities

One `lock` entity is created for each relay on the device (e.g.,
Relay A, Relay B).

| Action     | Description                                              |
| ---------- | -------------------------------------------------------- |
| **Unlock** | Triggers the relay for the configured hold duration.     |
| **Lock**   | Not supported — relay closure depends on device config.  |

Entity names are derived from the device configuration. If a relay
has a custom name configured on the device, that name is used.
