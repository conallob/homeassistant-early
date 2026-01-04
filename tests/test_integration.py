"""Integration tests for the EARLY integration."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.config_entries import ConfigEntry

from custom_components.early import async_setup_entry, async_unload_entry
from custom_components.early.const import DOMAIN, CONF_API_SECRET
from custom_components.early.sensor import EarlyAPICoordinator


class TestFullAPIIntegration:
    """Test full API integration workflow."""

    @pytest.mark.asyncio
    async def test_full_setup_and_tracking_workflow(
        self, mock_hass, mock_config_entry, mock_api_token_response, mock_activities_response
    ):
        """Test complete workflow: setup, fetch activities, start/stop tracking."""
        # Mock API responses
        token_response = MagicMock()
        token_response.json.return_value = mock_api_token_response
        token_response.status_code = 200
        token_response.raise_for_status = MagicMock()

        activities_response = MagicMock()
        activities_response.json.return_value = mock_activities_response
        activities_response.status_code = 200
        activities_response.raise_for_status = MagicMock()

        tracking_idle = MagicMock()
        tracking_idle.json.return_value = {"currentTracking": None}
        tracking_idle.status_code = 200
        tracking_idle.raise_for_status = MagicMock()

        tracking_active = MagicMock()
        tracking_active.json.return_value = {
            "currentTracking": {
                "activity": {"id": "activity_1", "name": "Working"},
                "startedAt": "2025-01-15T10:00:00.000Z",
            }
        }
        tracking_active.status_code = 200
        tracking_active.raise_for_status = MagicMock()

        start_response = MagicMock()
        start_response.status_code = 200
        start_response.raise_for_status = MagicMock()

        stop_response = MagicMock()
        stop_response.status_code = 200
        stop_response.raise_for_status = MagicMock()

        mock_hass.async_add_executor_job.side_effect = [
            token_response,  # Initial token
            activities_response,  # Fetch activities
            tracking_idle,  # Initial tracking status
            token_response,  # Start tracking - get token
            start_response,  # Start tracking
            token_response,  # Update after start
            tracking_active,  # Tracking status after start
            token_response,  # Stop tracking - get token
            stop_response,  # Stop tracking
            token_response,  # Update after stop
            tracking_idle,  # Tracking status after stop
        ]

        mock_hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)

        # Setup integration
        result = await async_setup_entry(mock_hass, mock_config_entry)
        assert result is True

        # Get coordinator
        coordinator = mock_hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]
        assert isinstance(coordinator, EarlyAPICoordinator)

        # Verify activities were fetched
        assert len(coordinator.get_all_activities()) == 2
        assert coordinator.get_all_activities()["activity_1"] == "Working"

        # Start tracking
        await coordinator.start_tracking("activity_1")

        # Stop tracking
        await coordinator.stop_tracking()

    @pytest.mark.asyncio
    async def test_full_bluetooth_integration_workflow(
        self, mock_hass, mock_bluetooth_config_entry_with_api,
        mock_api_token_response, mock_activities_response
    ):
        """Test Bluetooth device with API integration workflow."""
        # Mock API responses
        token_response = MagicMock()
        token_response.json.return_value = mock_api_token_response
        token_response.status_code = 200
        token_response.raise_for_status = MagicMock()

        activities_response = MagicMock()
        activities_response.json.return_value = mock_activities_response
        activities_response.status_code = 200
        activities_response.raise_for_status = MagicMock()

        mock_hass.async_add_executor_job.side_effect = [
            token_response,
            activities_response,
        ]

        mock_hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)

        # Setup integration
        result = await async_setup_entry(mock_hass, mock_bluetooth_config_entry_with_api)
        assert result is True

        # Verify entry exists in hass.data
        assert DOMAIN in mock_hass.data
        assert mock_bluetooth_config_entry_with_api.entry_id in mock_hass.data[DOMAIN]

    @pytest.mark.asyncio
    async def test_setup_unload_reload_cycle(self, mock_hass, mock_config_entry):
        """Test setup, unload, and reload cycle."""
        mock_hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
        mock_hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

        # Setup
        result = await async_setup_entry(mock_hass, mock_config_entry)
        assert result is True
        assert mock_config_entry.entry_id in mock_hass.data[DOMAIN]

        # Unload
        result = await async_unload_entry(mock_hass, mock_config_entry)
        assert result is True
        assert mock_config_entry.entry_id not in mock_hass.data[DOMAIN]

        # Reload
        result = await async_setup_entry(mock_hass, mock_config_entry)
        assert result is True
        assert mock_config_entry.entry_id in mock_hass.data[DOMAIN]

    @pytest.mark.asyncio
    async def test_multiple_config_entries(self, mock_hass):
        """Test multiple config entries can coexist."""
        entry1 = ConfigEntry(
            version=1,
            domain=DOMAIN,
            title="EARLY Account 1",
            data={
                CONF_API_KEY: "key1",
                CONF_API_SECRET: "secret1",
            },
            source="user",
            entry_id="entry1",
            unique_id="unique1",
        )

        entry2 = ConfigEntry(
            version=1,
            domain=DOMAIN,
            title="EARLY Account 2",
            data={
                CONF_API_KEY: "key2",
                CONF_API_SECRET: "secret2",
            },
            source="user",
            entry_id="entry2",
            unique_id="unique2",
        )

        mock_hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)

        # Setup both entries
        result1 = await async_setup_entry(mock_hass, entry1)
        result2 = await async_setup_entry(mock_hass, entry2)

        assert result1 is True
        assert result2 is True
        assert "entry1" in mock_hass.data[DOMAIN]
        assert "entry2" in mock_hass.data[DOMAIN]


class TestErrorRecovery:
    """Test error recovery scenarios."""

    @pytest.mark.asyncio
    async def test_coordinator_token_expiry_and_renewal(
        self, mock_hass, mock_api_token_response, mock_tracking_response_idle
    ):
        """Test coordinator handles token expiry and renews."""
        coordinator = EarlyAPICoordinator(mock_hass, "key", "secret")

        # First call - get token
        token_response = MagicMock()
        token_response.json.return_value = mock_api_token_response
        token_response.raise_for_status = MagicMock()

        # Second call - 401 unauthorized
        tracking_401 = MagicMock()
        tracking_401.status_code = 401

        # Third call - new token
        new_token_response = MagicMock()
        new_token_response.json.return_value = {"token": "new_token"}
        new_token_response.raise_for_status = MagicMock()

        # Fourth call - success with new token
        tracking_success = MagicMock()
        tracking_success.status_code = 200
        tracking_success.json.return_value = mock_tracking_response_idle
        tracking_success.raise_for_status = MagicMock()

        mock_hass.async_add_executor_job.side_effect = [
            token_response,  # Initial token
            tracking_401,  # 401 error
            new_token_response,  # Renew token
            tracking_success,  # Success with new token
        ]

        await coordinator.async_update()

        assert coordinator._token == "new_token"
        assert coordinator.tracking_data == mock_tracking_response_idle

    @pytest.mark.asyncio
    async def test_network_error_recovery(
        self, mock_hass, mock_api_token_response, mock_tracking_response_idle
    ):
        """Test recovery from network errors."""
        coordinator = EarlyAPICoordinator(mock_hass, "key", "secret")

        # First update - network error
        mock_hass.async_add_executor_job.side_effect = Exception("Network error")

        await coordinator.async_update()
        assert coordinator.tracking_data is None

        # Second update - success
        token_response = MagicMock()
        token_response.json.return_value = mock_api_token_response
        token_response.raise_for_status = MagicMock()

        tracking_response = MagicMock()
        tracking_response.status_code = 200
        tracking_response.json.return_value = mock_tracking_response_idle
        tracking_response.raise_for_status = MagicMock()

        mock_hass.async_add_executor_job.side_effect = [
            token_response,
            tracking_response,
        ]

        await coordinator.async_update()
        assert coordinator.tracking_data == mock_tracking_response_idle


class TestDeviceSideMappingIntegration:
    """Test device side mapping integration."""

    @pytest.mark.asyncio
    async def test_orientation_to_activity_mapping_workflow(
        self, mock_hass, mock_api_token_response, mock_activities_response
    ):
        """Test full workflow of orientation to activity mapping."""
        coordinator = EarlyAPICoordinator(mock_hass, "key", "secret")

        token_response = MagicMock()
        token_response.json.return_value = mock_api_token_response
        token_response.raise_for_status = MagicMock()

        activities_response = MagicMock()
        activities_response.json.return_value = mock_activities_response
        activities_response.raise_for_status = MagicMock()

        mock_hass.async_add_executor_job.side_effect = [
            token_response,
            activities_response,
        ]

        await coordinator._fetch_activities()

        # Verify mappings
        assert coordinator.get_activity_by_device_side(1) == "Working"
        assert coordinator.get_activity_by_device_side(2) == "Meeting"
        assert coordinator.get_activity_by_device_side(99) is None

    @pytest.mark.asyncio
    async def test_activities_update_refreshes_mappings(
        self, mock_hass, mock_api_token_response
    ):
        """Test that fetching activities updates device side mappings."""
        coordinator = EarlyAPICoordinator(mock_hass, "key", "secret")

        # Initial activities
        token_response = MagicMock()
        token_response.json.return_value = mock_api_token_response
        token_response.raise_for_status = MagicMock()

        activities_v1 = MagicMock()
        activities_v1.json.return_value = {
            "activities": [
                {"id": "1", "name": "Work", "deviceSide": 1},
            ]
        }
        activities_v1.raise_for_status = MagicMock()

        mock_hass.async_add_executor_job.side_effect = [
            token_response,
            activities_v1,
        ]

        await coordinator._fetch_activities()
        assert coordinator.get_activity_by_device_side(1) == "Work"
        assert coordinator.get_activity_by_device_side(2) is None

        # Updated activities
        activities_v2 = MagicMock()
        activities_v2.json.return_value = {
            "activities": [
                {"id": "1", "name": "Work", "deviceSide": 1},
                {"id": "2", "name": "Play", "deviceSide": 2},
            ]
        }
        activities_v2.raise_for_status = MagicMock()

        mock_hass.async_add_executor_job.side_effect = [
            token_response,
            activities_v2,
        ]

        await coordinator._fetch_activities()
        assert coordinator.get_activity_by_device_side(1) == "Work"
        assert coordinator.get_activity_by_device_side(2) == "Play"


class TestConcurrentOperations:
    """Test concurrent operations."""

    @pytest.mark.asyncio
    async def test_concurrent_coordinator_updates(
        self, mock_hass, mock_api_token_response, mock_tracking_response_idle
    ):
        """Test coordinator handles concurrent update requests."""
        coordinator = EarlyAPICoordinator(mock_hass, "key", "secret")

        token_response = MagicMock()
        token_response.json.return_value = mock_api_token_response
        token_response.raise_for_status = MagicMock()

        tracking_response = MagicMock()
        tracking_response.status_code = 200
        tracking_response.json.return_value = mock_tracking_response_idle
        tracking_response.raise_for_status = MagicMock()

        # Set up multiple responses
        mock_hass.async_add_executor_job.side_effect = [
            token_response,
            tracking_response,
            token_response,
            tracking_response,
        ]

        # Make concurrent calls (throttle should prevent double execution)
        await coordinator.async_update()
        await coordinator.async_update()

        # Due to throttling, should have fetched only once
        assert coordinator.tracking_data == mock_tracking_response_idle
