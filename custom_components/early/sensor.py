"""Platform for EARLY (Timeular) sensor integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

import requests

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import Throttle

from .const import (
    CONF_API_SECRET,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    API_SIGN_IN_ENDPOINT,
    API_TRACKING_ENDPOINT,
    API_ACTIVITIES_ENDPOINT,
    ATTR_ACTIVITY_ID,
    ATTR_ACTIVITY_NAME,
    ATTR_STARTED_AT,
    ATTR_NOTE,
)

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=DEFAULT_SCAN_INTERVAL)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EARLY sensor from a config entry."""
    # Check if this is a Bluetooth device or API configuration
    if "address" in config_entry.data:
        # This is a Bluetooth device - delegate to bluetooth_sensor
        from .bluetooth_sensor import async_setup_bluetooth_entry
        await async_setup_bluetooth_entry(hass, config_entry, async_add_entities)
        return

    # This is an API configuration
    api_key = config_entry.data.get(CONF_API_KEY)
    api_secret = config_entry.data.get(CONF_API_SECRET)

    if not api_key or not api_secret:
        _LOGGER.error("API key or secret missing from config entry")
        return

    # Create the coordinator
    coordinator = EarlyAPICoordinator(hass, api_key, api_secret)

    # Store the coordinator in hass.data for use by switch platform
    hass.data[DOMAIN][config_entry.entry_id]["coordinator"] = coordinator

    # Fetch initial data
    await coordinator.async_update()

    # Create sensors
    async_add_entities(
        [
            EarlyCurrentTrackingSensor(coordinator),
        ],
        True,
    )


