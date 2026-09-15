"""Test the EARLY switch platform."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.early.const import DOMAIN, ISSUE_REMOVED_ACTIVITIES
from custom_components.early.sensor import EarlyAPICoordinator
from custom_components.early.switch import EarlyActivitySwitch, async_setup_entry


class TestEarlyActivitySwitch:
    """Test the EarlyActivitySwitch class."""

    def test_switch_unique_id_without_config_entry_id(self, mock_hass):
        """Test unique_id keeps its original format for plain API entries."""
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")
        switch = EarlyActivitySwitch(coordinator, "activity_1", "Working")

        assert switch.unique_id == f"{DOMAIN}_activity_activity_1"

    def test_switch_unique_id_scoped_by_config_entry_id(self, mock_hass):
        """Test unique_id is scoped by config entry for Bluetooth+API entries.

        This avoids a collision with a Cloud API entry for the same account,
        since the README documents running both simultaneously.
        """
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")
        switch = EarlyActivitySwitch(
            coordinator, "activity_1", "Working", "bt_entry_id"
        )

        assert switch.unique_id == f"{DOMAIN}_bt_entry_id_activity_activity_1"

    @pytest.mark.asyncio
    async def test_switch_registers_and_unregisters_listener(self, mock_hass):
        """Test the switch registers for webhook-triggered refreshes and cleans up.

        This is what makes a webhook-triggered coordinator refresh show up
        immediately (via async_write_ha_state) instead of waiting for this
        entity's own next poll cycle.
        """
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")
        switch = EarlyActivitySwitch(coordinator, "activity_1", "Working")
        switch.async_write_ha_state = MagicMock()

        await switch.async_added_to_hass()
        assert len(coordinator._listeners) == 1

        coordinator._notify_listeners()
        switch.async_write_ha_state.assert_called_once()

        await switch.async_will_remove_from_hass()
        assert len(coordinator._listeners) == 0

    def test_switch_is_on_true(self, mock_hass):
        """Test switch is_on when activity is being tracked."""
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")
        coordinator._tracking_data = {
            "currentTracking": {
                "activity": {
                    "id": "activity_1",
                    "name": "Working",
                }
            }
        }
        switch = EarlyActivitySwitch(coordinator, "activity_1", "Working")

        assert switch.is_on is True

    def test_switch_is_on_false(self, mock_hass):
        """Test switch is_on when activity is not being tracked."""
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")
        coordinator._tracking_data = {
            "currentTracking": {
                "activity": {
                    "id": "activity_2",
                    "name": "Meeting",
                }
            }
        }
        switch = EarlyActivitySwitch(coordinator, "activity_1", "Working")

        assert switch.is_on is False

    def test_switch_is_on_true_flat_activity_id(self, mock_hass):
        """Test switch is_on resolves a flat activityId field, not just nested activity.id.

        Regression coverage: confirmed via real-account debug logs that
        EARLY's tracking endpoint can return currentTracking with a flat
        "activityId" field and no "activity" key at all. The old code only
        checked currentTracking["activity"]["id"], so every switch's is_on
        would resolve to False (never matching), regardless of which
        activity was actually being tracked.
        """
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")
        coordinator._tracking_data = {
            "currentTracking": {
                "id": 118278047,
                "activityId": "1752293",
                "startedAt": "2026-09-15T22:20:01.367",
            }
        }
        switch = EarlyActivitySwitch(coordinator, "1752293", "Focus")

        assert switch.is_on is True

    def test_switch_is_on_no_tracking(self, mock_hass):
        """Test switch is_on when nothing is being tracked."""
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")
        coordinator._tracking_data = {"currentTracking": None}
        switch = EarlyActivitySwitch(coordinator, "activity_1", "Working")

        assert switch.is_on is False

    def test_switch_is_on_no_data(self, mock_hass):
        """Test switch is_on when no tracking data available."""
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")
        switch = EarlyActivitySwitch(coordinator, "activity_1", "Working")

        assert switch.is_on is False

    @pytest.mark.asyncio
    async def test_switch_turn_on(self, mock_hass):
        """Test turning on a switch."""
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")
        coordinator.start_tracking = AsyncMock()
        coordinator.async_update = AsyncMock()
        switch = EarlyActivitySwitch(coordinator, "activity_1", "Working")

        await switch.async_turn_on()

        coordinator.start_tracking.assert_called_once_with("activity_1")
        coordinator.async_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_switch_turn_on_error(self, mock_hass):
        """Test turning on a switch with error."""
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")
        coordinator.start_tracking = AsyncMock(side_effect=Exception("API error"))
        switch = EarlyActivitySwitch(coordinator, "activity_1", "Working")

        # Should not raise exception
        await switch.async_turn_on()

        coordinator.start_tracking.assert_called_once_with("activity_1")

    @pytest.mark.asyncio
    async def test_switch_turn_off_when_on(self, mock_hass):
        """Test turning off a switch when it's on."""
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")
        coordinator._tracking_data = {
            "currentTracking": {
                "activity": {
                    "id": "activity_1",
                    "name": "Working",
                }
            }
        }
        coordinator.stop_tracking = AsyncMock()
        coordinator.async_update = AsyncMock()
        switch = EarlyActivitySwitch(coordinator, "activity_1", "Working")

        await switch.async_turn_off()

        coordinator.stop_tracking.assert_called_once()
        coordinator.async_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_switch_turn_off_when_off(self, mock_hass):
        """Test turning off a switch when it's already off."""
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")
        coordinator._tracking_data = {
            "currentTracking": {
                "activity": {
                    "id": "activity_2",
                    "name": "Meeting",
                }
            }
        }
        coordinator.stop_tracking = AsyncMock()
        switch = EarlyActivitySwitch(coordinator, "activity_1", "Working")

        await switch.async_turn_off()

        # Should not call stop_tracking since this activity is not active
        coordinator.stop_tracking.assert_not_called()

    @pytest.mark.asyncio
    async def test_switch_turn_off_error(self, mock_hass):
        """Test turning off a switch with error."""
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")
        coordinator._tracking_data = {
            "currentTracking": {
                "activity": {
                    "id": "activity_1",
                    "name": "Working",
                }
            }
        }
        coordinator.stop_tracking = AsyncMock(side_effect=Exception("API error"))
        switch = EarlyActivitySwitch(coordinator, "activity_1", "Working")

        # Should not raise exception
        await switch.async_turn_off()

        coordinator.stop_tracking.assert_called_once()

    def test_switch_available_true(self, mock_hass):
        """Test switch is available when tracking data exists."""
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")
        coordinator._tracking_data = {"currentTracking": None}
        switch = EarlyActivitySwitch(coordinator, "activity_1", "Working")

        assert switch.available is True

    def test_switch_available_false(self, mock_hass):
        """Test switch is unavailable when no tracking data."""
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")
        switch = EarlyActivitySwitch(coordinator, "activity_1", "Working")

        assert switch.available is False

    def test_switch_attributes(self, mock_hass):
        """Test switch attributes."""
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")
        switch = EarlyActivitySwitch(coordinator, "activity_1", "Working")

        attributes = switch.extra_state_attributes
        assert attributes["activity_id"] == "activity_1"
        assert attributes["activity_name"] == "Working"

    @pytest.mark.asyncio
    async def test_switch_update(self, mock_hass):
        """Test switch update method."""
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")
        coordinator.async_update = AsyncMock()
        switch = EarlyActivitySwitch(coordinator, "activity_1", "Working")

        await switch.async_update()

        coordinator.async_update.assert_called_once()


