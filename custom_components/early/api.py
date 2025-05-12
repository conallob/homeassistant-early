import requests
from .const import API_BASE_URL

class EarlyAppApiClient:
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        })

    def get_profile(self):
        resp = self.session.get(f"{API_BASE_URL}/profile")
        resp.raise_for_status()
        return resp.json()

    def get_current_activity(self):
        resp = self.session.get(f"{API_BASE_URL}/activities/current")
        resp.raise_for_status()
        return resp.json()

    def get_all_activities(self):
        resp = self.session.get(f"{API_BASE_URL}/activities")
        resp.raise_for_status()
        return resp.json()

    # Add more API methods as needed
