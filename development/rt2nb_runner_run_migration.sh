#!/bin/bash

pip3 install -r /opt/repo/requirements.txt

cd /opt/repo/

python3 development/check_if_nb_api_up.py
python3 rt2nb/racktables2netbox.py
