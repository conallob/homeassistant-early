from homeassistant.core import HomeAssistant
from .const import DOMAIN

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Timeular integration."""
    return True

async def async_setup_entry(hass: HomeAssistant, entry):
    """Set up the Timeular integration from a config entry."""
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )
    return True

async def async_unload_entry(hass: HomeAssistant, entry):
    """Unload a Timeular config entry."""
    await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    return True
