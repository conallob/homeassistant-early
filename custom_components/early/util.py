"""Shared helpers for the EARLY (Timeular) integration."""

from __future__ import annotations

from typing import Any

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


def get_current_activity_id(current_tracking: dict[str, Any]) -> str | None:
    """Resolve the currently tracked activity's id from a currentTracking object.

    EARLY's tracking endpoint has been observed returning this two
    different ways: a flat "activityId" field directly on
    currentTracking (confirmed via debug logs against a real account -
    e.g. {"id": 118278047, "activityId": "1752293", "startedAt": ...},
    with no "activity" key at all), and an older nested
    "activity": {"id": ...} object that this integration originally
    assumed. Neither shape reliably includes a "name" - see
    sensor.py's EarlyCurrentTrackingSensor, which always resolves the
    name separately via the coordinator's activities list. Checking both
    keeps this working regardless of which shape a given account/API
    version returns, since the flat form silently broke name resolution
    entirely (activity ended up None every time) rather than just
    missing the name.
    """
    activity_id = current_tracking.get("activityId")
    if activity_id:
        return activity_id
    return current_tracking.get("activity", {}).get("id")


def build_activity_display_name(activity_name: str, space_name: str | None) -> str:
    """Prefix an activity's name with its EARLY space (folder) name.

    EARLY lets the same activity name (e.g. "Administrivia") exist in
    multiple spaces - accounts that use one space per employer/context are
    a common case (see README). Without the space name, switches and the
    current-activity sensor can't distinguish "Administrivia" in one space
    from "Administrivia" in another. Falls back to the bare activity name
    when space_name is unavailable (e.g. the /space API call failed, or an
    activity has no resolvable spaceId), rather than showing a raw id or a
    broken-looking prefix.
    """
    if not space_name:
        return activity_name
    return f"{space_name}: {activity_name}"
