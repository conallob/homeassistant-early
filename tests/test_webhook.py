"""Test the EARLY webhook module."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.util.dt import utcnow

from custom_components.early.const import CONF_API_SECRET, DOMAIN
from custom_components.early.webhook import (
    WEBHOOK_EVENTS,
    WEBHOOK_STATE_KEY,
    async_setup_webhook,
    async_unload_webhook,
)


@pytest.fixture
def coordinator():
    """Return a mock coordinator."""
    coordinator = MagicMock()
    coordinator.async_subscribe_webhook = AsyncMock(
        side_effect=lambda event, url: f"sub_{event}"
    )
    coordinator.async_unsubscribe_webhook = AsyncMock()
    coordinator.async_update = AsyncMock()
    return coordinator


class TestAsyncSetupWebhook:
    """Test async_setup_webhook."""

    @pytest.mark.asyncio
    async def test_no_external_url_skips_registration(
        self, mock_hass, mock_config_entry, coordinator
    ):
        """Test setup is skipped (not raised) with no public URL configured."""
        from homeassistant.helpers.network import NoURLAvailableError

        mock_hass.data[DOMAIN] = {mock_config_entry.entry_id: {}}

        with patch(
            "custom_components.early.webhook.get_url",
            side_effect=NoURLAvailableError,
        ), patch(
            "custom_components.early.webhook.webhook.async_register"
        ) as mock_register:
            await async_setup_webhook(mock_hass, mock_config_entry, coordinator)

            mock_register.assert_not_called()
            coordinator.async_subscribe_webhook.assert_not_called()
            assert (
                "webhook_id" not in mock_hass.data[DOMAIN][mock_config_entry.entry_id]
            )

    @pytest.mark.asyncio
    async def test_registers_and_subscribes_both_events(
        self, mock_hass, mock_config_entry, coordinator
    ):
        """Test a webhook is registered and both events subscribed."""
        mock_hass.data[DOMAIN] = {mock_config_entry.entry_id: {}}

        with patch(
            "custom_components.early.webhook.get_url",
            return_value="https://ha.example.com",
        ), patch(
            "custom_components.early.webhook.webhook.async_generate_id",
            return_value="test_webhook_id",
        ), patch(
            "custom_components.early.webhook.webhook.async_register"
        ) as mock_register:
            await async_setup_webhook(mock_hass, mock_config_entry, coordinator)

            mock_register.assert_called_once()
            assert coordinator.async_subscribe_webhook.call_count == len(WEBHOOK_EVENTS)

            entry_data = mock_hass.data[DOMAIN][mock_config_entry.entry_id]
            assert entry_data["webhook_id"] == "test_webhook_id"
            assert len(entry_data["webhook_subscription_ids"]) == len(WEBHOOK_EVENTS)

    @pytest.mark.asyncio
    async def test_subscribed_url_is_built_from_the_reachability_check(
        self, mock_hass, mock_config_entry, coordinator
    ):
        """Test the URL subscribed with EARLY comes from the same get_url() call.

        Regression coverage: async_setup_webhook used to build webhook_url
        via webhook.async_generate_url(), which makes its own separate
        get_url() call with different defaults (allow_internal=True,
        allow_cloud=False) than the reachability check just above it. If
        those two calls ever resolved to different URLs, EARLY would
        happily accept a subscription pointed at a URL it can never
        reach - silently degrading to polling-only forever with nothing to
        log, since the "subscribe" call itself would still succeed. Now
        webhook_url is built directly from the checked URL, so the two
        can't diverge.
        """
        mock_hass.data[DOMAIN] = {mock_config_entry.entry_id: {}}

        with patch(
            "custom_components.early.webhook.get_url",
            return_value="https://ha.example.com",
        ), patch(
            "custom_components.early.webhook.webhook.async_generate_id",
            return_value="test_webhook_id",
        ), patch(
            "custom_components.early.webhook.webhook.async_register"
        ):
            await async_setup_webhook(mock_hass, mock_config_entry, coordinator)

            for call in coordinator.async_subscribe_webhook.call_args_list:
                _event, target_url = call.args
                assert (
                    target_url == "https://ha.example.com/api/webhook/test_webhook_id"
                )

    @pytest.mark.asyncio
    async def test_unregisters_local_webhook_when_no_subscriptions_succeed(
        self, mock_hass, mock_config_entry, coordinator
    ):
        """Test the local webhook is torn down if EARLY rejects every subscription."""
        coordinator.async_subscribe_webhook = AsyncMock(return_value=None)
        mock_hass.data[DOMAIN] = {mock_config_entry.entry_id: {}}

        with patch(
            "custom_components.early.webhook.get_url",
            return_value="https://ha.example.com",
        ), patch(
            "custom_components.early.webhook.webhook.async_generate_id",
            return_value="test_webhook_id",
        ), patch(
            "custom_components.early.webhook.webhook.async_register"
        ), patch(
            "custom_components.early.webhook.webhook.async_unregister"
        ) as mock_unregister:
            await async_setup_webhook(mock_hass, mock_config_entry, coordinator)

            mock_unregister.assert_called_once_with(mock_hass, "test_webhook_id")
            entry_data = mock_hass.data[DOMAIN][mock_config_entry.entry_id]
            assert "webhook_id" not in entry_data
            assert "webhook_subscription_ids" not in entry_data

    @pytest.mark.asyncio
    async def test_webhook_handler_triggers_unthrottled_refresh(
        self, mock_hass, mock_config_entry, coordinator
    ):
        """Test an incoming webhook call refreshes tracking data immediately."""
        mock_hass.data[DOMAIN] = {mock_config_entry.entry_id: {}}
        captured_handler = {}

        def _capture_register(hass, domain, name, webhook_id, handler, **kwargs):
            captured_handler["handler"] = handler

        with patch(
            "custom_components.early.webhook.get_url",
            return_value="https://ha.example.com",
        ), patch(
            "custom_components.early.webhook.webhook.async_generate_id",
            return_value="test_webhook_id",
        ), patch(
            "custom_components.early.webhook.webhook.async_register",
            side_effect=_capture_register,
        ):
            await async_setup_webhook(mock_hass, mock_config_entry, coordinator)

        request = MagicMock()
        request.json = AsyncMock(return_value={"type": "trackingStarted"})

        response = await captured_handler["handler"](
            mock_hass, "test_webhook_id", request
        )

        coordinator.async_update.assert_called_once_with(no_throttle=True)
        assert response.status == 200

    @pytest.mark.asyncio
    async def test_webhook_handler_tolerates_invalid_json(
        self, mock_hass, mock_config_entry, coordinator
    ):
        """Test the handler still refreshes even if the body isn't valid JSON."""
        mock_hass.data[DOMAIN] = {mock_config_entry.entry_id: {}}
        captured_handler = {}

        def _capture_register(hass, domain, name, webhook_id, handler, **kwargs):
            captured_handler["handler"] = handler

        with patch(
            "custom_components.early.webhook.get_url",
            return_value="https://ha.example.com",
        ), patch(
            "custom_components.early.webhook.webhook.async_generate_id",
            return_value="test_webhook_id",
        ), patch(
            "custom_components.early.webhook.webhook.async_register",
            side_effect=_capture_register,
        ):
            await async_setup_webhook(mock_hass, mock_config_entry, coordinator)

        request = MagicMock()
        request.json = AsyncMock(side_effect=ValueError("bad json"))

        response = await captured_handler["handler"](
            mock_hass, "test_webhook_id", request
        )

        coordinator.async_update.assert_called_once_with(no_throttle=True)
        assert response.status == 200

    @pytest.mark.asyncio
    async def test_webhook_handler_swallows_update_exception(
        self, mock_hass, mock_config_entry, coordinator
    ):
        """Test an exception from the coordinator refresh doesn't escape the handler.

        Regression test: coordinator.async_update() was previously called
        unguarded inside _handle_webhook, so any exception it raised (e.g.
        from a broken entity listener) would propagate out of the aiohttp
        view instead of being caught and logged like every other failure
        mode this module documents.
        """
        coordinator.async_update = AsyncMock(side_effect=RuntimeError("boom"))
        mock_hass.data[DOMAIN] = {mock_config_entry.entry_id: {}}
        captured_handler = {}

        def _capture_register(hass, domain, name, webhook_id, handler, **kwargs):
            captured_handler["handler"] = handler

        with patch(
            "custom_components.early.webhook.get_url",
            return_value="https://ha.example.com",
        ), patch(
            "custom_components.early.webhook.webhook.async_generate_id",
            return_value="test_webhook_id",
        ), patch(
            "custom_components.early.webhook.webhook.async_register",
            side_effect=_capture_register,
        ):
            await async_setup_webhook(mock_hass, mock_config_entry, coordinator)

        request = MagicMock()
        request.json = AsyncMock(return_value={"type": "trackingStarted"})

        response = await captured_handler["handler"](
            mock_hass, "test_webhook_id", request
        )

        assert response.status == 200

    @pytest.mark.asyncio
    async def test_webhook_handler_rate_limits_unthrottled_refreshes(
        self, mock_hass, mock_config_entry, coordinator
    ):
        """Test rapid webhook calls only force one unthrottled refresh.

        The webhook_id's obscurity is the only access control on the
        endpoint, and every hit otherwise bypasses the coordinator's
        normal @Throttle via no_throttle=True. Calls arriving faster than
        WEBHOOK_MIN_REFRESH_INTERVAL should fall back to a plain,
        still-throttled async_update() instead of each forcing another
        live EARLY API call.
        """
        mock_hass.data[DOMAIN] = {mock_config_entry.entry_id: {}}
        captured_handler = {}

        def _capture_register(hass, domain, name, webhook_id, handler, **kwargs):
            captured_handler["handler"] = handler

        with patch(
            "custom_components.early.webhook.get_url",
            return_value="https://ha.example.com",
        ), patch(
            "custom_components.early.webhook.webhook.async_generate_id",
            return_value="test_webhook_id",
        ), patch(
            "custom_components.early.webhook.webhook.async_register",
            side_effect=_capture_register,
        ):
            await async_setup_webhook(mock_hass, mock_config_entry, coordinator)

        request = MagicMock()
        request.json = AsyncMock(return_value={"type": "trackingStarted"})

        await captured_handler["handler"](mock_hass, "test_webhook_id", request)
        await captured_handler["handler"](mock_hass, "test_webhook_id", request)

        assert coordinator.async_update.call_args_list == [
            ((), {"no_throttle": True}),
            ((), {}),
        ]

    @pytest.mark.asyncio
    async def test_webhook_handler_allows_immediate_refresh_after_interval(
        self, mock_hass, mock_config_entry, coordinator
    ):
        """Test a call after WEBHOOK_MIN_REFRESH_INTERVAL gets an unthrottled refresh again."""
        from custom_components.early.webhook import WEBHOOK_MIN_REFRESH_INTERVAL

        mock_hass.data[DOMAIN] = {mock_config_entry.entry_id: {}}
        captured_handler = {}

        def _capture_register(hass, domain, name, webhook_id, handler, **kwargs):
            captured_handler["handler"] = handler

        with patch(
            "custom_components.early.webhook.get_url",
            return_value="https://ha.example.com",
        ), patch(
            "custom_components.early.webhook.webhook.async_generate_id",
            return_value="test_webhook_id",
        ), patch(
            "custom_components.early.webhook.webhook.async_register",
            side_effect=_capture_register,
        ):
            await async_setup_webhook(mock_hass, mock_config_entry, coordinator)

        request = MagicMock()
        request.json = AsyncMock(return_value={"type": "trackingStarted"})

        base_time = utcnow()
        with patch("custom_components.early.webhook.utcnow", return_value=base_time):
            await captured_handler["handler"](mock_hass, "test_webhook_id", request)

        with patch(
            "custom_components.early.webhook.utcnow",
            return_value=base_time + WEBHOOK_MIN_REFRESH_INTERVAL,
        ):
            await captured_handler["handler"](mock_hass, "test_webhook_id", request)

        assert coordinator.async_update.call_args_list == [
            ((), {"no_throttle": True}),
            ((), {"no_throttle": True}),
        ]

    @pytest.mark.asyncio
    async def test_webhook_handler_rate_limit_is_atomic_under_concurrency(
        self, mock_hass, mock_config_entry, coordinator
    ):
        """Test two webhook calls arriving together only get one unthrottled refresh.

        Regression coverage: the rate-limit check-then-set on
        last_refresh_at previously wasn't guarded by a lock. Two calls
        each await request.json() first, so without the lock both could
        resume and observe the same "no previous refresh" state before
        either writes it, and both would take the no_throttle=True path.
        """
        mock_hass.data[DOMAIN] = {mock_config_entry.entry_id: {}}
        captured_handler = {}

        def _capture_register(hass, domain, name, webhook_id, handler, **kwargs):
            captured_handler["handler"] = handler

        with patch(
            "custom_components.early.webhook.get_url",
            return_value="https://ha.example.com",
        ), patch(
            "custom_components.early.webhook.webhook.async_generate_id",
            return_value="test_webhook_id",
        ), patch(
            "custom_components.early.webhook.webhook.async_register",
            side_effect=_capture_register,
        ):
            await async_setup_webhook(mock_hass, mock_config_entry, coordinator)

        # request.json() yields control (like a real await on I/O would),
        # giving both concurrent handler calls a chance to interleave
        # before either reaches the rate-limit check.
        request = MagicMock()

        async def yielding_json():
            await asyncio.sleep(0)
            return {"type": "trackingStarted"}

        request.json = yielding_json

        await asyncio.gather(
            captured_handler["handler"](mock_hass, "test_webhook_id", request),
            captured_handler["handler"](mock_hass, "test_webhook_id", request),
        )

        no_throttle_calls = [
            call
            for call in coordinator.async_update.call_args_list
            if call == ((), {"no_throttle": True})
        ]
        assert len(no_throttle_calls) == 1


