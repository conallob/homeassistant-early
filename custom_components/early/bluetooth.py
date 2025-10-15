"""Bluetooth support for EARLY (Timeular) ZEI tracker."""
from __future__ import annotations

import logging
from typing import Any

from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant, callback

from .const import (
    BLE_ORIENTATION_CHARACTERISTIC_UUID,
    BLE_SERVICE_UUID,
    DEVICE_NAME_PREFIX,
)

_LOGGER = logging.getLogger(__name__)


class EarlyBluetoothDevice:
    """Representation of an EARLY Bluetooth tracker device."""

    def __init__(
        self,
        hass: HomeAssistant,
        device: BLEDevice,
        advertisement_data: bluetooth.BluetoothServiceInfoBleak,
    ) -> None:
        """Initialize the bluetooth device."""
        self.hass = hass
        self._device = device
        self._advertisement_data = advertisement_data
        self._client: BleakClient | None = None
        self._orientation: int = 0
        self._callbacks: list[callable] = []

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self._device.name or "EARLY Tracker"

    @property
    def address(self) -> str:
        """Return the address of the device."""
        return self._device.address

    @property
    def rssi(self) -> int:
        """Return the RSSI of the device."""
        return self._advertisement_data.rssi

    @property
    def orientation(self) -> int:
        """Return the current orientation (0-8)."""
        return self._orientation

    def register_callback(self, callback: callable) -> None:
        """Register a callback to be called when orientation changes."""
        self._callbacks.append(callback)

    def unregister_callback(self, callback: callable) -> None:
        """Unregister a callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    @callback
    def _fire_callbacks(self) -> None:
        """Fire all registered callbacks."""
        for callback_func in self._callbacks:
            callback_func()

    async def connect(self) -> bool:
        """Connect to the device."""
        if self._client and self._client.is_connected:
            return True

        try:
            _LOGGER.debug("Connecting to EARLY tracker at %s", self.address)
            self._client = BleakClient(self._device, disconnected_callback=self._on_disconnect)
            await self._client.connect()

            # Read initial orientation
            await self._read_orientation()

            # Subscribe to orientation changes
            await self._client.start_notify(
                BLE_ORIENTATION_CHARACTERISTIC_UUID,
                self._on_orientation_changed,
            )

            _LOGGER.info("Connected to EARLY tracker at %s", self.address)
            return True

        except BleakError as err:
            _LOGGER.error("Error connecting to EARLY tracker: %s", err)
            return False

    async def disconnect(self) -> None:
        """Disconnect from the device."""
        if self._client and self._client.is_connected:
            try:
                await self._client.disconnect()
                _LOGGER.debug("Disconnected from EARLY tracker at %s", self.address)
            except BleakError as err:
                _LOGGER.error("Error disconnecting from EARLY tracker: %s", err)

    async def _read_orientation(self) -> None:
        """Read the current orientation from the device."""
        if not self._client or not self._client.is_connected:
            return

        try:
            value = await self._client.read_gatt_char(BLE_ORIENTATION_CHARACTERISTIC_UUID)
            if value:
                # The orientation is the first byte of the characteristic
                self._orientation = int(value[0])
                _LOGGER.debug("Read orientation: %d", self._orientation)
        except BleakError as err:
            _LOGGER.error("Error reading orientation: %s", err)

    def _on_orientation_changed(self, sender: int, data: bytearray) -> None:
        """Handle orientation change notification."""
        if data:
            new_orientation = int(data[0])
            if new_orientation != self._orientation:
                _LOGGER.debug("Orientation changed from %d to %d", self._orientation, new_orientation)
                self._orientation = new_orientation
                self._fire_callbacks()

    def _on_disconnect(self, client: BleakClient) -> None:
        """Handle disconnection."""
        _LOGGER.warning("EARLY tracker at %s disconnected", self.address)
        self._client = None

    @staticmethod
    def match_device(
        service_info: bluetooth.BluetoothServiceInfoBleak,
    ) -> bool:
        """Check if the device matches EARLY tracker criteria."""
        # Check if the device name starts with "Timeular ZEI"
        if service_info.name and service_info.name.startswith(DEVICE_NAME_PREFIX):
            return True

        # Check if the device advertises the EARLY service UUID
        if BLE_SERVICE_UUID.lower() in [
            str(uuid).lower() for uuid in service_info.service_uuids
        ]:
            return True

        return False


async def async_discover_devices(
    hass: HomeAssistant,
) -> list[bluetooth.BluetoothServiceInfoBleak]:
    """Discover EARLY Bluetooth devices."""
    discovered_devices = []

    # Get all discovered bluetooth devices
    service_infos = bluetooth.async_discovered_service_info(hass)

    for service_info in service_infos:
        if EarlyBluetoothDevice.match_device(service_info):
            discovered_devices.append(service_info)

    return discovered_devices
