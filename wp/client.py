import requests
import base64


class WpClient:

    def __init__(self, api_url, user, password):
        self.api_url = api_url
        credentials = user + ":" + password
        self.token = base64.b64encode(credentials.encode())
        self.headers = {'Authorization': 'Basic ' + self.token.decode('utf-8')}

        # refresh some values we might need
        self.categories = self._get("categories")

    def get_posts(self):
        return self._get("posts")

    def get_events(self):
        return self._get("lsvr_event")

    def get_plugins(self):
        return self._get("plugins", True)

    # keine rechte
    def get_event_locations(self):
        return self._get("taxonomies/lsvr_event_location", True)

    def _get(self, type, auth=False):
         response = requests.get(self.api_url + type, headers=self.headers if auth is True else None)
         return response.json()