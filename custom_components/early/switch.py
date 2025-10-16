"""Platform for EARLY (Timeular) switch integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_API_SECRET, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EARLY switches from a config entry."""
    # Only set up switches for API configurations, not Bluetooth devices
    if "address" in config_entry.data:
        return

    api_key = config_entry.data.get(CONF_API_KEY)
    api_secret = config_entry.data.get(CONF_API_SECRET)

    if not api_key or not api_secret:
        _LOGGER.error("API key or secret missing from config entry")
        return

    # Get the coordinator from the sensor platform
    # We need to share the coordinator between sensor and switch platforms
    if DOMAIN not in hass.data or config_entry.entry_id not in hass.data[DOMAIN]:
        _LOGGER.error("Coordinator not found for entry %s", config_entry.entry_id)
        return

    coordinator = hass.data[DOMAIN][config_entry.entry_id].get("coordinator")
    if not coordinator:
        _LOGGER.error("Coordinator not initialized for entry %s", config_entry.entry_id)
        return

    # Fetch activities to create switches
    await coordinator.async_update()
    activities = coordinator.get_all_activities()

    if not activities:
        _LOGGER.warning("No activities found to create switches")
        return

    # Create a switch for each activity
    switches = [
        EarlyActivitySwitch(coordinator, activity_id, activity_name)
        for activity_id, activity_name in activities.items()
    ]

    async_add_entities(switches, True)


class EarlyActivitySwitch(SwitchEntity):
    """Representation of an EARLY activity switch."""

    def __init__(
        self, coordinator: Any, activity_id: str, activity_name: str
    ) -> None:
        """Initialize the switch."""
        self._coordinator = coordinator
        self._activity_id = activity_id
        self._activity_name = activity_name
        self._attr_name = f"EARLY {activity_name}"
        self._attr_unique_id = f"{DOMAIN}_activity_{activity_id}"
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
