import json
import html
from functools import lru_cache
import logging
import requests
import base64
from os.path import exists
from dorffunk.wp.log_formatter import ColoredFormatter

logger = logging.getLogger("WpClient")
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
ch.setFormatter(ColoredFormatter())
logger.addHandler(ch)


class WpClient:
    cache_file = 'cache.json'
    cache_parts_updated = []
    organizer_parent_cat = 605
    use_cache = True
    properties = {
        "lsvr_event": {
            "id": {"convert": "copy"},
            "date_gmt": {"convert": "copy"},
            "modified_gmt": {"convert": "copy"},
            "slug": {"convert": "copy"},
            "type": {"convert": "copy"},
            "link": {"convert": "copy"},
            "status": {"convert": "copy"},
            "title.rendered": {"convert": "unescape", "name": "title"},
            "content.rendered": {"convert": "unescape", "name": "content"},
            "excerpt.rendered": {"convert": "unescape", "name": "excerpt"},
            "dd_to_publish_as_showcase": {"convert": "copy"},
            "authorName": {"convert": "copy"},
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
        },
        "posts": {
            "id": {"convert": "copy"},
            "date_gmt": {"convert": "copy"},
            "modified_gmt": {"convert": "copy"},
            "slug": {"convert": "copy"},
            "type": {"convert": "copy"},
            "link": {"convert": "copy"},
            "status": {"convert": "copy"},
            "sticky": {"convert": "copy"},
            "title.rendered": {"convert": "unescape", "name": "title"},
            "content.rendered": {"convert": "unescape", "name": "content"},
            "excerpt.rendered": {"convert": "unescape", "name": "excerpt"},
            "dd_to_publish_as_showcase": {"convert": "copy"},
            "authorName": {"convert": "copy"},
            "featured_media": {"convert": "resolve_media"},
            "_links.wp:attachment": {"convert": "resolve_attachments", "name": "attachments"},
        }
    }

    def __init__(self, api_url, user, password, use_cache=True):
        self.api_url = api_url
        credentials = user + ":" + password
        self.token = base64.b64encode(credentials.encode())
        self.headers = {'Authorization': 'Basic ' + self.token.decode('utf-8')}
        self.use_cache = use_cache
        self.cache = {
            "categories": {},
            "tags": {},
            "lsvr_event_cat": {},
            "lsvr_event_tag": {}
        }

        if self.use_cache:
            self.read_cache()

    def read_cache(self):
        if exists(self.cache_file):
            with open(self.cache_file) as f:
                self.cache = json.load(f)

    def write_cache(self):
        if len(self.cache_parts_updated) > 0 and self.use_cache:
            with open(self.cache_file, 'w') as f:
                f.write(json.dumps(self.cache, indent=4))

    def get_category(self, uid):
        return self._get_ref("categories", uid)

    def get_tag(self, uid):
        return self._get_ref("tags", uid)

    def get_event_category(self, uid):
        return self._get_ref("lsvr_event_cat", uid)

    def get_event_tag(self, uid):
        return self._get_ref("lsvr_event_tag", uid)

    def get_user(self, uid):
        return self._get_ref("users", uid)

    def get_posts(self):
        posts = []
        for post in self._get("posts"):
            p = {
                "categories": [],
                "tags": []
            }
            for cat_id in post["categories"]:
                cat = self.get_category(cat_id)
                if cat is not None:
                    p["categories"].append(cat["name"])
                else:
                    logger.warning("category %d unknown" % cat_id)
            for tag_id in post["tags"]:
                tag = self.get_tag(tag_id)
                if tag is not None:
                    p["tags"].append(tag["name"])
                else:
                    logger.warning("tag %d unknown" % tag_id)
            author = self.get_user(post["author"])
            if author is not None:
                p["author"] = author["name"]
            self._copy_properties("posts", post, p)
            posts.append(p)
        return posts

    def get_events(self):
        events = []
        for event in self._get("lsvr_event"):
            ev = {
                "categories": [],
                "tags": [],
                "organizer": []
            }
            for cat_id in event["lsvr_event_cat"]:
                cat = self.get_event_category(cat_id)
                if cat is not None:
                    if cat["parent"] == self.organizer_parent_cat:
                        ev["organizer"].append(cat["name"])
                    else:
                        is_organizer = False
                        if cat["parent"] > 0:
                            parent = cat
                            while parent["parent"] > 0:
                                parent = self.get_event_category(parent["parent"])
                                if parent["parent"] == self.organizer_parent_cat:
                                    ev["organizer"].append(parent["name"])
                                    is_organizer = True
                                    break
                        if not is_organizer:
                            ev["categories"].append(cat["name"])
                else:
                    logger.warning("event category %d unknown" % cat_id)
            for tag_id in event["lsvr_event_tag"]:
                tag = self.get_tag(tag_id)
                if tag is not None:
                    event["tags"].append(tag["name"])
                else:
                    logger.warning("tag %d unknown" % tag_id)
            self._copy_properties("lsvr_event", event, ev)
            if ("authorName" not in ev or len(ev["authorName"]) == 0) and event["author"] > 0:
                # use username as fallback
                author = self.get_user(event["author"])
                if author is not None:
                    ev["authorName"] = author["name"]
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
        if media_id > 0:
            data = self._get("media/%s" % media_id)
            return data if data is not None else None
        return None

    # keine rechte
    def get_event_locations(self):
        return self._get("taxonomies/lsvr_event_location", True)

    def _get_ref(self, type_name, uid):
        if type_name not in self.cache or str(uid) not in self.cache[type_name]:
            # update cache
            self._update_cache(type_name)
        if str(uid) in self.cache[type_name]:
            return self.cache[type_name][str(uid)]
        else:
            return None

    def _update_cache(self, type_name):
        if type_name not in self.cache_parts_updated:
            data = {}
            logger.debug("Updating %s cache" % type_name)
            for entry in self._get(type_name, per_page=100):
                data[str(entry["id"])] = entry
            self.cache[type_name] = data
            self.cache_parts_updated.append(type_name)

    @lru_cache(maxsize=None)
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
