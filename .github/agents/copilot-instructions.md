<!--
SPDX-FileCopyrightText: 2026 Andrew Grimberg <tykeal@bardicgrove.org>
SPDX-License-Identifier: Apache-2.0
-->

# local-akuvox Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-02-25

## Active Technologies
- Python ≥3.13.2 with homeassistant, pylocal-akuvox ≥0.2.0, voluptuous (002-device-config-discovery)

- Python ≥3.13.2 with pylocal-akuvox (001-akuvox-lock-integration)
- Home Assistant config entries (001-akuvox-lock-integration)

## Project Structure

```text
custom_components/akuvox/
tests/
```

## Commands

```bash
uv run pytest tests/ -x -q
uv run ruff check custom_components/ tests/
uv run ruff format --check custom_components/ tests/
uv run mypy custom_components/
```

## Code Style

Python ≥3.13.2: Follow standard HA integration conventions

## Recent Changes
- 002-device-config-discovery: Added Python ≥3.13.2 (HA 2026.2.0 requirement) + homeassistant, pylocal-akuvox ≥0.2.0, voluptuous

- 001-akuvox-lock-integration: Added Python ≥3.13.2 with
  pylocal-akuvox for device communication

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
