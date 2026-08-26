"""Platform for EARLY (Timeular) switch integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .util import is_bluetooth_entry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EARLY switches from a config entry."""
    # Switches require an API coordinator to start/stop tracking. This is
    # available for plain API config entries, and for Bluetooth entries that
    # were also configured with optional API credentials. The coordinator is
    # created by the sensor platform, which is forwarded before this one.
    if DOMAIN not in hass.data or config_entry.entry_id not in hass.data[DOMAIN]:
        _LOGGER.error("Coordinator not found for entry %s", config_entry.entry_id)
        return

    coordinator = hass.data[DOMAIN][config_entry.entry_id].get("coordinator")
    if not coordinator:
        # No coordinator was created for this entry - either no API
        # credentials were configured (e.g. a Bluetooth-only tracker), or
        # credentials were configured but the initial activity fetch failed
        # (see bluetooth_sensor.py). Either way, there is nothing to create
        # activity switches for.
        _LOGGER.debug(
            "No API coordinator for entry %s; skipping activity switches",
            config_entry.entry_id,
        )
        return

    # Fetch activities to create switches
    await coordinator.async_update()
    activities = coordinator.get_all_activities()

    if not activities:
        _LOGGER.warning("No activities found to create switches")
        return

    # Bluetooth entries are a new source of activity switches (previously
    # they were skipped entirely). Scope their unique_id by config entry so
    # they can't collide with a Cloud API entry for the same account - the
    # README documents running both simultaneously. Plain API entries keep
    # their original unique_id format for backwards compatibility with
    # existing entity registries.
    entry_id_for_unique_id = (
        config_entry.entry_id if is_bluetooth_entry(config_entry) else None
    )

    # Create a switch for each activity
    switches = [
        EarlyActivitySwitch(
            coordinator, activity_id, activity_name, entry_id_for_unique_id
        )
        for activity_id, activity_name in activities.items()
    ]

    async_add_entities(switches, True)


class EarlyActivitySwitch(SwitchEntity):
    """Representation of an EARLY activity switch."""

    def __init__(
        self,
        coordinator: Any,
        activity_id: str,
        activity_name: str,
        config_entry_id: str | None = None,
    ) -> None:
        """Initialize the switch."""
        self._coordinator = coordinator
        self._activity_id = activity_id
        self._activity_name = activity_name
        self._attr_name = f"EARLY {activity_name}"
        self._attr_unique_id = (
            f"{DOMAIN}_{config_entry_id}_activity_{activity_id}"
            if config_entry_id
            else f"{DOMAIN}_activity_{activity_id}"
        )
        self._attr_icon = "mdi:timer"

    @property
    def is_on(self) -> bool:
        """Return true if the activity is currently being tracked."""
        if not self._coordinator.tracking_data:
            return False

        current_tracking = self._coordinator.tracking_data.get("currentTracking")
        if not current_tracking:
            return False

        activity = current_tracking.get("activity", {})
        current_activity_id = activity.get("id")

        return current_activity_id == self._activity_id

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start tracking this activity."""
        try:
            await self._coordinator.start_tracking(self._activity_id)
            await self.async_update()
        except Exception as err:
            _LOGGER.error(
                "Error starting tracking for activity %s: %s",
                self._activity_name,
                err,
            )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop tracking this activity."""
        # Only stop if this activity is currently being tracked
        if self.is_on:
            try:
                await self._coordinator.stop_tracking()
                await self.async_update()
            except Exception as err:
                _LOGGER.error(
                    "Error stopping tracking for activity %s: %s",
                    self._activity_name,
                    err,
                )

    async def async_update(self) -> None:
        """Update the switch state."""
        await self._coordinator.async_update()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._coordinator.tracking_data is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return {
            "activity_id": self._activity_id,
            "activity_name": self._activity_name,
        }
