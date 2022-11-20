import json
import html
from functools import cache
import logging
import requests
import base64
from os.path import exists
from wp.log_formatter import ColoredFormatter

logger = logging.getLogger("WpClient")
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
ch.setFormatter(ColoredFormatter())
logger.addHandler(ch)


class WpClient:
    cache_file = 'cache.json'
    cache_parts_updated = []
    properties = {
        "lsvr_event": {
            "id": {"convert": "copy"},
            "date_gmt": {"convert": "copy"},
            "modified_gmt": {"convert": "copy"},
            "slug": {"convert": "copy"},
            "type": {"convert": "copy"},
            "link": {"convert": "copy"},
            "title.rendered": {"convert": "unescape", "name": "title"},
            "content.rendered": {"convert": "unescape", "name": "content"},
            "excerpt.rendered": {"convert": "unescape", "name": "excerpt"},
            "dd_to_publish_as_showcase": {"convert": "copy"},
            "authorName": {"convert": "copy"},
            "status": {"convert": "copy"},
            "allDayEvent": {"convert": "copy"},
            "startTimeLong": {"convert": "copy"},
            "endTimeLong": {"convert": "copy"},
            "locationName": {"convert": "copy"},
            "_links.wp:attachment": {"convert": "resolve_attachments", "name": "attachments"},
            "featured_media": {"convert": "resolve_media"}
        },
        "media": {
            "id": {"convert": "copy"},
            "date_gmt": {"convert": "copy"},
            "modified_gmt": {"convert": "copy"},
            "alt_text": {"convert": "copy"},
            "media_type": {"convert": "copy"},
            "mime_type": {"convert": "copy"},
            "source_url": {"convert": "copy"},
            "title.rendered": {"convert": "unescape", "name": "title"},
            "caption.rendered": {"convert": "unescape", "name": "caption"},
            "description.rendered": {"convert": "unescape", "name": "description"},
        }
    }

    def __init__(self, api_url, user, password):
        self.api_url = api_url
        credentials = user + ":" + password
        self.token = base64.b64encode(credentials.encode())
        self.headers = {'Authorization': 'Basic ' + self.token.decode('utf-8')}

        # refresh some values we might need
        #self.categories = self._get("categories")

        self.cache = {
            "lsvr_event_cat": {},
            "lsvr_event_tag": {}
        }
        self.read_cache()

    def __del__(self):
        self.write_cache()

    def read_cache(self):
        if exists(self.cache_file):
            with open(self.cache_file) as f:
                self.cache = json.load(f)

    def write_cache(self):
        if len(self.cache_parts_updated) > 0:
            with open(self.cache_file, 'w') as f:
                f.write(json.dumps(self.cache, indent=4))

    def get_event_category(self, id):
        if str(id) not in self.cache["lsvr_event_cat"]:
            # update cache
            self.update_event_category_cache()
        if str(id) in self.cache["lsvr_event_cat"]:
            return self.cache["lsvr_event_cat"][str(id)]
        else:
            return None

    def update_event_category_cache(self):
        if "lsvr_event_cat" not in self.cache_parts_updated:
            data = {}
            logger.debug("Updating event category cache")
            for entry in self.get_event_categories():
                data[str(entry["id"])] = entry
            self.cache["lsvr_event_cat"] = data
            self.cache_parts_updated.append("lsvr_event_cat")

    def get_posts(self):
        return self._get("posts")

    def get_events(self):
        events = []
        for event in self._get("lsvr_event"):
            ev = {
                "categories": [],
                "tags": []
            }
            for cat_id in event["lsvr_event_cat"]:
                cat = self.get_event_category(cat_id)
                if cat is not None:
                    ev["categories"].append(cat["name"])
                else:
                    logger.warning("event category %d unknown" % cat_id)
            self._copy_properties("lsvr_event", event, ev)
            events.append(ev)
        return events

    def _copy_properties(self, wp_type, source, target):
        if wp_type in self.properties and source is not None:
            for key, config in self.properties[wp_type].items():
                if "." in key:
                    ref = source
                    for subkey in key.split("."):
                        if subkey in ref:
                            ref = ref[subkey]
                        else:
                            ref = None
                            break
                    if ref is not None:
                        self._copy_value(key, config, ref, target)
                elif key in source:
                    self._copy_value(key, config, source[key], target)
        return target

    def _copy_value(self, property_name, config, value, target):
        if "name" in config:
            property_name = config["name"]
        if config["convert"] == "copy":
            target[property_name] = value
        elif config["convert"] == "unescape":
            target[property_name] = html.unescape(value)
        elif config["convert"] == "resolve_media":
            # check if media is already in the attachments
            if "attachments" in target:
                for attachment in target["attachments"]:
                    if attachment["id"] == value:
                        target[property_name] = attachment
                        logger.debug("using attachment %s" % value)
                        return
            data = self.resolve_media(value)
            if data is not None:
                target[property_name] = self._copy_properties("media", data, {})
        elif config["convert"] == "resolve_attachments":
            # only use the first entry
            if len(value) > 0:
                endpoint = value[0]["href"].replace(self.api_url, "")
                data = self._get(endpoint)
                if data is not None:
                    media_data = []
                    for entry in data:
                        media_data.append(self._copy_properties("media", entry, {}))
                    target[property_name] = media_data

    def resolve_media(self, media_id):
        data = self._get("media/%s" % media_id)
        return data if data is not None else None

    def get_event_categories(self):
        return self._get("lsvr_event_cat", per_page=100)

    def get_event_tags(self):
        return self._get("lsvr_event_tag", per_page=100)

    # keine rechte
    def get_event_locations(self):
        return self._get("taxonomies/lsvr_event_location", True)

    @cache
    def _get(self, endpoint, auth=False, per_page=0, page=0, offset=0):
        params = {}
        if per_page > 0:
            params["per_page"] = per_page
        if page > 0:
            params["page"] = page
        if offset > 0:
            params["offset"] = offset
        logger.debug("requesting %s" % self.api_url + endpoint)
        response = requests.get(self.api_url + endpoint, headers=self.headers if auth is True else None, params=params)
        return response.json()
