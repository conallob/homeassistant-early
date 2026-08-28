"""The EARLY (Timeular) integration."""

from __future__ import annotations

import logging

from homeassistant.components import bluetooth as ha_bluetooth
from homeassistant.components.bluetooth.match import BluetoothCallbackMatcher
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback

from .bluetooth import EarlyBluetoothDevice
from .const import BLE_SERVICE_UUID, DEVICE_NAME_PREFIX, DOMAIN
from .util import is_bluetooth_entry
from .webhook import async_setup_webhook, async_unload_webhook

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up EARLY (Timeular) from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "config": entry.data,
        "bluetooth_devices": {},
    }

    # Set up platforms. SENSOR is forwarded and awaited on its own, not
    # together with SWITCH, because async_forward_entry_setups sets up
    # platforms concurrently (asyncio.gather) rather than in list order.
    # switch.py depends on the API coordinator that sensor.py/
    # bluetooth_sensor.py creates, so SENSOR must fully finish first.
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR])
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.SWITCH])

    # If SENSOR set up an API coordinator, try to subscribe it to EARLY's
    # webhooks so tracking start/stop is reflected immediately rather than
    # waiting up to DEFAULT_SCAN_INTERVAL seconds for the next poll. This is
    # best-effort: it requires a publicly reachable HA URL, and quietly
    # leaves the entry on polling-only if that (or the API subscription
    # call) isn't available - see webhook.py.
    coordinator = hass.data[DOMAIN][entry.entry_id].get("coordinator")
    if coordinator is not None:
        try:
            await async_setup_webhook(hass, entry, coordinator)
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception(
                "Unexpected error setting up EARLY webhook for entry %s; "
                "continuing with polling only",
                entry.entry_id,
            )

    # Register for bluetooth discovery if this is a bluetooth setup
    if is_bluetooth_entry(entry):
        # This is a bluetooth device entry
        @callback
        def _async_bluetooth_callback(
            service_info: ha_bluetooth.BluetoothServiceInfoBleak,
            change: ha_bluetooth.BluetoothChange,
        ) -> None:
            """Handle bluetooth device discovery and updates."""
            if service_info.address == entry.data["address"]:
                _LOGGER.debug(
                    "Bluetooth device update for %s: %s",
                    service_info.address,
                    change,
                )

        entry.async_on_unload(
            ha_bluetooth.async_register_callback(
                hass,
                _async_bluetooth_callback,
                BluetoothCallbackMatcher(address=entry.data["address"]),
                ha_bluetooth.BluetoothScanningMode.ACTIVE,
            )
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if entry.entry_id in hass.data.get(DOMAIN, {}):
        entry_data = hass.data[DOMAIN][entry.entry_id]

        # Disconnect from any bluetooth devices
        bluetooth_devices = entry_data.get("bluetooth_devices", {})
        for device in bluetooth_devices.values():
            if isinstance(device, EarlyBluetoothDevice):
                await device.disconnect()

        # Tear down any EARLY webhook subscription set up for this entry
        coordinator = entry_data.get("coordinator")
        if coordinator is not None:
            try:
                await async_unload_webhook(hass, entry, coordinator)
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception(
                    "Unexpected error tearing down EARLY webhook for entry %s",
                    entry.entry_id,
                )

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok
