"""Test the EARLY sensor platform."""

import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.util.dt import utcnow

from custom_components.early.const import DOMAIN
from custom_components.early.sensor import (
    EarlyAPICoordinator,
    EarlyCurrentTrackingSensor,
    async_setup_entry,
)


class TestEarlyAPICoordinator:
    """Test the EarlyAPICoordinator class."""

    @pytest.mark.asyncio
    async def test_get_token_success(self, mock_hass, mock_api_token_response):
        """Test successful token retrieval."""
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")

        with patch("requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_api_token_response
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            mock_hass.async_add_executor_job.return_value = mock_response

            token = await coordinator._get_token()

            assert token == "mock_bearer_token"
            assert coordinator._token == "mock_bearer_token"

    @pytest.mark.asyncio
    async def test_get_token_cached(self, mock_hass):
        """Test token is cached and not fetched again."""
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")
        coordinator._token = "cached_token"

        with patch("requests.post") as mock_post:
            token = await coordinator._get_token()

            assert token == "cached_token"
            mock_post.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_token_failure(self, mock_hass):
        """Test token retrieval failure."""
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")

        mock_hass.async_add_executor_job.side_effect = Exception("Connection failed")

        with pytest.raises(Exception):
            await coordinator._get_token()

    @pytest.mark.asyncio
    async def test_fetch_activities(
        self, mock_hass, mock_api_token_response, mock_activities_response
    ):
        """Test fetching activities."""
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")

        # Mock token request
        token_response = MagicMock()
        token_response.json.return_value = mock_api_token_response
        token_response.raise_for_status = MagicMock()

        # Mock activities request
        activities_response = MagicMock()
        activities_response.json.return_value = mock_activities_response
        activities_response.raise_for_status = MagicMock()

        mock_hass.async_add_executor_job.side_effect = [
            token_response,
            activities_response,
        ]

        await coordinator._fetch_activities()

        assert len(coordinator._activities) == 2
        assert coordinator._activities["activity_1"] == "Working"
        assert coordinator._activities["activity_2"] == "Meeting"

    @pytest.mark.asyncio
    async def test_fetch_activities_empty(self, mock_hass, mock_api_token_response):
        """Test fetching activities with empty response."""
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")

        # Mock token request
        token_response = MagicMock()
        token_response.json.return_value = mock_api_token_response
        token_response.raise_for_status = MagicMock()

        # Mock activities request with empty list
        activities_response = MagicMock()
        activities_response.json.return_value = {"activities": []}
        activities_response.raise_for_status = MagicMock()

        mock_hass.async_add_executor_job.side_effect = [
            token_response,
            activities_response,
        ]

        await coordinator._fetch_activities()

        assert len(coordinator._activities) == 0

    @pytest.mark.asyncio
    async def test_fetch_activities_token_refresh(
        self, mock_hass, mock_api_token_response, mock_activities_response
    ):
        """Test _fetch_activities retries on a 401 like the other API calls.

        Regression test: _fetch_activities previously didn't retry on an
        expired token, unlike async_update/start_tracking/stop_tracking -
        if the token expired between the last update and an hourly
        activities refresh, the fetch would fail, be logged, and leave
        the activity name mapping silently stale.
        """
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")
        coordinator._token = "expired_token"

        # Mock activities request with 401 on first call
        activities_response_401 = MagicMock()
        activities_response_401.status_code = 401

        # Mock new token request
        new_token_response = MagicMock()
        new_token_response.json.return_value = mock_api_token_response
        new_token_response.raise_for_status = MagicMock()

        # Mock activities request success on retry
        activities_response_success = MagicMock()
        activities_response_success.status_code = 200
        activities_response_success.json.return_value = mock_activities_response
        activities_response_success.raise_for_status = MagicMock()

        mock_hass.async_add_executor_job.side_effect = [
            activities_response_401,
            new_token_response,
            activities_response_success,
        ]

        await coordinator._fetch_activities()

        assert coordinator._token == "mock_bearer_token"
        assert len(coordinator._activities) == 2
        assert coordinator._activities["activity_1"] == "Working"

    @pytest.mark.asyncio
    async def test_async_update_success(
        self,
        mock_hass,
        mock_api_token_response,
        mock_activities_response,
        mock_tracking_response_active,
    ):
        """Test successful data update."""
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")

        # Mock token request
        token_response = MagicMock()
        token_response.json.return_value = mock_api_token_response
        token_response.raise_for_status = MagicMock()

        # Mock activities request
        activities_response = MagicMock()
        activities_response.json.return_value = mock_activities_response
        activities_response.raise_for_status = MagicMock()

        # Mock tracking request
        tracking_response = MagicMock()
        tracking_response.status_code = 200
        tracking_response.json.return_value = mock_tracking_response_active
        tracking_response.raise_for_status = MagicMock()

        mock_hass.async_add_executor_job.side_effect = [
            token_response,
            activities_response,
            tracking_response,
        ]

        await coordinator.async_update()

        assert coordinator.tracking_data == mock_tracking_response_active

    @pytest.mark.asyncio
    async def test_async_update_skips_fresh_activities(
        self, mock_hass, mock_tracking_response_active
    ):
        """Test async_update doesn't refetch activities within the hour.

        Regression coverage for the ACTIVITIES_REFRESH_INTERVAL staleness
        check: a coordinator with a recent _activities_last_fetch should
        skip _fetch_activities entirely and only hit the tracking endpoint.
        """
        from homeassistant.util.dt import utcnow

        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")
        coordinator._token = "cached_token"
        coordinator._activities = {"activity_1": "Working"}
        coordinator._activities_last_fetch = utcnow()

        # Mock tracking request - the only call this update should make
        tracking_response = MagicMock()
        tracking_response.status_code = 200
        tracking_response.json.return_value = mock_tracking_response_active
        tracking_response.raise_for_status = MagicMock()

        mock_hass.async_add_executor_job.side_effect = [tracking_response]

        await coordinator.async_update()

        assert coordinator.tracking_data == mock_tracking_response_active
        assert coordinator._activities == {"activity_1": "Working"}
        mock_hass.async_add_executor_job.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_update_token_refresh(
        self,
        mock_hass,
        mock_api_token_response,
        mock_activities_response,
        mock_tracking_response_active,
    ):
        """Test token refresh on 401 response."""
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")

        # Mock token request
        token_response = MagicMock()
        token_response.json.return_value = mock_api_token_response
        token_response.raise_for_status = MagicMock()

        # Mock activities request
        activities_response = MagicMock()
        activities_response.json.return_value = mock_activities_response
        activities_response.raise_for_status = MagicMock()

        # Mock tracking request with 401 on first call
        tracking_response_401 = MagicMock()
        tracking_response_401.status_code = 401

        # Mock tracking request with success on second call
        tracking_response_success = MagicMock()
        tracking_response_success.status_code = 200
        tracking_response_success.json.return_value = mock_tracking_response_active
        tracking_response_success.raise_for_status = MagicMock()

        # Mock new token request
        new_token_response = MagicMock()
        new_token_response.json.return_value = {"token": "new_bearer_token"}
        new_token_response.raise_for_status = MagicMock()

        mock_hass.async_add_executor_job.side_effect = [
            token_response,
            activities_response,
            tracking_response_401,
            new_token_response,
            tracking_response_success,
        ]

        await coordinator.async_update()

        assert coordinator.tracking_data == mock_tracking_response_active
        assert coordinator._token == "new_bearer_token"

    @pytest.mark.asyncio
    async def test_token_is_reset_on_401_before_refresh(
        self,
        mock_hass,
        mock_api_token_response,
        mock_activities_response,
        mock_tracking_response_active,
    ):
        """Test that token is explicitly set to None before refresh on 401."""
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")

        # Set initial token
        coordinator._token = "old_token"

        # Mock activities request
        activities_response = MagicMock()
        activities_response.json.return_value = mock_activities_response
        activities_response.raise_for_status = MagicMock()

        # Mock tracking request with 401
        tracking_response_401 = MagicMock()
        tracking_response_401.status_code = 401

        # Mock new token request
        new_token_response = MagicMock()
        new_token_response.json.return_value = {"token": "refreshed_token"}
        new_token_response.raise_for_status = MagicMock()

        # Mock successful tracking request
        tracking_response_success = MagicMock()
        tracking_response_success.status_code = 200
        tracking_response_success.json.return_value = mock_tracking_response_active
        tracking_response_success.raise_for_status = MagicMock()

        mock_hass.async_add_executor_job.side_effect = [
            activities_response,
            tracking_response_401,
            new_token_response,  # Token refresh
            tracking_response_success,
        ]

        # Verify token starts as old_token
        assert coordinator._token == "old_token"

        await coordinator.async_update()

        # Verify token was refreshed
        assert coordinator._token == "refreshed_token"
        assert coordinator.tracking_data == mock_tracking_response_active

    @pytest.mark.asyncio
    async def test_async_update_failure(self, mock_hass, mock_api_token_response):
        """Test update failure."""
        import requests as req_module

        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")
        coordinator._activities = {"test_id": "Test Activity"}

        # Mock token request
        token_response = MagicMock()
        token_response.json.return_value = mock_api_token_response
        token_response.raise_for_status = MagicMock()

        async def mock_executor(func):
            return func()

        mock_hass.async_add_executor_job = mock_executor

        # Mock tracking request failure
        with patch("custom_components.early.sensor.requests.post") as mock_post, patch(
            "custom_components.early.sensor.requests.get"
        ) as mock_get:
            mock_post.return_value = token_response
            mock_get.side_effect = req_module.exceptions.ConnectionError(
                "Network error"
            )

            await coordinator.async_update()

            assert coordinator.tracking_data is None

    @pytest.mark.asyncio
    async def test_start_tracking(
        self,
        mock_hass,
        mock_api_token_response,
        mock_tracking_response_active,
    ):
        """Test starting tracking."""
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")

        # Mock token request
        token_response = MagicMock()
        token_response.json.return_value = mock_api_token_response
        token_response.raise_for_status = MagicMock()

        # Mock start tracking request
        start_response = MagicMock()
        start_response.status_code = 200
        start_response.raise_for_status = MagicMock()

        # Mock update request after start
        tracking_response = MagicMock()
        tracking_response.status_code = 200
        tracking_response.json.return_value = mock_tracking_response_active
        tracking_response.raise_for_status = MagicMock()

        mock_hass.async_add_executor_job.side_effect = [
            token_response,
            start_response,
            token_response,  # For update call
            tracking_response,
        ]

        await coordinator.start_tracking("activity_1")

    @pytest.mark.asyncio
    async def test_start_tracking_token_refresh(
        self,
        mock_hass,
        mock_api_token_response,
        mock_tracking_response_active,
    ):
        """Test starting tracking with token refresh."""
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")

        # Mock token request
        token_response = MagicMock()
        token_response.json.return_value = mock_api_token_response
        token_response.raise_for_status = MagicMock()

        # Mock start tracking request with 401
        start_response_401 = MagicMock()
        start_response_401.status_code = 401

        # Mock start tracking request success
        start_response_success = MagicMock()
        start_response_success.status_code = 200
        start_response_success.raise_for_status = MagicMock()

        # Mock new token request
        new_token_response = MagicMock()
        new_token_response.json.return_value = {"token": "new_bearer_token"}
        new_token_response.raise_for_status = MagicMock()

        # Mock update request after start
        tracking_response = MagicMock()
        tracking_response.status_code = 200
        tracking_response.json.return_value = mock_tracking_response_active
        tracking_response.raise_for_status = MagicMock()

        mock_hass.async_add_executor_job.side_effect = [
            token_response,
            start_response_401,
            new_token_response,
            start_response_success,
            new_token_response,  # For update call
            tracking_response,
        ]

        await coordinator.start_tracking("activity_1")
        assert coordinator._token == "new_bearer_token"

    @pytest.mark.asyncio
    async def test_stop_tracking(
        self,
        mock_hass,
        mock_api_token_response,
        mock_tracking_response_idle,
    ):
        """Test stopping tracking."""
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")

        # Mock token request
        token_response = MagicMock()
        token_response.json.return_value = mock_api_token_response
        token_response.raise_for_status = MagicMock()

        # Mock stop tracking request
        stop_response = MagicMock()
        stop_response.status_code = 200
        stop_response.raise_for_status = MagicMock()

        # Mock update request after stop
        tracking_response = MagicMock()
        tracking_response.status_code = 200
        tracking_response.json.return_value = mock_tracking_response_idle
        tracking_response.raise_for_status = MagicMock()

        mock_hass.async_add_executor_job.side_effect = [
            token_response,
            stop_response,
            token_response,  # For update call
            tracking_response,
        ]

        await coordinator.stop_tracking()

    def test_get_activity_name(self, mock_hass):
        """Test getting activity name."""
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")
        coordinator._activities = {"activity_1": "Working", "activity_2": "Meeting"}

        assert coordinator.get_activity_name("activity_1") == "Working"
        assert coordinator.get_activity_name("unknown") == "Unknown Activity"

    def test_get_all_activities(self, mock_hass):
        """Test getting all activities."""
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")
        coordinator._activities = {"activity_1": "Working", "activity_2": "Meeting"}

        activities = coordinator.get_all_activities()
        assert len(activities) == 2
        assert activities["activity_1"] == "Working"

    def test_get_activity_by_device_side(self, mock_hass):
        """Test getting activity name by device side."""
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")
        coordinator._device_side_mapping = {
            1: "Working",
            2: "Meeting",
            3: "Break",
        }

        assert coordinator.get_activity_by_device_side(1) == "Working"
        assert coordinator.get_activity_by_device_side(2) == "Meeting"
        assert coordinator.get_activity_by_device_side(3) == "Break"
        assert coordinator.get_activity_by_device_side(4) is None
        assert coordinator.get_activity_by_device_side(99) is None

    @pytest.mark.asyncio
    async def test_fetch_activities_with_device_sides(
        self, mock_hass, mock_api_token_response, mock_activities_response
    ):
        """Test fetching activities builds device side mapping."""
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")

        # Mock token request
        token_response = MagicMock()
        token_response.json.return_value = mock_api_token_response
        token_response.raise_for_status = MagicMock()

        # Mock activities request
        activities_response = MagicMock()
        activities_response.json.return_value = mock_activities_response
        activities_response.raise_for_status = MagicMock()

        mock_hass.async_add_executor_job.side_effect = [
            token_response,
            activities_response,
        ]

        await coordinator._fetch_activities()

        assert len(coordinator._activities) == 2
        assert len(coordinator._device_side_mapping) == 2
        assert coordinator._device_side_mapping[1] == "Working"
        assert coordinator._device_side_mapping[2] == "Meeting"

    @pytest.mark.asyncio
    async def test_fetch_activities_with_unassigned_sides(
        self,
        mock_hass,
        mock_api_token_response,
        mock_activities_response_with_unassigned,
    ):
        """Test fetching activities with some unassigned device sides."""
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")

        # Mock token request
        token_response = MagicMock()
        token_response.json.return_value = mock_api_token_response
        token_response.raise_for_status = MagicMock()

        # Mock activities request
        activities_response = MagicMock()
        activities_response.json.return_value = mock_activities_response_with_unassigned
        activities_response.raise_for_status = MagicMock()

        mock_hass.async_add_executor_job.side_effect = [
            token_response,
            activities_response,
        ]

        await coordinator._fetch_activities()

        assert len(coordinator._activities) == 3
        assert len(coordinator._device_side_mapping) == 2  # Only 2 assigned
        assert coordinator._device_side_mapping[1] == "Working"
        assert coordinator._device_side_mapping[2] == "Meeting"
        assert 3 not in coordinator._device_side_mapping  # Break not assigned


class TestEarlyAPICoordinatorListeners:
    """Test the coordinator's webhook-refresh listener pub/sub."""

    def test_add_listener_returns_remover(self, mock_hass):
        """Test add_listener registers the callback and returns a remover."""
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")
        callback = MagicMock()

        remove = coordinator.add_listener(callback)
        coordinator._notify_listeners()
        callback.assert_called_once()

        remove()
        coordinator._notify_listeners()
        callback.assert_called_once()  # not called again after removal

    def test_notify_listeners_isolates_a_failing_listener(self, mock_hass):
        """Test one listener raising doesn't stop the others from running.

        Regression coverage: _notify_listeners previously called each
        listener unguarded, so a broken entity's async_write_ha_state could
        both skip every listener registered after it and propagate out of
        async_update() (and, transitively, out of the webhook handler).
        """
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")
        failing_callback = MagicMock(side_effect=RuntimeError("boom"))
        healthy_callback = MagicMock()
        coordinator.add_listener(failing_callback)
        coordinator.add_listener(healthy_callback)

        coordinator._notify_listeners()

        failing_callback.assert_called_once()
        healthy_callback.assert_called_once()

    def test_notify_listeners_survives_mutation_during_iteration(self, mock_hass):
        """Test removing a listener from within a callback doesn't break iteration.

        Regression coverage: _notify_listeners previously iterated
        self._listeners directly. Mutating that same list mid-iteration
        (e.g. an entity's remove_listener firing as a side effect of its
        own callback) would either skip the next listener or raise
        "list changed size during iteration" - iterating a snapshot avoids
        both.
        """
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")
        third_callback = MagicMock()

        def self_removing_callback():
            remove_second()

        first_callback = MagicMock()
        coordinator.add_listener(first_callback)
        remove_second = coordinator.add_listener(self_removing_callback)
        coordinator.add_listener(third_callback)

        coordinator._notify_listeners()

        first_callback.assert_called_once()
        third_callback.assert_called_once()
        assert len(coordinator._listeners) == 2

    @pytest.mark.asyncio
    async def test_async_update_holds_lock_for_its_duration(self, mock_hass):
        """Test the coordinator's update lock is held while a refresh is in flight.

        Regression coverage: a webhook-triggered refresh (no_throttle=True)
        can run concurrently with an in-flight, poll-triggered call.
        self._update_lock should serialize their bodies so one call's
        writes to self._token/_tracking_data can't be clobbered mid-flight
        by the other - this checks the lock is actually held for as long
        as a refresh is running, not just acquired and released instantly.
        """
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")
        coordinator._activities = {"activity_1": "Working"}
        coordinator._activities_last_fetch = utcnow()

        started = asyncio.Event()

        async def fake_request_with_retry(method, url, **kwargs):
            started.set()
            await asyncio.sleep(0.01)
            response = MagicMock()
            response.json.return_value = {"currentTracking": None}
            return response

        coordinator._request_with_retry = fake_request_with_retry

        async def probe_lock_while_update_runs():
            await started.wait()
            return coordinator._update_lock.locked()

        _, lock_was_held = await asyncio.gather(
            coordinator.async_update(no_throttle=True),
            probe_lock_while_update_runs(),
        )

        assert lock_was_held is True
        assert not coordinator._update_lock.locked()

    @pytest.mark.asyncio
    async def test_async_update_notifies_listeners(
        self,
        mock_hass,
        mock_api_token_response,
        mock_activities_response,
        mock_tracking_response_active,
    ):
        """Test a successful async_update notifies registered listeners."""
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")
        callback = MagicMock()
        coordinator.add_listener(callback)

        token_response = MagicMock()
        token_response.json.return_value = mock_api_token_response
        token_response.raise_for_status = MagicMock()

        activities_response = MagicMock()
        activities_response.json.return_value = mock_activities_response
        activities_response.raise_for_status = MagicMock()

        tracking_response = MagicMock()
        tracking_response.status_code = 200
        tracking_response.json.return_value = mock_tracking_response_active
        tracking_response.raise_for_status = MagicMock()

        mock_hass.async_add_executor_job.side_effect = [
            token_response,
            activities_response,
            tracking_response,
        ]

        await coordinator.async_update()

        callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_listeners_are_notified_after_the_lock_is_released(
        self,
        mock_hass,
        mock_api_token_response,
        mock_activities_response,
        mock_tracking_response_active,
    ):
        """Test a listener callback doesn't run while _update_lock is held.

        Regression coverage: _notify_listeners() previously ran inside the
        same `async with self._update_lock:` block as the fetch, so every
        entity's async_write_ha_state() ran while holding the lock meant
        to protect only the token/tracking-data writes - needlessly
        widening the critical section and blocking a webhook-triggered
        refresh behind whatever the slowest listener does.
        """
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")
        lock_state_when_notified = {}

        def listener():
            lock_state_when_notified["locked"] = coordinator._update_lock.locked()

        coordinator.add_listener(listener)

        token_response = MagicMock()
        token_response.json.return_value = mock_api_token_response
        token_response.raise_for_status = MagicMock()

        activities_response = MagicMock()
        activities_response.json.return_value = mock_activities_response
        activities_response.raise_for_status = MagicMock()

        tracking_response = MagicMock()
        tracking_response.status_code = 200
        tracking_response.json.return_value = mock_tracking_response_active
        tracking_response.raise_for_status = MagicMock()

        mock_hass.async_add_executor_job.side_effect = [
            token_response,
            activities_response,
            tracking_response,
        ]

        await coordinator.async_update()

        assert lock_state_when_notified["locked"] is False

    @pytest.mark.asyncio
    async def test_async_subscribe_webhook_success(self, mock_hass):
        """Test subscribing to a webhook event returns the subscription id."""
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")
        coordinator._token = "cached_token"

        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"id": "sub_123"}
        response.raise_for_status = MagicMock()
        mock_hass.async_add_executor_job.side_effect = [response]

        subscription_id = await coordinator.async_subscribe_webhook(
            "trackingStarted", "https://ha.example.com/api/webhook/abc"
        )

        assert subscription_id == "sub_123"

    @pytest.mark.asyncio
    async def test_async_subscribe_webhook_failure_returns_none(self, mock_hass):
        """Test a failed subscription request returns None instead of raising."""
        import requests as req_module

        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")
        coordinator._token = "cached_token"

        mock_hass.async_add_executor_job.side_effect = (
            req_module.exceptions.ConnectionError("Network error")
        )

        subscription_id = await coordinator.async_subscribe_webhook(
            "trackingStarted", "https://ha.example.com/api/webhook/abc"
        )

        assert subscription_id is None

    @pytest.mark.asyncio
    async def test_async_subscribe_webhook_malformed_response_returns_none(
        self, mock_hass
    ):
        """Test an unexpected response shape returns None instead of raising.

        Regression coverage: only requests.exceptions.RequestException was
        caught, so a response whose body isn't a JSON object (e.g.
        response.json() returning a list, or the request having already
        succeeded with EARLY but returning a body .get("id") can't be
        called on) would raise out of async_subscribe_webhook, out of the
        subscribe loop in webhook.py, and potentially out of entry setup -
        which doesn't match the rest of this module's "never leak or
        crash" design.
        """
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")
        coordinator._token = "cached_token"

        response = MagicMock()
        response.status_code = 200
        response.raise_for_status = MagicMock()
        response.json.return_value = ["unexpected", "list", "body"]
        mock_hass.async_add_executor_job.side_effect = [response]

        subscription_id = await coordinator.async_subscribe_webhook(
            "trackingStarted", "https://ha.example.com/api/webhook/abc"
        )

        assert subscription_id is None

    @pytest.mark.asyncio
    async def test_async_unsubscribe_webhook_success(self, mock_hass):
        """Test unsubscribing a webhook subscription."""
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")
        coordinator._token = "cached_token"

        response = MagicMock()
        response.status_code = 200
        response.raise_for_status = MagicMock()
        mock_hass.async_add_executor_job.side_effect = [response]

        await coordinator.async_unsubscribe_webhook("sub_123")

        mock_hass.async_add_executor_job.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_unsubscribe_webhook_failure_does_not_raise(self, mock_hass):
        """Test a failed unsubscribe request is swallowed, not raised."""
        import requests as req_module

        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")
        coordinator._token = "cached_token"

        mock_hass.async_add_executor_job.side_effect = (
            req_module.exceptions.ConnectionError("Network error")
        )

        await coordinator.async_unsubscribe_webhook("sub_123")


