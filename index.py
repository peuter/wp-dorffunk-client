#!/usr/bin/env python
import json
import os
from dotenv import load_dotenv
from wp.client import WpClient
import argparse

load_dotenv()

API_URL = os.getenv('API_URL')
WORDPRESS_USER = os.getenv('WORDPRESS_USER')
WORDPRESS_PASSWORD = os.getenv('WORDPRESS_PASSWORD')

parser = argparse.ArgumentParser(
    prog='WordpressClient',
    description='Read posts and events from a wordpress page with dorffunk plugins')

parser.add_argument('-C', '--no-cache', action='store_true', help='Ignore cache file')

if __name__ == '__main__':
    args = parser.parse_args()
    client = WpClient(API_URL, WORDPRESS_USER, WORDPRESS_PASSWORD, use_cache=args.no_cache == False)
    print(json.dumps(client.get_posts(), indent=4))
    #print(json.dumps(client.get_events(), indent=4))
    client.write_cache()