class TestAsyncUnloadWebhook:
    """Test async_unload_webhook."""

    @pytest.mark.asyncio
    async def test_unsubscribes_and_unregisters(
        self, mock_hass, mock_config_entry, coordinator
    ):
        """Test unload unsubscribes every event and removes the local webhook."""
        mock_hass.data[DOMAIN] = {
            mock_config_entry.entry_id: {
                "webhook_id": "test_webhook_id",
                "webhook_subscription_ids": {
                    "trackingStarted": "sub_started",
                    "trackingStopped": "sub_stopped",
                },
            }
        }

        with patch(
            "custom_components.early.webhook.webhook.async_unregister"
        ) as mock_unregister:
            await async_unload_webhook(mock_hass, mock_config_entry, coordinator)

            assert coordinator.async_unsubscribe_webhook.call_count == 2
            mock_unregister.assert_called_once_with(mock_hass, "test_webhook_id")

        entry_data = mock_hass.data[DOMAIN][mock_config_entry.entry_id]
        assert "webhook_id" not in entry_data
        assert "webhook_subscription_ids" not in entry_data

    @pytest.mark.asyncio
    async def test_noop_when_never_registered(
        self, mock_hass, mock_config_entry, coordinator
    ):
        """Test unload is a no-op when no webhook was ever set up for this entry."""
        mock_hass.data[DOMAIN] = {mock_config_entry.entry_id: {}}

        with patch(
            "custom_components.early.webhook.webhook.async_unregister"
        ) as mock_unregister:
            await async_unload_webhook(mock_hass, mock_config_entry, coordinator)

            mock_unregister.assert_not_called()
            coordinator.async_unsubscribe_webhook.assert_not_called()