class TestEarlyCurrentTrackingSensor:
    """Test the EarlyCurrentTrackingSensor class."""

    def test_sensor_state_unavailable(self, mock_hass):
        """Test sensor state when data is unavailable."""
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")
        sensor = EarlyCurrentTrackingSensor(coordinator)

        assert sensor.state == "unavailable"
        assert sensor.available is False

    def test_sensor_state_idle(self, mock_hass, mock_tracking_response_idle):
        """Test sensor state when idle."""
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")
        coordinator._tracking_data = mock_tracking_response_idle
        sensor = EarlyCurrentTrackingSensor(coordinator)

        assert sensor.state == "idle"
        assert sensor.available is True

    def test_sensor_state_tracking(self, mock_hass):
        """Test sensor state when tracking."""
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")
        coordinator._tracking_data = {
            "currentTracking": {
                "activity": {
                    "id": "activity_1",
                    "name": "Working",
                },
                "startedAt": "2025-01-15T10:30:00.000Z",
            }
        }
        sensor = EarlyCurrentTrackingSensor(coordinator)

        assert sensor.state == "Working"
        assert sensor.available is True

    def test_sensor_state_tracking_no_name(self, mock_hass):
        """Test sensor state when tracking but no activity name."""
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")
        coordinator._tracking_data = {
            "currentTracking": {
                "activity": {
                    "id": "activity_1",
                },
            }
        }
        sensor = EarlyCurrentTrackingSensor(coordinator)

        assert sensor.state == "tracking"

    def test_sensor_state_tracking_no_name_falls_back_to_activities_list(
        self, mock_hass
    ):
        """Test sensor state falls back to the activities list for the name.

        The EARLY API's currentTracking.activity object has been observed
        in practice to only include "id", not "name" - the sensor must
        resolve the name from the coordinator's separately-fetched
        activities list instead of showing the generic "tracking" state.
        """
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")
        coordinator._activities = {"activity_1": "Working"}
        coordinator._tracking_data = {
            "currentTracking": {
                "activity": {
                    "id": "activity_1",
                },
            }
        }
        sensor = EarlyCurrentTrackingSensor(coordinator)

        assert sensor.state == "Working"

    def test_sensor_state_tracking_no_name_unknown_activity_id(self, mock_hass):
        """Test sensor state when the activity id isn't in the activities map.

        E.g. a stale/not-yet-refreshed activities list, or a newly created
        activity. Should fall back to "tracking" rather than crashing or
        showing a misleading name.
        """
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")
        coordinator._activities = {"activity_2": "Meeting"}
        coordinator._tracking_data = {
            "currentTracking": {
                "activity": {
                    "id": "activity_1",
                },
            }
        }
        sensor = EarlyCurrentTrackingSensor(coordinator)

        assert sensor.state == "tracking"
        assert "activity_name" not in sensor.extra_state_attributes

    def test_sensor_attributes_unavailable(self, mock_hass):
        """Test sensor attributes when data unavailable."""
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")
        sensor = EarlyCurrentTrackingSensor(coordinator)

        assert sensor.extra_state_attributes == {}

    def test_sensor_attributes_idle(self, mock_hass, mock_tracking_response_idle):
        """Test sensor attributes when idle."""
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")
        coordinator._tracking_data = mock_tracking_response_idle
        sensor = EarlyCurrentTrackingSensor(coordinator)

        attributes = sensor.extra_state_attributes
        assert attributes == {"status": "idle"}

    def test_sensor_attributes_tracking(self, mock_hass):
        """Test sensor attributes when tracking."""
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")
        coordinator._tracking_data = {
            "currentTracking": {
                "activity": {
                    "id": "activity_1",
                    "name": "Working",
                },
                "startedAt": "2025-01-15T10:30:00.000Z",
                "note": {
                    "text": "Working on tests",
                },
            }
        }
        sensor = EarlyCurrentTrackingSensor(coordinator)

        attributes = sensor.extra_state_attributes
        assert attributes["activity_id"] == "activity_1"
        assert attributes["activity_name"] == "Working"
        assert attributes["started_at"] == "2025-01-15T10:30:00.000Z"
        assert attributes["note"] == "Working on tests"

    def test_sensor_attributes_tracking_no_name_falls_back_to_activities_list(
        self, mock_hass
    ):
        """Test activity_name attribute falls back to the activities list."""
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")
        coordinator._activities = {"activity_1": "Working"}
        coordinator._tracking_data = {
            "currentTracking": {
                "activity": {
                    "id": "activity_1",
                },
                "startedAt": "2025-01-15T10:30:00.000Z",
            }
        }
        sensor = EarlyCurrentTrackingSensor(coordinator)

        attributes = sensor.extra_state_attributes
        assert attributes["activity_id"] == "activity_1"
        assert attributes["activity_name"] == "Working"

    def test_sensor_attributes_tracking_no_note(self, mock_hass):
        """Test sensor attributes when tracking without note."""
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")
        coordinator._tracking_data = {
            "currentTracking": {
                "activity": {
                    "id": "activity_1",
                    "name": "Working",
                },
                "startedAt": "2025-01-15T10:30:00.000Z",
            }
        }
        sensor = EarlyCurrentTrackingSensor(coordinator)

        attributes = sensor.extra_state_attributes
        assert "note" not in attributes

    @pytest.mark.asyncio
    async def test_sensor_update(self, mock_hass):
        """Test sensor update method."""
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")
        coordinator.async_update = AsyncMock()
        sensor = EarlyCurrentTrackingSensor(coordinator)

        await sensor.async_update()

        coordinator.async_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_sensor_registers_and_unregisters_listener(self, mock_hass):
        """Test the sensor registers for webhook-triggered refreshes and cleans up.

        This is what makes a webhook-triggered coordinator refresh show up
        immediately (via async_write_ha_state) instead of waiting for this
        entity's own next poll cycle.
        """
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")
        sensor = EarlyCurrentTrackingSensor(coordinator)
        sensor.async_write_ha_state = MagicMock()

        await sensor.async_added_to_hass()
        assert len(coordinator._listeners) == 1

        coordinator._notify_listeners()
        sensor.async_write_ha_state.assert_called_once()

        await sensor.async_will_remove_from_hass()
        assert len(coordinator._listeners) == 0


