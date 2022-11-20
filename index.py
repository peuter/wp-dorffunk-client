#!/usr/bin/env python
import json
import os
from dotenv import load_dotenv
from wp.client import WpClient

load_dotenv()

API_URL = os.getenv('API_URL')
WORDPRESS_USER = os.getenv('WORDPRESS_USER')
WORDPRESS_PASSWORD = os.getenv('WORDPRESS_PASSWORD')

if __name__ == '__main__':
    client = WpClient(API_URL, WORDPRESS_USER, WORDPRESS_PASSWORD)
    #print(json.dumps(client.get_posts(), indent=4))
    print(json.dumps(client.get_events(), indent=4))
    client.write_cache()