class TestSwitchPlatformSetup:
    """Test the switch platform setup."""

    @pytest.mark.asyncio
    async def test_async_setup_entry_success(self, mock_hass, mock_config_entry):
        """Test successful switch setup."""
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")
        coordinator._activities = {
            "activity_1": "Working",
            "activity_2": "Meeting",
        }
        coordinator._tracking_data = {"currentTracking": None}

        mock_hass.data[DOMAIN] = {
            mock_config_entry.entry_id: {"coordinator": coordinator}
        }

        coordinator.async_update = AsyncMock()
        async_add_entities = AsyncMock()

        await async_setup_entry(mock_hass, mock_config_entry, async_add_entities)

        async_add_entities.assert_called_once()
        entities = async_add_entities.call_args[0][0]
        assert len(entities) == 2
        assert all(isinstance(e, EarlyActivitySwitch) for e in entities)
        # Plain API entries keep the original unique_id format.
        assert all(e.unique_id.startswith(f"{DOMAIN}_activity_") for e in entities)

    @pytest.mark.asyncio
    async def test_async_setup_entry_bluetooth(
        self, mock_hass, mock_bluetooth_config_entry
    ):
        """Test setup skips Bluetooth devices."""
        async_add_entities = AsyncMock()

        await async_setup_entry(
            mock_hass, mock_bluetooth_config_entry, async_add_entities
        )

        async_add_entities.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_setup_entry_bluetooth_with_api(
        self, mock_hass, mock_bluetooth_config_entry_with_api
    ):
        """Test switches are created for a Bluetooth entry with API credentials."""
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")
        coordinator._activities = {
            "activity_1": "Working",
            "activity_2": "Meeting",
        }
        coordinator._tracking_data = {"currentTracking": None}

        mock_hass.data[DOMAIN] = {
            mock_bluetooth_config_entry_with_api.entry_id: {"coordinator": coordinator}
        }

        coordinator.async_update = AsyncMock()
        async_add_entities = AsyncMock()

        await async_setup_entry(
            mock_hass, mock_bluetooth_config_entry_with_api, async_add_entities
        )

        async_add_entities.assert_called_once()
        entities = async_add_entities.call_args[0][0]
        assert len(entities) == 2
        assert all(isinstance(e, EarlyActivitySwitch) for e in entities)
        # Bluetooth+API switches must be scoped by config entry so they
        # can't collide with a Cloud API entry for the same account.
        assert all(
            e.unique_id.startswith(
                f"{DOMAIN}_{mock_bluetooth_config_entry_with_api.entry_id}_activity_"
            )
            for e in entities
        )

    @pytest.mark.asyncio
    async def test_async_setup_entry_bluetooth_api_fetch_failed(
        self, mock_hass, mock_bluetooth_config_entry_with_api
    ):
        """Test switches are skipped when the initial activity fetch failed.

        bluetooth_sensor.py only stores a coordinator in hass.data when the
        initial async_fetch_activities() call succeeds; if it raises a
        RequestException, the entry is left with no "coordinator" key even
        though API credentials were configured. Switch setup must treat that
        the same as no credentials at all.
        """
        mock_hass.data[DOMAIN] = {mock_bluetooth_config_entry_with_api.entry_id: {}}
        async_add_entities = AsyncMock()

        await async_setup_entry(
            mock_hass, mock_bluetooth_config_entry_with_api, async_add_entities
        )

        async_add_entities.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_setup_entry_missing_credentials(self, mock_hass):
        """Test setup fails gracefully with missing credentials."""
        config_entry = MagicMock()
        config_entry.data = {}
        async_add_entities = AsyncMock()

        await async_setup_entry(mock_hass, config_entry, async_add_entities)

        async_add_entities.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_setup_entry_no_coordinator(self, mock_hass, mock_config_entry):
        """Test setup fails gracefully when coordinator not found."""
        mock_hass.data[DOMAIN] = {}
        async_add_entities = AsyncMock()

        await async_setup_entry(mock_hass, mock_config_entry, async_add_entities)

        async_add_entities.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_setup_entry_no_activities(self, mock_hass, mock_config_entry):
        """Test setup with no activities."""
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")
        coordinator._activities = {}
        coordinator._tracking_data = {"currentTracking": None}

        mock_hass.data[DOMAIN] = {
            mock_config_entry.entry_id: {"coordinator": coordinator}
        }

        coordinator.async_update = AsyncMock()
        async_add_entities = AsyncMock()

        await async_setup_entry(mock_hass, mock_config_entry, async_add_entities)

        async_add_entities.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_setup_entry_no_activities_still_registers_sync_listener(
        self, mock_hass, mock_config_entry
    ):
        """Test the dynamic-sync listener is registered even starting from zero activities.

        Regression coverage: async_setup_entry used to return early when
        the initial activities fetch was empty, before
        _async_sync_activity_switches was ever registered as a coordinator
        listener. Since that registration only happens here, a fresh EARLY
        account (or a transient empty first fetch) meant any activity
        created afterward would never get a switch until a full reload -
        exactly the gap this platform exists to close.
        """
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")
        coordinator._activities = {}
        coordinator._tracking_data = {"currentTracking": None}
        coordinator.async_update = AsyncMock()

        mock_hass.data[DOMAIN] = {
            mock_config_entry.entry_id: {"coordinator": coordinator}
        }
        async_add_entities = MagicMock()

        await async_setup_entry(mock_hass, mock_config_entry, async_add_entities)

        async_add_entities.assert_not_called()
        assert len(coordinator._listeners) == 1

        # An activity now exists (e.g. the user just created one in EARLY).
        coordinator._activities["activity_1"] = "Working"
        coordinator._notify_listeners()

        async_add_entities.assert_called_once()
        new_entities = async_add_entities.call_args[0][0]
        assert len(new_entities) == 1
        assert new_entities[0]._activity_id == "activity_1"

    @pytest.mark.asyncio
    async def test_async_setup_entry_registers_unload_cleanup(
        self, mock_hass, mock_config_entry
    ):
        """Test the coordinator listener is torn down when the entry unloads."""
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")
        coordinator._activities = {"activity_1": "Working"}
        coordinator._tracking_data = {"currentTracking": None}
        coordinator.async_update = AsyncMock()

        mock_hass.data[DOMAIN] = {
            mock_config_entry.entry_id: {"coordinator": coordinator}
        }

        await async_setup_entry(mock_hass, mock_config_entry, AsyncMock())

        assert len(coordinator._listeners) == 1
        assert mock_config_entry._on_unload is not None
        assert len(mock_config_entry._on_unload) == 1

        # Simulate the entry unloading.
        mock_config_entry._on_unload[0]()
        assert len(coordinator._listeners) == 0


