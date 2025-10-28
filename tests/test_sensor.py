"""Test the EARLY sensor platform."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import timedelta

from custom_components.early.sensor import (
    EarlyAPICoordinator,
    EarlyCurrentTrackingSensor,
    async_setup_entry,
)
from custom_components.early.const import DOMAIN


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
    async def test_async_update_failure(self, mock_hass, mock_api_token_response):
        """Test update failure."""
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")

        # Mock token request
        token_response = MagicMock()
        token_response.json.return_value = mock_api_token_response
        token_response.raise_for_status = MagicMock()

        # Mock tracking request failure
        mock_hass.async_add_executor_job.side_effect = [
            token_response,
            Exception("Network error"),
        ]

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


class TestSensorPlatformSetup:
    """Test the sensor platform setup."""

    @pytest.mark.asyncio
    async def test_async_setup_entry_api(self, mock_hass, mock_config_entry):
        """Test setting up API sensor entry."""
        mock_hass.data[DOMAIN] = {mock_config_entry.entry_id: {}}
        async_add_entities = AsyncMock()

        with patch(
            "custom_components.early.sensor.EarlyAPICoordinator.async_update"
        ) as mock_update:
            mock_update.return_value = None

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