class TestWebhookSurvivesRestart:
    """Test cleanup of a subscription left behind by a non-graceful restart.

    async_unload_entry (and thus async_unload_webhook) only runs on a clean
    unload/reload - a bare process restart skips it entirely, which would
    otherwise leak an orphaned webhook_id/subscription in EARLY's account
    every time it happens. async_setup_webhook mirrors its state into
    config_entry.data (WEBHOOK_STATE_KEY) specifically so the next setup
    can find and clean up whatever the last run left behind.
    """

    @pytest.fixture
    def entry_with_stale_webhook_state(self):
        """Return a config entry carrying webhook state from a "previous run"."""
        return ConfigEntry(
            version=1,
            minor_version=1,
            domain=DOMAIN,
            title="EARLY",
            data={
                CONF_API_KEY: "test_api_key",
                CONF_API_SECRET: "test_api_secret",
                WEBHOOK_STATE_KEY: {
                    "webhook_id": "stale_webhook_id",
                    "subscription_ids": {
                        "trackingStarted": "stale_sub_started",
                        "trackingStopped": "stale_sub_stopped",
                    },
                },
            },
            source="user",
            entry_id="test_entry_id",
            unique_id="test_unique_id",
        )

    @pytest.mark.asyncio
    async def test_setup_unsubscribes_stale_state_before_resubscribing(
        self, mock_hass, entry_with_stale_webhook_state, coordinator
    ):
        """Test stale subscriptions are unsubscribed before new ones are created."""
        mock_hass.data[DOMAIN] = {entry_with_stale_webhook_state.entry_id: {}}

        with patch(
            "custom_components.early.webhook.get_url",
            return_value="https://ha.example.com",
        ), patch(
            "custom_components.early.webhook.webhook.async_generate_id",
            return_value="new_webhook_id",
        ), patch(
            "custom_components.early.webhook.webhook.async_generate_url",
            return_value="https://ha.example.com/api/webhook/new_webhook_id",
        ), patch(
            "custom_components.early.webhook.webhook.async_register"
        ):
            await async_setup_webhook(
                mock_hass, entry_with_stale_webhook_state, coordinator
            )

            coordinator.async_unsubscribe_webhook.assert_any_call("stale_sub_started")
            coordinator.async_unsubscribe_webhook.assert_any_call("stale_sub_stopped")

            mock_hass.config_entries.async_update_entry.assert_any_call(
                entry_with_stale_webhook_state,
                data={
                    CONF_API_KEY: "test_api_key",
                    CONF_API_SECRET: "test_api_secret",
                },
            )

    @pytest.mark.asyncio
    async def test_stale_subscription_forgotten_even_without_a_public_url(
        self, mock_hass, entry_with_stale_webhook_state, coordinator
    ):
        """Test stale state is cleaned up even if setup can't create a new webhook.

        Regression coverage: async_setup_webhook used to check get_url()
        before calling _async_forget_previous_subscription and return
        early on NoURLAvailableError. If a public URL was available on a
        prior setup but stops being available later (proxy reconfigured,
        Cloud disconnected, etc.), that early return meant the old
        subscription - and its WEBHOOK_STATE_KEY entry - was never cleaned
        up, since the only code path that would do it required the URL
        that's now missing.
        """
        from homeassistant.helpers.network import NoURLAvailableError

        mock_hass.data[DOMAIN] = {entry_with_stale_webhook_state.entry_id: {}}

        with patch(
            "custom_components.early.webhook.get_url",
            side_effect=NoURLAvailableError,
        ):
            await async_setup_webhook(
                mock_hass, entry_with_stale_webhook_state, coordinator
            )

            coordinator.async_unsubscribe_webhook.assert_any_call("stale_sub_started")
            coordinator.async_unsubscribe_webhook.assert_any_call("stale_sub_stopped")
            mock_hass.config_entries.async_update_entry.assert_any_call(
                entry_with_stale_webhook_state,
                data={
                    CONF_API_KEY: "test_api_key",
                    CONF_API_SECRET: "test_api_secret",
                },
            )

    @pytest.mark.asyncio
    async def test_setup_persists_new_state_for_future_cleanup(
        self, mock_hass, mock_config_entry, coordinator
    ):
        """Test a successful setup mirrors its webhook state into entry.data."""
        mock_hass.data[DOMAIN] = {mock_config_entry.entry_id: {}}

        with patch(
            "custom_components.early.webhook.get_url",
            return_value="https://ha.example.com",
        ), patch(
            "custom_components.early.webhook.webhook.async_generate_id",
            return_value="new_webhook_id",
        ), patch(
            "custom_components.early.webhook.webhook.async_generate_url",
            return_value="https://ha.example.com/api/webhook/new_webhook_id",
        ), patch(
            "custom_components.early.webhook.webhook.async_register"
        ):
            await async_setup_webhook(mock_hass, mock_config_entry, coordinator)

            _, kwargs = mock_hass.config_entries.async_update_entry.call_args
            assert kwargs["data"][WEBHOOK_STATE_KEY]["webhook_id"] == "new_webhook_id"

    @pytest.mark.asyncio
    async def test_unload_clears_persisted_state(
        self, mock_hass, entry_with_stale_webhook_state, coordinator
    ):
        """Test a graceful unload clears the persisted webhook state too."""
        mock_hass.data[DOMAIN] = {
            entry_with_stale_webhook_state.entry_id: {
                "webhook_id": "stale_webhook_id",
                "webhook_subscription_ids": {
                    "trackingStarted": "stale_sub_started",
                    "trackingStopped": "stale_sub_stopped",
                },
            }
        }

        with patch("custom_components.early.webhook.webhook.async_unregister"):
            await async_unload_webhook(
                mock_hass, entry_with_stale_webhook_state, coordinator
            )

            mock_hass.config_entries.async_update_entry.assert_called_once_with(
                entry_with_stale_webhook_state,
                data={
                    CONF_API_KEY: "test_api_key",
                    CONF_API_SECRET: "test_api_secret",
                },
            )
