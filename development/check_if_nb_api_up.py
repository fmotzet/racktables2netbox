#!/usr/bin/env python3

from time import sleep
import requests
import os

nb_not_up = True
api_url = "http://netbox:8000/api"
max_timeout_attempts = 20
current_attempts = 0
while nb_not_up:
    try:
        response = requests.get(api_url)
        if "circuits" in response.text:
            nb_not_up = False
            exit(0)
    except:
        print("did not get a repsonse yet")
    if not current_attempts < max_timeout_attempts:
        print("max attempts reached. dying")
        exit(2)
    if nb_not_up:
        print("netbox not yet up. sleeping for 10s and trying again")
        current_attempts = current_attempts + 1
        sleep(10)

