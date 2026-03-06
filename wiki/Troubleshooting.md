<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# Troubleshooting

## Cannot Connect to Device

- Verify the device IP address is correct and reachable from
  your Home Assistant host.
- Check that the HTTP API is enabled on the device (see
  [Device Setup](Device-Setup)).
- If using authentication, confirm the credentials match the
  device configuration exactly.
- If using SSL, try disabling certificate verification to rule
  out certificate issues.

## Webhook Events Not Received

- Ensure your Home Assistant instance is accessible from the
  device's network.
- Check that webhooks are enabled in the integration options
  (see [Configuration](Configuration)).
- Verify the device's action URL points to the correct
  Home Assistant webhook URL.
- Use HTTPS/TLS for webhook URLs. `valid_code_entered` webhooks
  include the entered PIN in the query string; using HTTP
  transmits it in plaintext. Only use HTTP on a trusted network
  for testing.

## Lock Entity Shows Unknown State

- The device may not have responded to the initial status poll.
  Wait for the next polling interval (30 seconds).
- Check Home Assistant logs for connection errors.

## Cloud-Provisioned Users or Schedules

Users and schedules provisioned via Akuvox cloud services cannot
be modified or deleted through this integration. The integration
returns a clear error message when this is attempted.

## Enabling Debug Logging

Add the following to your `configuration.yaml` to enable debug
logging for the integration:

```yaml
logger:
  default: info
  logs:
    custom_components.local_akuvox: debug
```

Restart Home Assistant and reproduce the issue. Debug logs will
appear in **Settings** → **System** → **Logs**.
