#!/usr/bin/env python3

from time import sleep
import requests
import os

max_timeout = 300
nb_not_up = True
api_url = "http://netbox:8000/api"
while nb_not_up:
    try:
        response = requests.get(api_url)
        if "circuits" in response.json():
            nb_not_up = False
    except:
        print("did not get a repsonse yet")
    
    if nb_not_up:
        print("netbox not yet up. sleeping for 10s and trying again")
        sleep(10)
