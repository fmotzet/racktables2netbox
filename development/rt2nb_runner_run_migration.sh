#!/bin/bash

pip3 install -r /opt/repo/requirements.txt

cd /opt/repo/
python3 rt2nb/racktables2netbox.py
