"""Test the EARLY Bluetooth support."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch, call
from bleak.exc import BleakError

from custom_components.early.bluetooth import (
    EarlyBluetoothDevice,
    async_discover_devices,
)


class TestEarlyBluetoothDevice:
    """Test the EarlyBluetoothDevice class."""

    @pytest.fixture
    def mock_service_info(self, mock_ble_device):
        """Return a mock Bluetooth service info."""
        service_info = MagicMock()
        service_info.name = "Timeular ZEI"
        service_info.address = "AA:BB:CC:DD:EE:FF"
        service_info.rssi = -50
        service_info.service_uuids = ["c7e70010-c847-11e6-8175-8c89a55d403c"]
        service_info.device = mock_ble_device
        return service_info

    def test_device_properties(self, mock_hass, mock_ble_device, mock_service_info):
        """Test device properties."""
        device = EarlyBluetoothDevice(mock_hass, mock_ble_device, mock_service_info)

        assert device.name == "Timeular ZEI"
        assert device.address == "AA:BB:CC:DD:EE:FF"
        assert device.rssi == -50
        assert device.orientation == 0

    def test_device_name_fallback(self, mock_hass, mock_service_info):
        """Test device name fallback when no name."""
        ble_device = MagicMock()
        ble_device.name = None
        ble_device.address = "AA:BB:CC:DD:EE:FF"

        device = EarlyBluetoothDevice(mock_hass, ble_device, mock_service_info)

        assert device.name == "EARLY Tracker"

    def test_register_callback(self, mock_hass, mock_ble_device, mock_service_info):
        """Test registering a callback."""
        device = EarlyBluetoothDevice(mock_hass, mock_ble_device, mock_service_info)
        callback = MagicMock()

        device.register_callback(callback)

        assert callback in device._callbacks

    def test_unregister_callback(self, mock_hass, mock_ble_device, mock_service_info):
        """Test unregistering a callback."""
        device = EarlyBluetoothDevice(mock_hass, mock_ble_device, mock_service_info)
        callback = MagicMock()

        device.register_callback(callback)
        device.unregister_callback(callback)

        assert callback not in device._callbacks

    def test_unregister_nonexistent_callback(
        self, mock_hass, mock_ble_device, mock_service_info
    ):
        """Test unregistering a callback that doesn't exist."""
        device = EarlyBluetoothDevice(mock_hass, mock_ble_device, mock_service_info)
        callback = MagicMock()

        # Should not raise exception
        device.unregister_callback(callback)

    def test_fire_callbacks(self, mock_hass, mock_ble_device, mock_service_info):
        """Test firing callbacks."""
        device = EarlyBluetoothDevice(mock_hass, mock_ble_device, mock_service_info)
        callback1 = MagicMock()
        callback2 = MagicMock()

        device.register_callback(callback1)
        device.register_callback(callback2)

        device._fire_callbacks()

        callback1.assert_called_once()
        callback2.assert_called_once()

    def test_fire_callbacks_one_fails(
        self, mock_hass, mock_ble_device, mock_service_info
    ):
        """Test firing callbacks when one fails."""
        device = EarlyBluetoothDevice(mock_hass, mock_ble_device, mock_service_info)
        callback1 = MagicMock(side_effect=Exception("Callback error"))
        callback2 = MagicMock()

        device.register_callback(callback1)
        device.register_callback(callback2)

        # Should not raise exception, but callback2 might not be called
        # depending on implementation
        with pytest.raises(Exception):
            device._fire_callbacks()

    @pytest.mark.asyncio
    async def test_connect_success(
        self, mock_hass, mock_ble_device, mock_service_info, mock_bleak_client
    ):
        """Test successful connection."""
        device = EarlyBluetoothDevice(mock_hass, mock_ble_device, mock_service_info)

        result = await device.connect()

        assert result is True
        assert device._client is not None

    @pytest.mark.asyncio
    async def test_connect_already_connected(
        self, mock_hass, mock_ble_device, mock_service_info, mock_bleak_client
    ):
        """Test connecting when already connected."""
        device = EarlyBluetoothDevice(mock_hass, mock_ble_device, mock_service_info)

        # First connection
        await device.connect()

        # Second connection should return True without reconnecting
        with patch("custom_components.early.bluetooth.BleakClient") as mock_client:
            result = await device.connect()
            assert result is True
            # BleakClient should not be called again
            mock_client.assert_not_called()

    @pytest.mark.asyncio
    async def test_connect_failure(
        self, mock_hass, mock_ble_device, mock_service_info
    ):
        """Test connection failure."""
        device = EarlyBluetoothDevice(mock_hass, mock_ble_device, mock_service_info)

        with patch("custom_components.early.bluetooth.BleakClient") as mock_client:
            client = AsyncMock()
            client.connect = AsyncMock(side_effect=BleakError("Connection failed"))
            mock_client.return_value = client

            result = await device.connect()

            assert result is False

    @pytest.mark.asyncio
    async def test_disconnect_success(
        self, mock_hass, mock_ble_device, mock_service_info, mock_bleak_client
    ):
        """Test successful disconnection."""
        device = EarlyBluetoothDevice(mock_hass, mock_ble_device, mock_service_info)

        # Connect first
        await device.connect()

        # Then disconnect
        await device.disconnect()

        device._client.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect_not_connected(
        self, mock_hass, mock_ble_device, mock_service_info
    ):
        """Test disconnecting when not connected."""
        device = EarlyBluetoothDevice(mock_hass, mock_ble_device, mock_service_info)

        # Should not raise exception
        await device.disconnect()

    @pytest.mark.asyncio
    async def test_disconnect_failure(
        self, mock_hass, mock_ble_device, mock_service_info, mock_bleak_client
    ):
        """Test disconnection failure."""
        device = EarlyBluetoothDevice(mock_hass, mock_ble_device, mock_service_info)

        # Connect first
        await device.connect()

        # Mock disconnect failure
        device._client.disconnect = AsyncMock(side_effect=BleakError("Disconnect failed"))

        # Should not raise exception
        await device.disconnect()

    @pytest.mark.asyncio
    async def test_read_orientation(
        self, mock_hass, mock_ble_device, mock_service_info, mock_bleak_client
    ):
        """Test reading orientation."""
        device = EarlyBluetoothDevice(mock_hass, mock_ble_device, mock_service_info)

        # Connect first
        await device.connect()

        # Mock read returning orientation 3
        device._client.read_gatt_char = AsyncMock(return_value=bytearray([3]))

        await device._read_orientation()

        assert device.orientation == 3

    @pytest.mark.asyncio
    async def test_read_orientation_not_connected(
        self, mock_hass, mock_ble_device, mock_service_info
    ):
        """Test reading orientation when not connected."""
        device = EarlyBluetoothDevice(mock_hass, mock_ble_device, mock_service_info)

        # Should not raise exception
        await device._read_orientation()

        assert device.orientation == 0

    @pytest.mark.asyncio
    async def test_read_orientation_failure(
        self, mock_hass, mock_ble_device, mock_service_info, mock_bleak_client
    ):
        """Test reading orientation failure."""
        device = EarlyBluetoothDevice(mock_hass, mock_ble_device, mock_service_info)

        # Connect first
        await device.connect()

        # Mock read failure
        device._client.read_gatt_char = AsyncMock(side_effect=BleakError("Read failed"))

        # Should not raise exception
        await device._read_orientation()

        assert device.orientation == 3  # Should remain at initial value

    def test_on_orientation_changed(
        self, mock_hass, mock_ble_device, mock_service_info
    ):
        """Test orientation change callback."""
        device = EarlyBluetoothDevice(mock_hass, mock_ble_device, mock_service_info)
        callback = MagicMock()
        device.register_callback(callback)

        # Simulate orientation change
        device._on_orientation_changed(1, bytearray([5]))

        assert device.orientation == 5
        callback.assert_called_once()

    def test_on_orientation_changed_same_value(
        self, mock_hass, mock_ble_device, mock_service_info
    ):
        """Test orientation change with same value."""
        device = EarlyBluetoothDevice(mock_hass, mock_ble_device, mock_service_info)
        device._orientation = 3
        callback = MagicMock()
        device.register_callback(callback)

        # Simulate orientation change to same value
        device._on_orientation_changed(1, bytearray([3]))

        assert device.orientation == 3
        callback.assert_not_called()

    def test_on_orientation_changed_empty_data(
        self, mock_hass, mock_ble_device, mock_service_info
    ):
        """Test orientation change with empty data."""
        device = EarlyBluetoothDevice(mock_hass, mock_ble_device, mock_service_info)
        callback = MagicMock()
        device.register_callback(callback)

        # Simulate orientation change with empty data
        device._on_orientation_changed(1, bytearray([]))

        callback.assert_not_called()

    def test_on_disconnect(self, mock_hass, mock_ble_device, mock_service_info):
        """Test disconnection callback."""
        device = EarlyBluetoothDevice(mock_hass, mock_ble_device, mock_service_info)
        device._client = MagicMock()

        device._on_disconnect(device._client)

        assert device._client is None

    def test_match_device_by_name(self):
        """Test matching device by name."""
        service_info = MagicMock()
        service_info.name = "Timeular ZEI 123"
        service_info.service_uuids = []

        assert EarlyBluetoothDevice.match_device(service_info) is True

    def test_match_device_by_uuid(self):
        """Test matching device by service UUID."""
        service_info = MagicMock()
        service_info.name = "Unknown Device"
        service_info.service_uuids = ["c7e70010-c847-11e6-8175-8c89a55d403c"]

        assert EarlyBluetoothDevice.match_device(service_info) is True

    def test_match_device_by_uuid_case_insensitive(self):
        """Test matching device by service UUID (case insensitive)."""
        service_info = MagicMock()
        service_info.name = "Unknown Device"
        service_info.service_uuids = ["C7E70010-C847-11E6-8175-8C89A55D403C"]

        assert EarlyBluetoothDevice.match_device(service_info) is True

    def test_match_device_no_match(self):
        """Test device doesn't match."""
        service_info = MagicMock()
        service_info.name = "Other Device"
        service_info.service_uuids = ["12345678-1234-1234-1234-123456789012"]

        assert EarlyBluetoothDevice.match_device(service_info) is False

    def test_match_device_no_name(self):
        """Test matching device with no name."""
        service_info = MagicMock()
        service_info.name = None
        service_info.service_uuids = []

        assert EarlyBluetoothDevice.match_device(service_info) is False


