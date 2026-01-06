"""Test the EARLY Bluetooth sensor platform."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import SIGNAL_STRENGTH_DECIBELS_MILLIWATT

from custom_components.early.bluetooth_sensor import (
    EarlyTrackerOrientationSensor,
    EarlyTrackerRSSISensor,
    EarlyTrackerCurrentActivitySensor,
    async_setup_bluetooth_entry,
)
from custom_components.early.bluetooth import EarlyBluetoothDevice
from custom_components.early.sensor import EarlyAPICoordinator
from custom_components.early.const import DOMAIN


@pytest.fixture
def mock_bluetooth_device_for_sensor(mock_hass, mock_ble_device):
    """Return a mock Bluetooth device for sensor tests."""
    service_info = MagicMock()
    service_info.name = "Timeular ZEI"
    service_info.address = "AA:BB:CC:DD:EE:FF"
    service_info.rssi = -50
    service_info.device = mock_ble_device

    device = EarlyBluetoothDevice(mock_hass, mock_ble_device, service_info)
    device._orientation = 3
    return device


@pytest.fixture
def mock_config_entry_bt():
    """Return a mock Bluetooth config entry."""
    entry = MagicMock()
    entry.entry_id = "test_bt_entry"
    entry.data = {"address": "AA:BB:CC:DD:EE:FF"}
    return entry


class TestEarlyTrackerOrientationSensor:
    """Test the EarlyTrackerOrientationSensor class."""

    def test_sensor_initialization(self, mock_bluetooth_device_for_sensor, mock_config_entry_bt):
        """Test sensor initialization."""
        sensor = EarlyTrackerOrientationSensor(
            mock_bluetooth_device_for_sensor, mock_config_entry_bt
        )

        assert sensor._device == mock_bluetooth_device_for_sensor
        assert sensor._attr_name == "Timeular ZEI Orientation"
        assert sensor._attr_unique_id == "AA:BB:CC:DD:EE:FF_orientation"

    def test_sensor_device_info(self, mock_bluetooth_device_for_sensor, mock_config_entry_bt):
        """Test sensor device info."""
        sensor = EarlyTrackerOrientationSensor(
            mock_bluetooth_device_for_sensor, mock_config_entry_bt
        )

        device_info = sensor.device_info

        assert device_info["identifiers"] == {(DOMAIN, "AA:BB:CC:DD:EE:FF")}
        assert device_info["name"] == "Timeular ZEI"
        assert device_info["manufacturer"] == "Timeular"
        assert device_info["model"] == "ZEI Tracker"

    def test_sensor_native_value(self, mock_bluetooth_device_for_sensor, mock_config_entry_bt):
        """Test sensor native value."""
        sensor = EarlyTrackerOrientationSensor(
            mock_bluetooth_device_for_sensor, mock_config_entry_bt
        )

        assert sensor.native_value == 3

    def test_sensor_attributes(self, mock_bluetooth_device_for_sensor, mock_config_entry_bt):
        """Test sensor attributes."""
        sensor = EarlyTrackerOrientationSensor(
            mock_bluetooth_device_for_sensor, mock_config_entry_bt
        )

        attributes = sensor.extra_state_attributes

        assert attributes["orientation"] == 3
        assert attributes["device_address"] == "AA:BB:CC:DD:EE:FF"

    def test_sensor_available_connected(
        self, mock_bluetooth_device_for_sensor, mock_config_entry_bt
    ):
        """Test sensor availability when connected."""
        mock_bluetooth_device_for_sensor._client = MagicMock()
        mock_bluetooth_device_for_sensor._client.is_connected = True

        sensor = EarlyTrackerOrientationSensor(
            mock_bluetooth_device_for_sensor, mock_config_entry_bt
        )

        assert sensor.available is True

    def test_sensor_available_disconnected(
        self, mock_bluetooth_device_for_sensor, mock_config_entry_bt
    ):
        """Test sensor availability when disconnected."""
        mock_bluetooth_device_for_sensor._client = None

        sensor = EarlyTrackerOrientationSensor(
            mock_bluetooth_device_for_sensor, mock_config_entry_bt
        )

        assert sensor.available is False

    def test_sensor_handle_orientation_change(
        self, mock_bluetooth_device_for_sensor, mock_config_entry_bt
    ):
        """Test handling orientation change."""
        sensor = EarlyTrackerOrientationSensor(
            mock_bluetooth_device_for_sensor, mock_config_entry_bt
        )
        sensor.async_write_ha_state = MagicMock()

        sensor._handle_orientation_change()

        sensor.async_write_ha_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_sensor_will_remove_from_hass(
        self, mock_bluetooth_device_for_sensor, mock_config_entry_bt
    ):
        """Test sensor removal."""
        sensor = EarlyTrackerOrientationSensor(
            mock_bluetooth_device_for_sensor, mock_config_entry_bt
        )
        mock_bluetooth_device_for_sensor.unregister_callback = MagicMock()

        await sensor.async_will_remove_from_hass()

        mock_bluetooth_device_for_sensor.unregister_callback.assert_called_once()

    def test_sensor_callback_registration(
        self, mock_bluetooth_device_for_sensor, mock_config_entry_bt
    ):
        """Test callback is registered during initialization."""
        mock_bluetooth_device_for_sensor.register_callback = MagicMock()

        sensor = EarlyTrackerOrientationSensor(
            mock_bluetooth_device_for_sensor, mock_config_entry_bt
        )

        mock_bluetooth_device_for_sensor.register_callback.assert_called_once()


class TestEarlyTrackerRSSISensor:
    """Test the EarlyTrackerRSSISensor class."""

    @pytest.fixture
    def mock_bluetooth_device(self, mock_hass, mock_ble_device):
        """Return a mock Bluetooth device."""
        service_info = MagicMock()
        service_info.name = "Timeular ZEI"
        service_info.address = "AA:BB:CC:DD:EE:FF"
        service_info.rssi = -50
        service_info.device = mock_ble_device

        device = EarlyBluetoothDevice(mock_hass, mock_ble_device, service_info)
        return device

    @pytest.fixture
    def mock_config_entry_bt(self):
        """Return a mock Bluetooth config entry."""
        entry = MagicMock()
        entry.entry_id = "test_bt_entry"
        entry.data = {"address": "AA:BB:CC:DD:EE:FF"}
        return entry

    def test_sensor_initialization(self, mock_bluetooth_device, mock_config_entry_bt):
        """Test sensor initialization."""
        sensor = EarlyTrackerRSSISensor(mock_bluetooth_device, mock_config_entry_bt)

        assert sensor._device == mock_bluetooth_device
        assert sensor._attr_name == "Timeular ZEI Signal Strength"
        assert sensor._attr_unique_id == "AA:BB:CC:DD:EE:FF_rssi"
        assert sensor._attr_device_class == SensorDeviceClass.SIGNAL_STRENGTH
        assert (
            sensor._attr_native_unit_of_measurement
            == SIGNAL_STRENGTH_DECIBELS_MILLIWATT
        )
        assert sensor._attr_entity_registry_enabled_default is False

    def test_sensor_device_info(self, mock_bluetooth_device, mock_config_entry_bt):
        """Test sensor device info."""
        sensor = EarlyTrackerRSSISensor(mock_bluetooth_device, mock_config_entry_bt)

        device_info = sensor.device_info

        assert device_info["identifiers"] == {(DOMAIN, "AA:BB:CC:DD:EE:FF")}
        assert device_info["name"] == "Timeular ZEI"
        assert device_info["manufacturer"] == "Timeular"
        assert device_info["model"] == "ZEI Tracker"

    def test_sensor_native_value(self, mock_bluetooth_device, mock_config_entry_bt):
        """Test sensor native value."""
        sensor = EarlyTrackerRSSISensor(mock_bluetooth_device, mock_config_entry_bt)

        assert sensor.native_value == -50

    def test_sensor_available_connected(
        self, mock_bluetooth_device, mock_config_entry_bt
    ):
        """Test sensor availability when connected."""
        mock_bluetooth_device._client = MagicMock()
        mock_bluetooth_device._client.is_connected = True

        sensor = EarlyTrackerRSSISensor(mock_bluetooth_device, mock_config_entry_bt)

        assert sensor.available is True

    def test_sensor_available_disconnected(
        self, mock_bluetooth_device, mock_config_entry_bt
    ):
        """Test sensor availability when disconnected."""
        mock_bluetooth_device._client = None

        sensor = EarlyTrackerRSSISensor(mock_bluetooth_device, mock_config_entry_bt)

        assert sensor.available is False


class TestBluetoothSensorPlatformSetup:
    """Test the Bluetooth sensor platform setup."""

    @pytest.mark.asyncio
    async def test_async_setup_bluetooth_entry_success(self, mock_hass):
        """Test successful Bluetooth sensor setup."""
        config_entry = MagicMock()
        config_entry.entry_id = "test_bt_entry"
        config_entry.data = {"address": "AA:BB:CC:DD:EE:FF"}

        mock_hass.data[DOMAIN] = {
            config_entry.entry_id: {"bluetooth_devices": {}}
        }

        service_info = MagicMock()
        service_info.name = "Timeular ZEI"
        service_info.address = "AA:BB:CC:DD:EE:FF"
        service_info.device = MagicMock()
        service_info.device.name = "Timeular ZEI"
        service_info.device.address = "AA:BB:CC:DD:EE:FF"

        async_add_entities = AsyncMock()

        with patch(
            "custom_components.early.bluetooth_sensor.bluetooth.async_last_service_info",
            return_value=service_info,
        ):
            with patch(
                "custom_components.early.bluetooth_sensor.EarlyBluetoothDevice.connect",
                return_value=True,
            ):
                await async_setup_bluetooth_entry(
                    mock_hass, config_entry, async_add_entities
                )

                async_add_entities.assert_called_once()
                entities = async_add_entities.call_args[0][0]
                assert len(entities) == 2
                assert isinstance(entities[0], EarlyTrackerOrientationSensor)
                assert isinstance(entities[1], EarlyTrackerRSSISensor)

    @pytest.mark.asyncio
    async def test_async_setup_bluetooth_entry_no_service_info(self, mock_hass):
        """Test setup fails when service info not found."""
        config_entry = MagicMock()
        config_entry.entry_id = "test_bt_entry"
        config_entry.data = {"address": "AA:BB:CC:DD:EE:FF"}

        async_add_entities = AsyncMock()

        with patch(
            "custom_components.early.bluetooth_sensor.bluetooth.async_last_service_info",
            return_value=None,
        ):
            await async_setup_bluetooth_entry(
                mock_hass, config_entry, async_add_entities
            )

            async_add_entities.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_setup_bluetooth_entry_connection_failed(self, mock_hass):
        """Test setup fails when connection fails."""
        config_entry = MagicMock()
        config_entry.entry_id = "test_bt_entry"
        config_entry.data = {"address": "AA:BB:CC:DD:EE:FF"}

        mock_hass.data[DOMAIN] = {
            config_entry.entry_id: {"bluetooth_devices": {}}
        }

        service_info = MagicMock()
        service_info.name = "Timeular ZEI"
        service_info.address = "AA:BB:CC:DD:EE:FF"
        service_info.device = MagicMock()

        async_add_entities = AsyncMock()

        with patch(
            "custom_components.early.bluetooth_sensor.bluetooth.async_last_service_info",
            return_value=service_info,
        ):
            with patch(
                "custom_components.early.bluetooth_sensor.EarlyBluetoothDevice.connect",
                return_value=False,
            ):
                await async_setup_bluetooth_entry(
                    mock_hass, config_entry, async_add_entities
                )

                async_add_entities.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_setup_bluetooth_entry_with_api_credentials(
        self, mock_hass, mock_api_token_response, mock_activities_response
    ):
        """Test setup with API credentials creates current activity sensor."""
        config_entry = MagicMock()
        config_entry.entry_id = "test_bt_entry"
        config_entry.data = {
            "address": "AA:BB:CC:DD:EE:FF",
            "api_key": "test_key",
            "api_secret": "test_secret",
        }

        mock_hass.data[DOMAIN] = {
            config_entry.entry_id: {"bluetooth_devices": {}}
        }

        service_info = MagicMock()
        service_info.name = "Timeular ZEI"
        service_info.address = "AA:BB:CC:DD:EE:FF"
        service_info.device = MagicMock()

        async_add_entities = AsyncMock()

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

        with patch(
            "custom_components.early.bluetooth_sensor.bluetooth.async_last_service_info",
            return_value=service_info,
        ):
            with patch(
                "custom_components.early.bluetooth_sensor.EarlyBluetoothDevice.connect",
                return_value=True,
            ):
                await async_setup_bluetooth_entry(
                    mock_hass, config_entry, async_add_entities
                )

                async_add_entities.assert_called_once()
                entities = async_add_entities.call_args[0][0]
                assert len(entities) == 3  # Orientation, RSSI, and Current Activity
                assert isinstance(entities[0], EarlyTrackerOrientationSensor)
                assert isinstance(entities[1], EarlyTrackerRSSISensor)
                assert isinstance(entities[2], EarlyTrackerCurrentActivitySensor)


class TestEarlyTrackerCurrentActivitySensor:
    """Test the EarlyTrackerCurrentActivitySensor class."""

    @pytest.fixture
    def mock_bluetooth_device(self, mock_hass, mock_ble_device):
        """Return a mock Bluetooth device."""
        service_info = MagicMock()
        service_info.name = "Timeular ZEI"
        service_info.address = "AA:BB:CC:DD:EE:FF"
        service_info.rssi = -50
        service_info.device = mock_ble_device

        device = EarlyBluetoothDevice(mock_hass, mock_ble_device, service_info)
        device._orientation = 1
        return device

    @pytest.fixture
    def mock_coordinator(self, mock_hass):
        """Return a mock coordinator."""
        coordinator = EarlyAPICoordinator(mock_hass, "test_key", "test_secret")
        coordinator._device_side_mapping = {
            1: "Working",
            2: "Meeting",
            3: "Break",
        }
        return coordinator

    @pytest.fixture
    def mock_config_entry_bt(self):
        """Return a mock Bluetooth config entry."""
        entry = MagicMock()
        entry.entry_id = "test_bt_entry"
        entry.data = {"address": "AA:BB:CC:DD:EE:FF"}
        return entry

    def test_sensor_initialization(
        self, mock_bluetooth_device, mock_config_entry_bt, mock_coordinator
    ):
        """Test sensor initialization."""
        sensor = EarlyTrackerCurrentActivitySensor(
            mock_bluetooth_device, mock_config_entry_bt, mock_coordinator
        )

        assert sensor._device == mock_bluetooth_device
        assert sensor._coordinator == mock_coordinator
        assert sensor._attr_name == "Timeular ZEI Current Activity"
        assert sensor._attr_unique_id == "AA:BB:CC:DD:EE:FF_current_activity"

    def test_sensor_device_info(
        self, mock_bluetooth_device, mock_config_entry_bt, mock_coordinator
    ):
        """Test sensor device info."""
        sensor = EarlyTrackerCurrentActivitySensor(
            mock_bluetooth_device, mock_config_entry_bt, mock_coordinator
        )

        device_info = sensor.device_info

        assert device_info["identifiers"] == {(DOMAIN, "AA:BB:CC:DD:EE:FF")}
        assert device_info["name"] == "Timeular ZEI"
        assert device_info["manufacturer"] == "Timeular"
        assert device_info["model"] == "ZEI Tracker"

    def test_sensor_native_value_with_activity(
        self, mock_bluetooth_device, mock_config_entry_bt, mock_coordinator
    ):
        """Test sensor native value when orientation has assigned activity."""
        sensor = EarlyTrackerCurrentActivitySensor(
            mock_bluetooth_device, mock_config_entry_bt, mock_coordinator
        )

        assert sensor.native_value == "Working"

    def test_sensor_native_value_idle(
        self, mock_bluetooth_device, mock_config_entry_bt, mock_coordinator
    ):
        """Test sensor native value when orientation has no assigned activity."""
        mock_bluetooth_device._orientation = 5  # No activity assigned to side 5
        sensor = EarlyTrackerCurrentActivitySensor(
            mock_bluetooth_device, mock_config_entry_bt, mock_coordinator
        )

        assert sensor.native_value == "idle"

    def test_sensor_native_value_unknown(
        self, mock_bluetooth_device, mock_config_entry_bt, mock_coordinator
    ):
        """Test sensor native value when orientation is None."""
        mock_bluetooth_device._orientation = None
        sensor = EarlyTrackerCurrentActivitySensor(
            mock_bluetooth_device, mock_config_entry_bt, mock_coordinator
        )

        assert sensor.native_value == "unknown"

    def test_sensor_attributes_with_activity(
        self, mock_bluetooth_device, mock_config_entry_bt, mock_coordinator
    ):
        """Test sensor attributes when activity is assigned."""
        sensor = EarlyTrackerCurrentActivitySensor(
            mock_bluetooth_device, mock_config_entry_bt, mock_coordinator
        )

        attributes = sensor.extra_state_attributes

        assert attributes["orientation"] == 1
        assert attributes["device_address"] == "AA:BB:CC:DD:EE:FF"
        assert attributes["activity_name"] == "Working"

    def test_sensor_attributes_without_activity(
        self, mock_bluetooth_device, mock_config_entry_bt, mock_coordinator
    ):
        """Test sensor attributes when no activity assigned."""
        mock_bluetooth_device._orientation = 5  # No activity on side 5
        sensor = EarlyTrackerCurrentActivitySensor(
            mock_bluetooth_device, mock_config_entry_bt, mock_coordinator
        )

        attributes = sensor.extra_state_attributes

        assert attributes["orientation"] == 5
        assert attributes["device_address"] == "AA:BB:CC:DD:EE:FF"
        assert "activity_name" not in attributes

    def test_sensor_available_connected(
        self, mock_bluetooth_device, mock_config_entry_bt, mock_coordinator
    ):
        """Test sensor availability when connected."""
        mock_bluetooth_device._client = MagicMock()
        mock_bluetooth_device._client.is_connected = True

        sensor = EarlyTrackerCurrentActivitySensor(
            mock_bluetooth_device, mock_config_entry_bt, mock_coordinator
        )

        assert sensor.available is True

    def test_sensor_available_disconnected(
        self, mock_bluetooth_device, mock_config_entry_bt, mock_coordinator
    ):
        """Test sensor availability when disconnected."""
        mock_bluetooth_device._client = None

        sensor = EarlyTrackerCurrentActivitySensor(
            mock_bluetooth_device, mock_config_entry_bt, mock_coordinator
        )

        assert sensor.available is False

    def test_sensor_handle_orientation_change(
        self, mock_bluetooth_device, mock_config_entry_bt, mock_coordinator
    ):
        """Test handling orientation change."""
        sensor = EarlyTrackerCurrentActivitySensor(
            mock_bluetooth_device, mock_config_entry_bt, mock_coordinator
        )
        sensor.async_write_ha_state = MagicMock()

        sensor._handle_orientation_change()

        sensor.async_write_ha_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_sensor_will_remove_from_hass(
        self, mock_bluetooth_device, mock_config_entry_bt, mock_coordinator
    ):
        """Test sensor removal."""
        sensor = EarlyTrackerCurrentActivitySensor(
            mock_bluetooth_device, mock_config_entry_bt, mock_coordinator
        )
        mock_bluetooth_device.unregister_callback = MagicMock()

        await sensor.async_will_remove_from_hass()

        mock_bluetooth_device.unregister_callback.assert_called_once()

    def test_sensor_callback_registration(
        self, mock_bluetooth_device, mock_config_entry_bt, mock_coordinator
    ):
        """Test callback is registered during initialization."""
        mock_bluetooth_device.register_callback = MagicMock()

        sensor = EarlyTrackerCurrentActivitySensor(
            mock_bluetooth_device, mock_config_entry_bt, mock_coordinator
        )

        mock_bluetooth_device.register_callback.assert_called_once()
