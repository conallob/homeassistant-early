"""The EARLY (Timeular) integration."""
from __future__ import annotations

import logging

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.match import BluetoothCallbackMatcher
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback

from .bluetooth import EarlyBluetoothDevice
from .const import DOMAIN, BLE_SERVICE_UUID, DEVICE_NAME_PREFIX

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up EARLY (Timeular) from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "config": entry.data,
        "bluetooth_devices": {},
    }

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register for bluetooth discovery if this is a bluetooth setup
    if "address" in entry.data:
        # This is a bluetooth device entry
        @callback
        def _async_bluetooth_callback(
            service_info: bluetooth.BluetoothServiceInfoBleak,
            change: bluetooth.BluetoothChange,
        ) -> None:
            """Handle bluetooth device discovery and updates."""
            if service_info.address == entry.data["address"]:
                _LOGGER.debug(
                    "Bluetooth device update for %s: %s",
                    service_info.address,
                    change,
                )

        entry.async_on_unload(
            bluetooth.async_register_callback(
                hass,
                _async_bluetooth_callback,
                BluetoothCallbackMatcher(address=entry.data["address"]),
                bluetooth.BluetoothScanningMode.ACTIVE,
            )
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Disconnect from any bluetooth devices
    if entry.entry_id in hass.data[DOMAIN]:
        bluetooth_devices = hass.data[DOMAIN][entry.entry_id].get("bluetooth_devices", {})
        for device in bluetooth_devices.values():
            if isinstance(device, EarlyBluetoothDevice):
                await device.disconnect()

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