class TestSensorPlatformSetup:
    """Test the sensor platform setup."""

    @pytest.mark.asyncio
    async def test_async_setup_entry_api(self, mock_hass, mock_config_entry):
        """Test setting up API sensor entry."""
        mock_hass.data[DOMAIN] = {mock_config_entry.entry_id: {}}
        async_add_entities = AsyncMock()

        with patch(
            "custom_components.early.sensor.EarlyAPICoordinator.async_update",
            new_callable=AsyncMock,
        ) as mock_update:
            await async_setup_entry(mock_hass, mock_config_entry, async_add_entities)

            async_add_entities.assert_called_once()
            entities = async_add_entities.call_args[0][0]
            assert len(entities) == 1
            assert isinstance(entities[0], EarlyCurrentTrackingSensor)

    @pytest.mark.asyncio
    async def test_async_setup_entry_bluetooth(
        self, mock_hass, mock_bluetooth_config_entry
    ):
        """Test setting up Bluetooth sensor entry delegates correctly."""
        async_add_entities = AsyncMock()

        with patch(
            "custom_components.early.bluetooth_sensor.async_setup_bluetooth_entry"
        ) as mock_bt_setup:
            mock_bt_setup.return_value = None

            await async_setup_entry(
                mock_hass, mock_bluetooth_config_entry, async_add_entities
            )

            mock_bt_setup.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_setup_entry_missing_credentials(self, mock_hass):
        """Test setup fails gracefully with missing credentials."""
        config_entry = MagicMock()
        config_entry.data = {}
        async_add_entities = AsyncMock()

        await async_setup_entry(mock_hass, config_entry, async_add_entities)

        async_add_entities.assert_not_called()
