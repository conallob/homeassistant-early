"""Shared helpers for the EARLY (Timeular) integration."""

from __future__ import annotations

from homeassistant.config_entries import SOURCE_BLUETOOTH, ConfigEntry


def is_bluetooth_entry(config_entry: ConfigEntry) -> bool:
    """Return True if this config entry represents a Bluetooth tracker.

    Bluetooth entries are always created via the discovery flow
    (config_flow.py's async_step_bluetooth), so HA stamps them with
    source=SOURCE_BLUETOOTH at creation time and that never changes -
    this is a more robust discriminator than checking for an "address"
    key in config_entry.data, which would silently misroute any future
    Cloud API entry that happened to also store an "address" field.
    """
    return config_entry.source == SOURCE_BLUETOOTH
