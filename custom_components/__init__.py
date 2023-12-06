import requests


# To Use:
#
#
# timeular:
#  api_key: YOUR_API_KEY
#

class TimeularConfig:
    def __init__(self, api_key, base_url="https://api.timeular.com/v3"):
        self.api_key = api_key
        self.base_url = base_url

    def _request(self, method, endpoint, **kwargs):
        kwargs["headers"] = {
            "Authorization": f"Bearer {self.api_key}",
        }

        return requests.request(method, f"{self.base_url}/{endpoint}", **kwargs)

    def get_activities(self):
        response = self._request("GET", "activities")

        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to get activities: {response.text}")

    def create_activity(self, data):
        response = self._request("POST", "activities", json=data)

        if response.status_code == 201:
            return response.json()
        else:
            raise Exception(f"Failed to create activity: {response.text}")

    def get_tags(self):
        response = self._request("GET", "tags")

        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to get tags: {response.text}")

    def create_tag(self, data):
        response = self._request("POST", "tags", json=data)

        if response.status_code == 201:
            return response.json()
        else:
            raise Exception(f"Failed to create tag: {response.text}")

    def start_timer(self, activity_id, duration_in_minutes=None):
        data = {"activity_id": activity_id}

        if duration_in_minutes:
            data["duration"] = duration_in_minutes

        response = self._request("POST", "timers", json=data)

        if response.status_code == 201:
            return response.json()
        else:
            raise Exception(f"Failed to start timer: {response.text}")

    def stop_timer(self):
        response = self._request("POST", "timers/stop")

        if response.status_code == 204:
            return None
        else:
            raise Exception(f"Failed to stop timer: {response.text}")

    def get_timers(self):
        response = self._request("GET", "timers")

        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to get timers: {response.text}")