class TestActivitySwitchDynamicSync:
    """Test switch.py's dynamic add-on-new-activity / repair-on-removed-activity behavior.

    Switches are otherwise only ever created once, at platform setup - an
    activity added or deleted in EARLY afterward would go unnoticed until a
    full integration reload. _async_sync_activity_switches (registered as a
    coordinator listener) is what catches that on every subsequent refresh.
    """

    async def _setup(self, mock_hass, mock_config_entry, activities):
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")
        coordinator._activities = dict(activities)
        coordinator._tracking_data = {"currentTracking": None}
        coordinator.async_update = AsyncMock()

        mock_hass.data[DOMAIN] = {
            mock_config_entry.entry_id: {"coordinator": coordinator}
        }
        async_add_entities = MagicMock()

        await async_setup_entry(mock_hass, mock_config_entry, async_add_entities)

        return coordinator, async_add_entities

    @pytest.mark.asyncio
    async def test_new_activity_gets_a_switch_without_reload(
        self, mock_hass, mock_config_entry
    ):
        """Test a new activity gets its switch added immediately, no reload."""
        coordinator, async_add_entities = await self._setup(
            mock_hass, mock_config_entry, {"activity_1": "Working"}
        )
        assert async_add_entities.call_count == 1

        coordinator._activities["activity_2"] = "Meeting"
        coordinator._notify_listeners()

        assert async_add_entities.call_count == 2
        new_entities = async_add_entities.call_args_list[1][0][0]
        assert len(new_entities) == 1
        assert new_entities[0]._activity_id == "activity_2"
        assert new_entities[0]._activity_name == "Meeting"

    @pytest.mark.asyncio
    async def test_new_activity_on_bluetooth_entry_gets_entry_scoped_unique_id(
        self, mock_hass, mock_bluetooth_config_entry_with_api
    ):
        """Test a dynamically-added switch on a Bluetooth+API entry is still scoped.

        CLAUDE.md calls out that Bluetooth+API entries scope their
        switches' unique_id by config_entry.entry_id (to avoid colliding
        with a Cloud API entry for the same account), while plain API
        entries don't. _build_switch is shared between the initial setup
        and _async_sync_activity_switches, but this pins down that the
        entry-scoping still applies to a switch added later via the sync
        listener, not just the ones created at initial setup.
        """
        coordinator, async_add_entities = await self._setup(
            mock_hass, mock_bluetooth_config_entry_with_api, {"activity_1": "Working"}
        )

        coordinator._activities["activity_2"] = "Meeting"
        coordinator._notify_listeners()

        new_entities = async_add_entities.call_args_list[1][0][0]
        assert len(new_entities) == 1
        assert new_entities[0].unique_id == (
            f"{DOMAIN}_{mock_bluetooth_config_entry_with_api.entry_id}"
            "_activity_activity_2"
        )

    @pytest.mark.asyncio
    async def test_no_new_switch_created_twice_for_the_same_activity(
        self, mock_hass, mock_config_entry
    ):
        """Test repeated notifications with no further changes don't re-add switches."""
        coordinator, async_add_entities = await self._setup(
            mock_hass, mock_config_entry, {"activity_1": "Working"}
        )

        coordinator._activities["activity_2"] = "Meeting"
        coordinator._notify_listeners()
        coordinator._notify_listeners()
        coordinator._notify_listeners()

        # One call for the initial setup, one for the single new activity -
        # the later no-op notifications must not re-add it.
        assert async_add_entities.call_count == 2

    @pytest.mark.asyncio
    async def test_removed_activity_raises_a_fixable_repair_issue(
        self, mock_hass, mock_config_entry
    ):
        """Test a deleted EARLY activity raises a fixable repair issue."""
        coordinator, _ = await self._setup(
            mock_hass,
            mock_config_entry,
            {"activity_1": "Working", "activity_2": "Meeting"},
        )

        del coordinator._activities["activity_2"]

        with patch(
            "custom_components.early.switch.ir.async_create_issue"
        ) as mock_create_issue:
            coordinator._notify_listeners()

            mock_create_issue.assert_called_once()
            args, kwargs = mock_create_issue.call_args
            assert args[1] == DOMAIN
            assert args[2] == f"{mock_config_entry.entry_id}_{ISSUE_REMOVED_ACTIVITIES}"
            assert kwargs["is_fixable"] is True
            assert kwargs["translation_key"] == ISSUE_REMOVED_ACTIVITIES
            assert "translation_placeholders" not in kwargs
            assert kwargs["data"]["entry_id"] == mock_config_entry.entry_id
            assert kwargs["data"]["removed_activity_names"] == "Meeting"

    @pytest.mark.asyncio
    async def test_no_issue_created_when_activities_unchanged(
        self, mock_hass, mock_config_entry
    ):
        """Test a plain refresh with no activity changes never creates an issue."""
        coordinator, _ = await self._setup(
            mock_hass, mock_config_entry, {"activity_1": "Working"}
        )

        with patch(
            "custom_components.early.switch.ir.async_create_issue"
        ) as mock_create_issue, patch(
            "custom_components.early.switch.ir.async_delete_issue"
        ) as mock_delete_issue:
            coordinator._notify_listeners()

            mock_create_issue.assert_not_called()
            mock_delete_issue.assert_called_once_with(
                mock_hass,
                DOMAIN,
                f"{mock_config_entry.entry_id}_{ISSUE_REMOVED_ACTIVITIES}",
            )

    @pytest.mark.asyncio
    async def test_issue_cleared_once_removed_activity_reappears(
        self, mock_hass, mock_config_entry
    ):
        """Test the repair issue is cleared if the activity list matches again."""
        coordinator, _ = await self._setup(
            mock_hass,
            mock_config_entry,
            {"activity_1": "Working", "activity_2": "Meeting"},
        )

        del coordinator._activities["activity_2"]
        with patch("custom_components.early.switch.ir.async_create_issue"):
            coordinator._notify_listeners()

        coordinator._activities["activity_2"] = "Meeting"
        with patch(
            "custom_components.early.switch.ir.async_delete_issue"
        ) as mock_delete_issue:
            coordinator._notify_listeners()

            mock_delete_issue.assert_called_once_with(
                mock_hass,
                DOMAIN,
                f"{mock_config_entry.entry_id}_{ISSUE_REMOVED_ACTIVITIES}",
            )

    @pytest.mark.asyncio
    async def test_add_and_remove_in_the_same_refresh(
        self, mock_hass, mock_config_entry
    ):
        """Test one activity added and another removed in the same refresh.

        Both code paths are driven off the same two set-difference
        computations (new_ids/removed_ids from current_ids vs. known_ids),
        so this pins down that they're independent - an addition landing
        in the same refresh as a removal shouldn't suppress either.
        """
        coordinator, async_add_entities = await self._setup(
            mock_hass,
            mock_config_entry,
            {"activity_1": "Working", "activity_2": "Meeting"},
        )

        del coordinator._activities["activity_2"]
        coordinator._activities["activity_3"] = "Focus"

        with patch(
            "custom_components.early.switch.ir.async_create_issue"
        ) as mock_create_issue:
            coordinator._notify_listeners()

            new_entities = async_add_entities.call_args_list[1][0][0]
            assert len(new_entities) == 1
            assert new_entities[0]._activity_id == "activity_3"

            mock_create_issue.assert_called_once()
            _, kwargs = mock_create_issue.call_args
            assert kwargs["data"]["removed_activity_names"] == "Meeting"

    @pytest.mark.asyncio
    async def test_issue_keeps_firing_on_every_refresh_while_unresolved(
        self, mock_hass, mock_config_entry
    ):
        """Test async_create_issue re-fires on repeated refreshes, not just once.

        Intentional behavior: removed_ids is derived from tracked_activities,
        which is never pruned outside of a reload, so as long as the removed
        activity stays gone this keeps calling async_create_issue on every
        subsequent refresh. That's a cheap, idempotent upsert (keyed by
        issue_id), not a bug - this pins it down as a regression guard.
        """
        coordinator, _ = await self._setup(
            mock_hass,
            mock_config_entry,
            {"activity_1": "Working", "activity_2": "Meeting"},
        )

        del coordinator._activities["activity_2"]

        with patch(
            "custom_components.early.switch.ir.async_create_issue"
        ) as mock_create_issue:
            coordinator._notify_listeners()
            coordinator._notify_listeners()
            coordinator._notify_listeners()

            assert mock_create_issue.call_count == 3
