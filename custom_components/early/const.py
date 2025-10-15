"""Constants for the EARLY (Timeular) integration."""

DOMAIN = "early"
CONF_API_KEY = "api_key"
CONF_API_SECRET = "api_secret"

# API Configuration
API_BASE_URL = "https://api.timeular.com/api/v3"
API_SIGN_IN_ENDPOINT = f"{API_BASE_URL}/developer/sign-in"
API_TRACKING_ENDPOINT = f"{API_BASE_URL}/tracking"
API_ACTIVITIES_ENDPOINT = f"{API_BASE_URL}/activities"

# Bluetooth Configuration
BLE_SERVICE_UUID = "c7e70010-c847-11e6-8175-8c89a55d403c"
BLE_ORIENTATION_CHARACTERISTIC_UUID = "c7e70012-c847-11e6-8175-8c89a55d403c"
DEVICE_NAME_PREFIX = "Timeular ZEI"

# Update interval (in seconds)
DEFAULT_SCAN_INTERVAL = 30

# Sensor attributes
ATTR_ACTIVITY_ID = "activity_id"
ATTR_ACTIVITY_NAME = "activity_name"
ATTR_STARTED_AT = "started_at"
ATTR_NOTE = "note"
ATTR_ORIENTATION = "orientation"
ATTR_RSSI = "rssi"
ATTR_BATTERY_LEVEL = "battery_level"
