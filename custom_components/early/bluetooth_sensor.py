"""Bluetooth sensor platform for EARLY (Timeular) tracker."""
from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING

from homeassistant.components import bluetooth
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, SIGNAL_STRENGTH_DECIBELS_MILLIWATT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .bluetooth import EarlyBluetoothDevice
from .const import (
    CONF_API_SECRET,
    DOMAIN,
    ATTR_ORIENTATION,
    ATTR_RSSI,
    ATTR_ACTIVITY_NAME,
    DEVICE_NAME_PREFIX,
)

if TYPE_CHECKING:
    from .sensor import EarlyAPICoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_bluetooth_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EARLY Bluetooth sensors from a config entry."""
    address = config_entry.data["address"]

    # Get the bluetooth device info
    service_info = bluetooth.async_last_service_info(hass, address, connectable=True)
    if not service_info:
        _LOGGER.error("Could not find bluetooth device with address %s", address)
        return

    # Create the bluetooth device wrapper
    ble_device = EarlyBluetoothDevice(
        hass, service_info.device, service_info
    )

    # Connect to the device
    if not await ble_device.connect():
        _LOGGER.error("Failed to connect to bluetooth device %s", address)
        return

    # Store the device in hass data
    hass.data[DOMAIN][config_entry.entry_id]["bluetooth_devices"][address] = ble_device

    # Check if we have API credentials to fetch activity mappings
    coordinator = None
    api_key = config_entry.data.get(CONF_API_KEY)
    api_secret = config_entry.data.get(CONF_API_SECRET)

    if api_key and api_secret:
        # Import here to avoid circular dependency
        from .sensor import EarlyAPICoordinator

        # Create coordinator for fetching activities
        coordinator = EarlyAPICoordinator(hass, api_key, api_secret)
        # Fetch activities to get device side mappings
        await coordinator._fetch_activities()

        # Store coordinator for later use
        hass.data[DOMAIN][config_entry.entry_id]["coordinator"] = coordinator

    # Create sensors
    sensors = [
        EarlyTrackerOrientationSensor(ble_device, config_entry),
        EarlyTrackerRSSISensor(ble_device, config_entry),
    ]

    # Add current activity sensor if we have API credentials
    if coordinator:
        sensors.append(
            EarlyTrackerCurrentActivitySensor(ble_device, config_entry, coordinator)
        )

    async_add_entities(sensors, True)


class EarlyTrackerOrientationSensor(SensorEntity):
    """Representation of an EARLY tracker orientation sensor."""

    def __init__(
        self,
        device: EarlyBluetoothDevice,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        self._device = device
        self._config_entry = config_entry
        self._attr_name = f"{device.name} Orientation"
        self._attr_unique_id = f"{device.address}_orientation"
        self._attr_icon = "mdi:axis-z-rotate-counterclockwise"
        self._attr_native_unit_of_measurement = None

        # Register callback for orientation changes
        self._device.register_callback(self._handle_orientation_change)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.address)},
            name=self._device.name,
            manufacturer="Timeular",
            model="ZEI Tracker",
            connections={(bluetooth.DOMAIN, self._device.address)},
        )

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        return self._device.orientation

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return {
            ATTR_ORIENTATION: self._device.orientation,
            "device_address": self._device.address,
        }

    @callback
    def _handle_orientation_change(self) -> None:
        """Handle orientation change from the device."""
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._device._client is not None and self._device._client.is_connected

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect from the device when removed."""
        self._device.unregister_callback(self._handle_orientation_change)


class EarlyTrackerRSSISensor(SensorEntity):
    """Representation of an EARLY tracker RSSI sensor."""

    def __init__(
        self,
        device: EarlyBluetoothDevice,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        self._device = device
        self._config_entry = config_entry
        self._attr_name = f"{device.name} Signal Strength"
        self._attr_unique_id = f"{device.address}_rssi"
        self._attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
        self._attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
        self._attr_entity_registry_enabled_default = False

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.address)},
            name=self._device.name,
            manufacturer="Timeular",
            model="ZEI Tracker",
            connections={(bluetooth.DOMAIN, self._device.address)},
        )

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        return self._device.rssi

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._device._client is not None and self._device._client.is_connected


class EarlyTrackerCurrentActivitySensor(SensorEntity):
    """Representation of an EARLY tracker current activity sensor based on orientation."""

    def __init__(
        self,
        device: EarlyBluetoothDevice,
        config_entry: ConfigEntry,
        coordinator: EarlyAPICoordinator,
    ) -> None:
        """Initialize the sensor."""
        self._device = device
        self._config_entry = config_entry
        self._coordinator = coordinator
        self._attr_name = f"{device.name} Current Activity"
        self._attr_unique_id = f"{device.address}_current_activity"
        self._attr_icon = "mdi:clock-outline"

        # Register callback for orientation changes
        self._device.register_callback(self._handle_orientation_change)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.address)},
            name=self._device.name,
            manufacturer="Timeular",
            model="ZEI Tracker",
            connections={(bluetooth.DOMAIN, self._device.address)},
        )

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        orientation = self._device.orientation
        if orientation is None:
            return "unknown"

        # Get the activity name for this orientation
        activity_name = self._coordinator.get_activity_by_device_side(orientation)
        if activity_name:
            return activity_name

        # No activity assigned to this side
        return "idle"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        attributes = {
            ATTR_ORIENTATION: self._device.orientation,
            "device_address": self._device.address,
        }

        # Add activity name if available
        orientation = self._device.orientation
        if orientation is not None:
            activity_name = self._coordinator.get_activity_by_device_side(orientation)
            if activity_name:
                attributes[ATTR_ACTIVITY_NAME] = activity_name

        return attributes

    @callback
    def _handle_orientation_change(self) -> None:
        """Handle orientation change from the device."""
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._device._client is not None and self._device._client.is_connected

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect from the device when removed."""
        self._device.unregister_callback(self._handle_orientation_change)
