from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN

async def async_setup(hass: HomeAssistant, config) -> bool:
    """Remove YAML support; only allow UI setup."""
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Early App from a config entry (UI only)."""
    hass.data.setdefault(DOMAIN, {})
    hass.async_create_task(hass.config_entries.async_forward_entry_setup(entry, "sensor"))
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
