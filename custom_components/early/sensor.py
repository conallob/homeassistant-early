"""Platform for EARLY (Timeular) sensor integration."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Callable

import requests
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import Throttle
from homeassistant.util.dt import utcnow

from .const import (
    API_ACTIVITIES_ENDPOINT,
    API_SIGN_IN_ENDPOINT,
    API_TRACKING_ENDPOINT,
    API_WEBHOOK_SUBSCRIPTION_ENDPOINT,
    ATTR_ACTIVITY_ID,
    ATTR_ACTIVITY_NAME,
    ATTR_NOTE,
    ATTR_STARTED_AT,
    CONF_API_SECRET,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .util import is_bluetooth_entry

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=DEFAULT_SCAN_INTERVAL)
ACTIVITIES_REFRESH_INTERVAL = timedelta(hours=1)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EARLY sensor from a config entry."""
    # Check if this is a Bluetooth device or API configuration
    if is_bluetooth_entry(config_entry):
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
        self._device_side_mapping: dict[int, str] = {}
        self._activities_last_fetch: datetime | None = None
        self._listeners: list[Callable[[], None]] = []
        # Serializes async_update()'s body so a webhook-triggered refresh
        # (no_throttle=True, see webhook.py) can't interleave its
        # token/tracking-data writes with a concurrently in-flight,
        # poll-triggered call - @Throttle below only guards how often a
        # call *starts*, not whether two calls can run at once.
        self._update_lock = asyncio.Lock()

    def add_listener(self, update_callback: Callable[[], None]) -> Callable[[], None]:
        """Register a callback to be invoked whenever tracking data refreshes.

        Used by entities so a webhook-triggered refresh (see webhook.py) is
        reflected immediately via async_write_ha_state, instead of sitting
        in the coordinator until the entity's own poll cycle catches up.
        Returns a function that removes the listener again.
        """
        self._listeners.append(update_callback)

        def remove_listener() -> None:
            self._listeners.remove(update_callback)

        return remove_listener

    def _notify_listeners(self) -> None:
        """Call every registered listener after a data refresh.

        Each callback is isolated so one misbehaving entity can't stop the
        others from being notified, or propagate out of async_update() and
        break the coordinator refresh (poll- or webhook-triggered) itself.
        Iterates a snapshot rather than self._listeners directly, so a
        listener that adds/removes a listener synchronously (none do
        today) can't skip an entry or raise a mutated-during-iteration
        error.
        """
        for update_callback in list(self._listeners):
            try:
                update_callback()
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Error notifying EARLY coordinator listener")

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
            token = data.get("token")
            if not token:
                raise requests.exceptions.HTTPError(
                    "API returned 200 but response contained no token"
                )
            self._token = token
            _LOGGER.debug("Successfully obtained EARLY API token")
            return self._token
        except requests.exceptions.RequestException as err:
            _LOGGER.error("Error getting EARLY API token: %s", err)
            raise

    async def _make_request(
        self, method: str, url: str, **kwargs: Any
    ) -> requests.Response:
        """Perform a single authenticated request using the current token."""
        token = await self._get_token()
        headers = {"Authorization": f"Bearer {token}"}
        return await self.hass.async_add_executor_job(
            lambda: getattr(requests, method)(
                url, headers=headers, timeout=10, **kwargs
            )
        )

    async def _request_with_retry(
        self, method: str, url: str, **kwargs: Any
    ) -> requests.Response:
        """Perform an authenticated request, retrying once if the token expired.

        Shared by every EARLY API call site (activity fetch, tracking
        status, start/stop tracking) so the 401-detect -> reset token ->
        retry behavior only needs to be implemented once.
        """
        response = await self._make_request(method, url, **kwargs)

        if response.status_code == 401:
            # Token expired, reset and try again
            _LOGGER.debug("Token expired, resetting")
            self._token = None
            response = await self._make_request(method, url, **kwargs)

        response.raise_for_status()
        return response

    async def _fetch_activities(self) -> None:
        """Fetch activities list to map activity IDs to names."""
        try:
            response = await self._request_with_retry("get", API_ACTIVITIES_ENDPOINT)
            data = response.json()

            # Build a mapping of activity ID to activity name
            # and device side to activity name
            if "activities" in data:
                self._activities = {
                    activity["id"]: activity.get("name", "Unknown Activity")
                    for activity in data["activities"]
                }

                # Build device side mapping (orientation -> activity name)
                self._device_side_mapping = {}
                for activity in data["activities"]:
                    device_side = activity.get("deviceSide")
                    if device_side is not None:
                        # deviceSide is the orientation number reported by
                        # the tracker (0-8): 1-8 are the physical sides, and
                        # 0 means the tracker is resting on its base with no
                        # side selected. Activities are only ever assigned to
                        # sides 1-8 in the EARLY app, so a deviceSide of 0
                        # should not normally appear here - if it does, it's
                        # treated like any other side and simply won't match
                        # anything meaningful via get_activity_by_device_side.
                        self._device_side_mapping[int(device_side)] = activity.get(
                            "name", "Unknown Activity"
                        )

                self._activities_last_fetch = utcnow()
                _LOGGER.debug(
                    "Fetched %d activities with %d device side mappings",
                    len(self._activities),
                    len(self._device_side_mapping),
                )

        except requests.exceptions.RequestException as err:
            _LOGGER.error("Error fetching EARLY activities: %s", err)

    async def async_fetch_activities(self) -> None:
        """Fetch activities from the API (public wrapper for external callers)."""
        await self._fetch_activities()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self) -> None:
        """Fetch data from EARLY API.

        The body runs under self._update_lock so a webhook-triggered
        refresh (no_throttle=True) can't interleave its writes with a
        concurrently in-flight, poll-triggered call.
        """
        async with self._update_lock:
            try:
                # Refresh activities at startup and at most once per hour
                activities_stale = (
                    not self._activities
                    or self._activities_last_fetch is None
                    or utcnow() - self._activities_last_fetch
                    > ACTIVITIES_REFRESH_INTERVAL
                )
                if activities_stale:
                    await self._fetch_activities()

                # Fetch current tracking status
                response = await self._request_with_retry("get", API_TRACKING_ENDPOINT)
                self._tracking_data = response.json()
                _LOGGER.debug("Updated EARLY tracking data: %s", self._tracking_data)

            except requests.exceptions.RequestException as err:
                _LOGGER.error("Error fetching EARLY tracking data: %s", err)
                self._tracking_data = None

            self._notify_listeners()

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

    def get_activity_by_device_side(self, device_side: int) -> str | None:
        """Get activity name from device side (orientation)."""
        return self._device_side_mapping.get(device_side)

    async def start_tracking(self, activity_id: str) -> None:
        """Start tracking a specific activity."""
        try:
            endpoint = f"{API_TRACKING_ENDPOINT}/{activity_id}/start"
            await self._request_with_retry("post", endpoint, json={})
            _LOGGER.debug("Started tracking activity %s", activity_id)

            # Update tracking data immediately
            await self.async_update()

        except requests.exceptions.RequestException as err:
            _LOGGER.error(
                "Error starting tracking for activity %s: %s", activity_id, err
            )
            raise

    async def stop_tracking(self) -> None:
        """Stop the current tracking."""
        try:
            endpoint = f"{API_TRACKING_ENDPOINT}/stop"
            await self._request_with_retry("post", endpoint, json={})
            _LOGGER.debug("Stopped tracking")

            # Update tracking data immediately
            await self.async_update()

        except requests.exceptions.RequestException as err:
            _LOGGER.error("Error stopping tracking: %s", err)
            raise

    async def async_subscribe_webhook(self, event: str, target_url: str) -> str | None:
        """Subscribe target_url to an EARLY webhook event.

        Returns the subscription id EARLY assigns, or None if the
        subscription request failed - callers should treat that as "no
        webhook available" and keep relying on polling rather than erroring
        out, since webhook support depends on Home Assistant having a
        publicly reachable URL.
        """
        try:
            response = await self._request_with_retry(
                "post",
                API_WEBHOOK_SUBSCRIPTION_ENDPOINT,
                json={"event": event, "targetUrl": target_url},
            )
            subscription_id = response.json().get("id")
            _LOGGER.debug(
                "Subscribed to EARLY webhook event %s (subscription %s)",
                event,
                subscription_id,
            )
            return subscription_id
        except requests.exceptions.RequestException as err:
            _LOGGER.warning(
                "Could not subscribe to EARLY webhook event %s: %s", event, err
            )
            return None
        except Exception:  # pylint: disable=broad-except
            # An unexpected response shape (e.g. a body that isn't a JSON
            # object) means the POST above may still have created a live
            # subscription on EARLY's side, even though we can't recover
            # its id to track/unsubscribe it later. There's nothing more
            # useful to do here than what a request failure already does -
            # log it and let the caller treat this event as unsubscribed,
            # rather than letting it crash webhook setup or getting
            # silently swallowed further up the call stack.
            _LOGGER.exception(
                "Unexpected error subscribing to EARLY webhook event %s", event
            )
            return None

    async def async_unsubscribe_webhook(self, subscription_id: str) -> None:
        """Remove a previously created EARLY webhook subscription."""
        try:
            await self._request_with_retry(
                "delete",
                f"{API_WEBHOOK_SUBSCRIPTION_ENDPOINT}/{subscription_id}",
            )
            _LOGGER.debug("Unsubscribed EARLY webhook %s", subscription_id)
        except requests.exceptions.RequestException as err:
            _LOGGER.debug(
                "Error unsubscribing EARLY webhook %s: %s", subscription_id, err
            )


class EarlyCurrentTrackingSensor(SensorEntity):
    """Representation of an EARLY current tracking sensor."""

    def __init__(self, coordinator: EarlyAPICoordinator) -> None:
        """Initialize the sensor."""
        self._coordinator = coordinator
        self._attr_name = "EARLY Current Activity"
        self._attr_unique_id = f"{DOMAIN}_current_tracking"
        self._attr_icon = "mdi:clock-outline"
        self._remove_listener: Callable[[], None] | None = None

    async def async_added_to_hass(self) -> None:
        """Register for immediate updates when the coordinator refreshes.

        This is what makes a webhook-triggered refresh (see webhook.py)
        show up right away instead of waiting for this entity's own next
        poll cycle.
        """
        self._remove_listener = self._coordinator.add_listener(
            self.async_write_ha_state
        )

    async def async_will_remove_from_hass(self) -> None:
        """Unregister from the coordinator."""
        if self._remove_listener is not None:
            self._remove_listener()
            self._remove_listener = None

    @property
    def _current_activity_name(self) -> str | None:
        """Resolve the current activity's name.

        The tracking endpoint's currentTracking.activity object doesn't
        reliably include a "name" field (observed in practice to return
        only "id") - fall back to the activities list the coordinator
        fetches separately from the activities endpoint.
        """
        if not self._coordinator.tracking_data:
            return None

        current_tracking = self._coordinator.tracking_data.get("currentTracking")
        if not current_tracking:
            return None

        activity = current_tracking.get("activity", {})
        name = activity.get("name")
        if name:
            return name

        activity_id = activity.get("id")
        if activity_id:
            return self._coordinator.get_all_activities().get(activity_id)

        return None

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        if not self._coordinator.tracking_data:
            return "unavailable"

        current_tracking = self._coordinator.tracking_data.get("currentTracking")
        if not current_tracking:
            return "idle"

        activity_name = self._current_activity_name
        return activity_name if activity_name else "tracking"

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
            ATTR_ACTIVITY_NAME: self._current_activity_name,
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
