from homeassistant.helpers.entity import Entity
from .const import DOMAIN
from .api import EarlyAppApiClient

async def async_setup_entry(hass, config_entry, async_add_entities):
    # Retrieve the access token from the credential store
    entry_id = config_entry.entry_id
    token_storage_key = f"{DOMAIN}_token_{entry_id}"
    access_token = await hass.helpers.storage.async_migrator(token_storage_key, None)
    api = EarlyAppApiClient(access_token)

    profile = await hass.async_add_executor_job(api.get_profile)
    current_activity = await hass.async_add_executor_job(api.get_current_activity)
    all_activities = await hass.async_add_executor_job(api.get_all_activities)

    entities = [
        EarlyAppProfileSensor(profile),
        EarlyAppCurrentActivitySensor(current_activity),
        EarlyAppAllActivitiesSensor(all_activities),
    ]
    async_add_entities(entities)

class EarlyAppProfileSensor(Entity):
    def __init__(self, profile):
        self._attr_name = "Early App Profile Name"
        self._state = profile.get("name")

    @property
    def state(self):
        return self._state

class EarlyAppCurrentActivitySensor(Entity):
    def __init__(self, current_activity):
        self._attr_name = "Early App Current Activity"
        self._state = current_activity.get("name")

    @property
    def state(self):
        return self._state

class EarlyAppAllActivitiesSensor(Entity):
    def __init__(self, all_activities):
        self._attr_name = "Early App All Activities"
        self._state = ", ".join(a.get("name") for a in all_activities)

    @property
    def state(self):
        return self._state
