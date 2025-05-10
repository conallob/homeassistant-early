import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_ACCESS_TOKEN
from .const import DOMAIN

class EarlyAppConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Early App."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            # Store the token in the credential store
            await self.hass.helpers.storage.async_migrator(
                f"{DOMAIN}_token_{self.context['entry_id']}", user_input[CONF_ACCESS_TOKEN]
            )
            return self.async_create_entry(title="Early App", data={})
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_ACCESS_TOKEN): str}),
            errors=errors,
        )
