"""Common test fixtures for EARLY integration."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from custom_components.early.const import DOMAIN, CONF_API_SECRET


@pytest.fixture
def mock_hass():
    """Return a mock Home Assistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.data = {}
    hass.config_entries = MagicMock()
    hass.async_create_task = AsyncMock()
    hass.async_add_executor_job = AsyncMock()
    return hass


@pytest.fixture
def mock_config_entry():
    """Return a mock config entry."""
    return ConfigEntry(
        version=1,
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


@pytest.fixture
def mock_bluetooth_config_entry():
    """Return a mock Bluetooth config entry."""
    return ConfigEntry(
        version=1,
        domain=DOMAIN,
        title="EARLY ZEI Tracker",
        data={"address": "AA:BB:CC:DD:EE:FF"},
        source="bluetooth",
        entry_id="test_bt_entry_id",
        unique_id="AA:BB:CC:DD:EE:FF",
    )


@pytest.fixture
def mock_api_token_response():
    """Return a mock API token response."""
    return {
        "token": "mock_bearer_token"
    }


@pytest.fixture
def mock_activities_response():
    """Return a mock activities API response."""
    return {
        "activities": [
            {
                "id": "activity_1",
                "name": "Working",
                "color": "#FF0000",
            },
            {
                "id": "activity_2",
                "name": "Meeting",
                "color": "#00FF00",
            },
        ]
    }


@pytest.fixture
def mock_tracking_response_active():
    """Return a mock tracking response with active tracking."""
    return {
        "currentTracking": {
            "activity": {
                "id": "activity_1",
            },
            "startedAt": "2025-01-15T10:30:00.000Z",
            "note": {
                "text": "Working on tests"
            }
        }
    }


@pytest.fixture
def mock_tracking_response_idle():
    """Return a mock tracking response with no active tracking."""
    return {
        "currentTracking": None
    }


@pytest.fixture
def mock_ble_device():
    """Return a mock BLE device."""
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
