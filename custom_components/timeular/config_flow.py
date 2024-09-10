from homeassistant import config_entries
from homeassistant.core import callback
import voluptuous as vol
from .const import DOMAIN

class TimeularConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Timeular."""

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is not None:
            return self.async_create_entry(title="Timeular", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("api_key"): str,
            })
        )