class EarlyAPICoordinator:
    """Class to manage fetching EARLY data from the API."""

    def __init__(self, hass: HomeAssistant, api_key: str, api_secret: str) -> None:
        """Initialize the coordinator."""
        self.hass = hass
        self._api_key = api_key
        self._api_secret = api_secret
        self._token: str | None = None
        self._tracking_data: dict[str, Any] | None = None
        self._activities: dict[str, str] = {}

    async def _get_token(self) -> str:
        """Get authentication token from EARLY API."""
        if self._token:
            return self._token

        try:
            response = await self.hass.async_add_executor_job(
                lambda: requests.post(
                    API_SIGN_IN_ENDPOINT,
                    json={"apiKey": self._api_key, "apiSecret": self._api_secret},
                    timeout=10,
                )
            )
            response.raise_for_status()
            data = response.json()
            self._token = data.get("token")
            _LOGGER.debug("Successfully obtained EARLY API token")
            return self._token
        except requests.exceptions.RequestException as err:
            _LOGGER.error("Error getting EARLY API token: %s", err)
            raise

    async def _fetch_activities(self) -> None:
        """Fetch activities list to map activity IDs to names."""
        try:
            token = await self._get_token()
            headers = {"Authorization": f"Bearer {token}"}

            response = await self.hass.async_add_executor_job(
                lambda: requests.get(
                    API_ACTIVITIES_ENDPOINT,
                    headers=headers,
                    timeout=10,
                )
            )
            response.raise_for_status()
            data = response.json()

            # Build a mapping of activity ID to activity name
            if "activities" in data:
                self._activities = {
                    activity["id"]: activity.get("name", "Unknown Activity")
                    for activity in data["activities"]
                }
                _LOGGER.debug("Fetched %d activities", len(self._activities))

        except requests.exceptions.RequestException as err:
            _LOGGER.error("Error fetching EARLY activities: %s", err)

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self) -> None:
        """Fetch data from EARLY API."""
        try:
            token = await self._get_token()
            headers = {"Authorization": f"Bearer {token}"}

            # Fetch activities if we don't have them yet
            if not self._activities:
                await self._fetch_activities()

            # Fetch current tracking status
            response = await self.hass.async_add_executor_job(
                lambda: requests.get(
                    API_TRACKING_ENDPOINT,
                    headers=headers,
                    timeout=10,
                )
            )

            if response.status_code == 401:
                # Token expired, reset and try again
                _LOGGER.debug("Token expired, resetting")
                self._token = None
                token = await self._get_token()
                headers = {"Authorization": f"Bearer {token}"}
                response = await self.hass.async_add_executor_job(
                    lambda: requests.get(
                        API_TRACKING_ENDPOINT,
                        headers=headers,
                        timeout=10,
                    )
                )

            response.raise_for_status()
            self._tracking_data = response.json()
            _LOGGER.debug("Updated EARLY tracking data: %s", self._tracking_data)

        except requests.exceptions.RequestException as err:
            _LOGGER.error("Error fetching EARLY tracking data: %s", err)
            self._tracking_data = None

    @property
    def tracking_data(self) -> dict[str, Any] | None:
        """Return the current tracking data."""
        return self._tracking_data

    def get_activity_name(self, activity_id: str) -> str:
        """Get activity name from activity ID."""
        return self._activities.get(activity_id, "Unknown Activity")

    def get_all_activities(self) -> dict[str, str]:
        """Return all activities as a dict of {id: name}."""
        return self._activities

    async def start_tracking(self, activity_id: str) -> None:
        """Start tracking a specific activity."""
        try:
            token = await self._get_token()
            headers = {"Authorization": f"Bearer {token}"}

            # Build the tracking start endpoint
            endpoint = f"{API_TRACKING_ENDPOINT}/{activity_id}/start"

            response = await self.hass.async_add_executor_job(
                lambda: requests.post(
                    endpoint,
                    headers=headers,
                    json={},
                    timeout=10,
                )
            )

            if response.status_code == 401:
                # Token expired, reset and try again
                self._token = None
                token = await self._get_token()
                headers = {"Authorization": f"Bearer {token}"}
                response = await self.hass.async_add_executor_job(
                    lambda: requests.post(
                        endpoint,
                        headers=headers,
                        json={},
                        timeout=10,
                    )
                )

            response.raise_for_status()
            _LOGGER.debug("Started tracking activity %s", activity_id)

            # Update tracking data immediately
            await self.async_update()

        except requests.exceptions.RequestException as err:
            _LOGGER.error("Error starting tracking for activity %s: %s", activity_id, err)
            raise

    async def stop_tracking(self) -> None:
        """Stop the current tracking."""
        try:
            token = await self._get_token()
            headers = {"Authorization": f"Bearer {token}"}

            # Build the tracking stop endpoint
            endpoint = f"{API_TRACKING_ENDPOINT}/stop"

            response = await self.hass.async_add_executor_job(
                lambda: requests.post(
                    endpoint,
                    headers=headers,
                    json={},
                    timeout=10,
                )
            )

            if response.status_code == 401:
                # Token expired, reset and try again
                self._token = None
                token = await self._get_token()
                headers = {"Authorization": f"Bearer {token}"}
                response = await self.hass.async_add_executor_job(
                    lambda: requests.post(
                        endpoint,
                        headers=headers,
                        json={},
                        timeout=10,
                    )
                )

            response.raise_for_status()
            _LOGGER.debug("Stopped tracking")

            # Update tracking data immediately
            await self.async_update()

        except requests.exceptions.RequestException as err:
            _LOGGER.error("Error stopping tracking: %s", err)
            raise


class EarlyCurrentTrackingSensor(SensorEntity):
    """Representation of an EARLY current tracking sensor."""

    def __init__(self, coordinator: EarlyAPICoordinator) -> None:
        """Initialize the sensor."""
        self._coordinator = coordinator
        self._attr_name = "EARLY Current Activity"
        self._attr_unique_id = f"{DOMAIN}_current_tracking"
        self._attr_icon = "mdi:clock-outline"

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        if not self._coordinator.tracking_data:
            return "unavailable"

        current_tracking = self._coordinator.tracking_data.get("currentTracking")
        if not current_tracking:
            return "idle"

        activity = current_tracking.get("activity", {})
        activity_name = activity.get("name")

        if activity_name:
            return activity_name

        return "tracking"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if not self._coordinator.tracking_data:
            return {}

        current_tracking = self._coordinator.tracking_data.get("currentTracking")
        if not current_tracking:
            return {"status": "idle"}

        activity = current_tracking.get("activity", {})
        attributes = {
            ATTR_ACTIVITY_ID: activity.get("id"),
            ATTR_ACTIVITY_NAME: activity.get("name"),
            ATTR_STARTED_AT: current_tracking.get("startedAt"),
            ATTR_NOTE: current_tracking.get("note", {}).get("text"),
        }

        return {k: v for k, v in attributes.items() if v is not None}

    async def async_update(self) -> None:
        """Update the sensor."""
        await self._coordinator.async_update()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._coordinator.tracking_data is not None
