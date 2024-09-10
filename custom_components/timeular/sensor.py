import requests
from homeassistant.helpers.entity import Entity
from .const import API_URL

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Timeular sensor platform."""
    api_key = entry.data["api_key"]
    async_add_entities([TimeularSensor(api_key)])

class TimeularSensor(Entity):
    """Representation of a Timeular Sensor."""

    def __init__(self, api_key):
        """Initialize the sensor."""
        self._api_key = api_key
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Timeular Sensor"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def update(self):
        """Fetch new state data for the sensor."""
        response = requests.get(
            f"{API_URL}/tracking",
            headers={
                "Authorization": f"Bearer {self._api_key}"
            }
        )
        if response.status_code == 200:
            data = response.json()
            self._state = data.get("currentTracking", {}).get("activity", "No activity")
        else:
            self._state = "Error"
