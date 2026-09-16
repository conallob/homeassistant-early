"""Common test fixtures for EARLY integration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from custom_components.early.const import CONF_API_SECRET, DOMAIN


@pytest.fixture(scope="function")
def mock_hass():
    """Return a mock Home Assistant instance.

    Function-scoped to prevent test pollution from mutable state.
    """
    hass = MagicMock(spec=HomeAssistant)
    hass.data = {}
    hass.config_entries = MagicMock()
    hass.async_create_task = AsyncMock()
    hass.async_add_executor_job = AsyncMock()
    return hass


@pytest.fixture(scope="function")
def mock_config_entry():
    """Return a mock config entry."""
    return ConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="EARLY",
        data={
            CONF_API_KEY: "test_api_key",
            CONF_API_SECRET: "test_api_secret",
        },
        source="user",
        entry_id="test_entry_id",
        unique_id="test_unique_id",
    )


@pytest.fixture(scope="function")
def mock_bluetooth_config_entry():
    """Return a mock Bluetooth config entry.

    Function-scoped as ConfigEntry may be modified in tests.
    """
    return ConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="EARLY ZEI Tracker",
        data={"address": "AA:BB:CC:DD:EE:FF"},
        source="bluetooth",
        entry_id="test_bt_entry_id",
        unique_id="AA:BB:CC:DD:EE:FF",
    )


@pytest.fixture(scope="function")
def mock_bluetooth_config_entry_with_api():
    """Return a mock Bluetooth config entry with API credentials.

    Function-scoped as ConfigEntry may be modified in tests.
    """
    return ConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="EARLY ZEI Tracker",
        data={"address": "AA:BB:CC:DD:EE:FF"},
        options={
            CONF_API_KEY: "test_api_key",
            CONF_API_SECRET: "test_api_secret",
        },
        source="bluetooth",
        entry_id="test_bt_api_entry_id",
        unique_id="AA:BB:CC:DD:EE:FF",
    )


@pytest.fixture(scope="session")
def mock_api_token_response():
    """Return a mock API token response.

    Session-scoped for performance as this is immutable data.
    """
    return {"token": "mock_bearer_token"}


@pytest.fixture(scope="session")
def mock_spaces_response_named():
    """Return a mock EARLY spaces response with real, named spaces.

    Mirrors a real account's GET /space response - used together with
    mock_activities_response_multi_space to test that activities in
    different spaces get their space name prefixed onto their display
    name (see util.build_activity_display_name).
    """
    return {
        "data": [
            {"id": "space_1", "name": "Google"},
            {"id": "space_2", "name": "Andromeda"},
        ]
    }


@pytest.fixture(scope="session")
def mock_activities_response_multi_space():
    """Return a mock activities response with the same name across two spaces.

    Mirrors the real-world case reported by a user: identically-named
    activities (e.g. "Administrivia") in more than one EARLY space
    ("folder") because they track the same categories per employer/context.
    """
    return {
        "activities": [
            {
                "id": "activity_1",
                "name": "Administrivia",
                "color": "#FF0000",
                "spaceId": "space_1",
                "deviceSide": None,
            },
            {
                "id": "activity_2",
                "name": "Administrivia",
                "color": "#00FF00",
                "spaceId": "space_2",
                "deviceSide": 1,
            },
        ]
    }


@pytest.fixture(scope="session")
def mock_activities_response():
    """Return a mock activities API response.

    Session-scoped for performance as this is immutable data.
    """
    return {
        "activities": [
            {
                "id": "activity_1",
                "name": "Working",
                "color": "#FF0000",
                "deviceSide": 1,
            },
            {
                "id": "activity_2",
                "name": "Meeting",
                "color": "#00FF00",
                "deviceSide": 2,
            },
        ]
    }


@pytest.fixture(scope="session")
def mock_activities_response_with_unassigned():
    """Return a mock activities API response with some unassigned activities.

    Session-scoped for performance as this is immutable data.
    """
    return {
        "activities": [
            {
                "id": "activity_1",
                "name": "Working",
                "color": "#FF0000",
                "deviceSide": 1,
            },
            {
                "id": "activity_2",
                "name": "Meeting",
                "color": "#00FF00",
                "deviceSide": 2,
            },
            {
                "id": "activity_3",
                "name": "Break",
                "color": "#0000FF",
                "deviceSide": None,  # Not assigned to any side
            },
        ]
    }


@pytest.fixture(scope="session")
def mock_tracking_response_active():
    """Return a mock tracking response with active tracking.

    Session-scoped for performance as this is immutable data.
    """
    return {
        "currentTracking": {
            "activity": {
                "id": "activity_1",
            },
            "startedAt": "2025-01-15T10:30:00.000Z",
            "note": {"text": "Working on tests"},
        }
    }


@pytest.fixture(scope="session")
def mock_tracking_response_idle():
    """Return a mock tracking response with no active tracking.

    Session-scoped for performance as this is immutable data.
    """
    return {"currentTracking": None}


@pytest.fixture(scope="function")
def mock_ble_device():
    """Return a mock BLE device.

    Function-scoped as mocks may have state modified by tests.
    """
    device = MagicMock()
    device.address = "AA:BB:CC:DD:EE:FF"
    device.name = "Timeular ZEI"
    device.rssi = -50
    return device


@pytest.fixture
def mock_bleak_client():
    """Return a mock Bleak client."""
    with patch("custom_components.early.bluetooth.BleakClient") as mock_client:
        client = AsyncMock()
        client.connect = AsyncMock(return_value=True)
        client.disconnect = AsyncMock()
        client.is_connected = True
        client.read_gatt_char = AsyncMock(return_value=bytearray([3]))
        client.start_notify = AsyncMock()
        mock_client.return_value = client
        yield mock_client
