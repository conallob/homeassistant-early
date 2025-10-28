"""Test the EARLY switch platform."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from custom_components.early.switch import (
    EarlyActivitySwitch,
    async_setup_entry,
)
from custom_components.early.sensor import EarlyAPICoordinator
from custom_components.early.const import DOMAIN


class TestEarlyActivitySwitch:
    """Test the EarlyActivitySwitch class."""

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
        coordinator = EarlyAPICoordinator(
            mock_hass, "test_key", "test_secret"
        )
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
    async def test_async_setup_entry_missing_credentials(self, mock_hass):
        """Test setup fails gracefully with missing credentials."""
        config_entry = MagicMock()
        config_entry.data = {}
        async_add_entities = AsyncMock()

        await async_setup_entry(mock_hass, config_entry, async_add_entities)

        async_add_entities.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_setup_entry_no_coordinator(
        self, mock_hass, mock_config_entry
    ):
        """Test setup fails gracefully when coordinator not found."""
        mock_hass.data[DOMAIN] = {}
        async_add_entities = AsyncMock()

        await async_setup_entry(mock_hass, mock_config_entry, async_add_entities)

        async_add_entities.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_setup_entry_no_activities(
        self, mock_hass, mock_config_entry
    ):
        """Test setup with no activities."""
        coordinator = EarlyAPICoordinator(
            mock_hass, "test_key", "test_secret"
        )
        coordinator._activities = {}
        coordinator._tracking_data = {"currentTracking": None}

        mock_hass.data[DOMAIN] = {
            mock_config_entry.entry_id: {"coordinator": coordinator}
        }

        coordinator.async_update = AsyncMock()
        async_add_entities = AsyncMock()

        await async_setup_entry(mock_hass, mock_config_entry, async_add_entities)

        async_add_entities.assert_not_called()
