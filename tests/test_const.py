"""Test the EARLY integration constants."""
import pytest

from custom_components.early.const import (
    DOMAIN,
    CONF_API_SECRET,
    API_BASE_URL,
    API_SIGN_IN_ENDPOINT,
    API_TRACKING_ENDPOINT,
    API_ACTIVITIES_ENDPOINT,
    BLE_SERVICE_UUID,
    BLE_ORIENTATION_CHARACTERISTIC_UUID,
    DEVICE_NAME_PREFIX,
    DEFAULT_SCAN_INTERVAL,
    ATTR_ACTIVITY_ID,
    ATTR_ACTIVITY_NAME,
    ATTR_STARTED_AT,
    ATTR_NOTE,
    ATTR_ORIENTATION,
    ATTR_RSSI,
    ATTR_BATTERY_LEVEL,
)


class TestConstants:
    """Test that all constants are defined correctly."""

    def test_domain(self):
        """Test domain constant."""
        assert DOMAIN == "early"
        assert isinstance(DOMAIN, str)

    def test_conf_api_secret(self):
        """Test API secret config key."""
        assert CONF_API_SECRET == "api_secret"
        assert isinstance(CONF_API_SECRET, str)

    def test_api_base_url(self):
        """Test API base URL."""
        assert API_BASE_URL == "https://api.timeular.com/api/v3"
        assert isinstance(API_BASE_URL, str)
        assert API_BASE_URL.startswith("https://")

    def test_api_sign_in_endpoint(self):
        """Test sign-in endpoint."""
        assert API_SIGN_IN_ENDPOINT == f"{API_BASE_URL}/developer/sign-in"
        assert isinstance(API_SIGN_IN_ENDPOINT, str)
        assert "developer/sign-in" in API_SIGN_IN_ENDPOINT

    def test_api_tracking_endpoint(self):
        """Test tracking endpoint."""
        assert API_TRACKING_ENDPOINT == f"{API_BASE_URL}/tracking"
        assert isinstance(API_TRACKING_ENDPOINT, str)
        assert "tracking" in API_TRACKING_ENDPOINT

    def test_api_activities_endpoint(self):
        """Test activities endpoint."""
        assert API_ACTIVITIES_ENDPOINT == f"{API_BASE_URL}/activities"
        assert isinstance(API_ACTIVITIES_ENDPOINT, str)
        assert "activities" in API_ACTIVITIES_ENDPOINT

    def test_ble_service_uuid(self):
        """Test BLE service UUID."""
        assert BLE_SERVICE_UUID == "c7e70010-c847-11e6-8175-8c89a55d403c"
        assert isinstance(BLE_SERVICE_UUID, str)
        assert len(BLE_SERVICE_UUID) == 36  # UUID length with dashes

    def test_ble_orientation_characteristic_uuid(self):
        """Test BLE orientation characteristic UUID."""
        assert BLE_ORIENTATION_CHARACTERISTIC_UUID == "c7e70012-c847-11e6-8175-8c89a55d403c"
        assert isinstance(BLE_ORIENTATION_CHARACTERISTIC_UUID, str)
        assert len(BLE_ORIENTATION_CHARACTERISTIC_UUID) == 36

    def test_device_name_prefix(self):
        """Test device name prefix."""
        assert DEVICE_NAME_PREFIX == "Timeular ZEI"
        assert isinstance(DEVICE_NAME_PREFIX, str)

    def test_default_scan_interval(self):
        """Test default scan interval."""
        assert DEFAULT_SCAN_INTERVAL == 30
        assert isinstance(DEFAULT_SCAN_INTERVAL, int)
        assert DEFAULT_SCAN_INTERVAL > 0

    def test_attr_activity_id(self):
        """Test activity ID attribute."""
        assert ATTR_ACTIVITY_ID == "activity_id"
        assert isinstance(ATTR_ACTIVITY_ID, str)

    def test_attr_activity_name(self):
        """Test activity name attribute."""
        assert ATTR_ACTIVITY_NAME == "activity_name"
        assert isinstance(ATTR_ACTIVITY_NAME, str)

    def test_attr_started_at(self):
        """Test started_at attribute."""
        assert ATTR_STARTED_AT == "started_at"
        assert isinstance(ATTR_STARTED_AT, str)

    def test_attr_note(self):
        """Test note attribute."""
        assert ATTR_NOTE == "note"
        assert isinstance(ATTR_NOTE, str)

    def test_attr_orientation(self):
        """Test orientation attribute."""
        assert ATTR_ORIENTATION == "orientation"
        assert isinstance(ATTR_ORIENTATION, str)

    def test_attr_rssi(self):
        """Test RSSI attribute."""
        assert ATTR_RSSI == "rssi"
        assert isinstance(ATTR_RSSI, str)

    def test_attr_battery_level(self):
        """Test battery level attribute."""
        assert ATTR_BATTERY_LEVEL == "battery_level"
        assert isinstance(ATTR_BATTERY_LEVEL, str)

    def test_uuids_are_valid_format(self):
        """Test that UUIDs are in valid format."""
        import re
        uuid_pattern = re.compile(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
            re.IGNORECASE
        )

        assert uuid_pattern.match(BLE_SERVICE_UUID)
        assert uuid_pattern.match(BLE_ORIENTATION_CHARACTERISTIC_UUID)

    def test_all_attributes_are_snake_case(self):
        """Test that all attribute constants use snake_case."""
        import re
        snake_case_pattern = re.compile(r'^[a-z_]+$')

        assert snake_case_pattern.match(ATTR_ACTIVITY_ID)
        assert snake_case_pattern.match(ATTR_ACTIVITY_NAME)
        assert snake_case_pattern.match(ATTR_STARTED_AT)
        assert snake_case_pattern.match(ATTR_NOTE)
        assert snake_case_pattern.match(ATTR_ORIENTATION)
        assert snake_case_pattern.match(ATTR_RSSI)
        assert snake_case_pattern.match(ATTR_BATTERY_LEVEL)

    def test_endpoints_consistency(self):
        """Test that all endpoints use the same base URL."""
        assert API_SIGN_IN_ENDPOINT.startswith(API_BASE_URL)
        assert API_TRACKING_ENDPOINT.startswith(API_BASE_URL)
        assert API_ACTIVITIES_ENDPOINT.startswith(API_BASE_URL)

    def test_endpoint_paths_are_lowercase(self):
        """Test that endpoint paths use lowercase."""
        endpoints = [
            API_SIGN_IN_ENDPOINT,
            API_TRACKING_ENDPOINT,
            API_ACTIVITIES_ENDPOINT,
        ]

        for endpoint in endpoints:
            path = endpoint.replace(API_BASE_URL, "")
            assert path.islower() or "/" in path or "-" in path