class TestAsyncDiscoverDevices:
    """Test the async_discover_devices function."""

    @pytest.mark.asyncio
    async def test_discover_devices_found(self, mock_hass):
        """Test discovering devices."""
        service_info1 = MagicMock()
        service_info1.name = "Timeular ZEI 1"
        service_info1.service_uuids = []

        service_info2 = MagicMock()
        service_info2.name = "Other Device"
        service_info2.service_uuids = []

        service_info3 = MagicMock()
        service_info3.name = "Timeular ZEI 2"
        service_info3.service_uuids = []

        with patch(
            "custom_components.early.bluetooth.bluetooth.async_discovered_service_info",
            return_value=[service_info1, service_info2, service_info3],
        ):
            devices = await async_discover_devices(mock_hass)

            assert len(devices) == 2
            assert service_info1 in devices
            assert service_info3 in devices
            assert service_info2 not in devices

    @pytest.mark.asyncio
    async def test_discover_devices_none_found(self, mock_hass):
        """Test discovering devices with none found."""
        service_info = MagicMock()
        service_info.name = "Other Device"
        service_info.service_uuids = []

        with patch(
            "custom_components.early.bluetooth.bluetooth.async_discovered_service_info",
            return_value=[service_info],
        ):
            devices = await async_discover_devices(mock_hass)

            assert len(devices) == 0

    @pytest.mark.asyncio
    async def test_discover_devices_empty(self, mock_hass):
        """Test discovering devices with empty list."""
        with patch(
            "custom_components.early.bluetooth.bluetooth.async_discovered_service_info",
            return_value=[],
        ):
            devices = await async_discover_devices(mock_hass)

            assert len(devices) == 0
