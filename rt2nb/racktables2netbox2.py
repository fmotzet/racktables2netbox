#!/usr/bin/env python3
# -*- coding: utf-8 -*-
__version__ = 1.00

import os
import json
import logging
from os import replace
import pprint
import pymysql
import pynetbox
import requests
import slugify
import socket
import struct
import urllib3
import urllib.parse
import re
from time import sleep
import yaml
import copy
import datetime
import re
import ipcalc


class Migrator:
    def slugify(self, text):
        return slugify.slugify(text, max_length=50)

    def create_tenant_group(self, name):
        pass

    def create_tenant(self, name, tenant_group=None):
        logger.info("Creating tenant {}").format(name)

        tenant = {"name": name, "slug": self.slugify(name)}

        if tenant_group:
            tenant["tenant_group"] = netbox.tenancy.tenant_groups.all()

        return netbox.tenancy.tenants.create(tenant)

    def create_region(self, name, parent=None):
        netbox.dcim.regions.create()

        if not parent:
            pass
        pass

    def create_site(
        self,
        name,
        region,
        status,
        physical_address,
        facility,
        shipping_address,
        contact_phone,
        contact_email,
        contact_name,
        tenant,
        time_zone,
    ):
        slug = self.slugify(name)
        pass


# Re-Enabled SSL verification
# urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
class NETBOX(object):
    def __init__(self, pynetboxobj):
        self.base_url = "{}/api".format(config["NetBox"]["NETBOX_HOST"])
        self.py_netbox = pynetboxobj
        self.all_ips = None
        self.all_prefixes = None
        # Create HTTP connection pool
        self.s = requests.Session()

        # SSL verification
        self.s.verify = True

        # Define REST Headers
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json; indent=4",
            "Authorization": "Token {0}".format(config["NetBox"]["NETBOX_TOKEN"]),
        }

        self.s.headers.update(headers)
        self.device_types = None

    def uploader(self, data, url, method="POST"):

        logger.debug("HTTP Request: {} - {} - {}".format(method, url, data))

        try:
            request = requests.Request(method, url, data=json.dumps(data))
            prepared_request = self.s.prepare_request(request)
            r = self.s.send(prepared_request)
            logger.debug(f"HTTP Response: {r.status_code!s} - {r.reason}")
            if r.status_code not in [200, 201]:
                logger.debug(r.text)
            r.raise_for_status()
            r.close()
        except:
            logger.debug("POST attempt failed")
        try:
            if r:
                return_obj = r.json
        except:
            sleep(2)
            return {}
        return return_obj

    def uploader2(self, data, url, method="POST"):
        # ignores failures.
        method = "POST"

        logger.debug("HTTP Request: {} - {} - {}".format(method, url, data))

        request = requests.Request(method, url, data=json.dumps(data))
        prepared_request = self.s.prepare_request(request)
        r = self.s.send(prepared_request)
        logger.debug(f"HTTP Response: {r.status_code!s} - {r.reason}")
        r.close()
        logger.debug(r.text)

    def fetcher(self, url):
        method = "GET"

        logger.debug("HTTP Request: {} - {}".format(method, url))
        max_attempts = 3
        current_attempt = 0
        while current_attempt < max_attempts:

            try:
                request = requests.Request(method, url)
                prepared_request = self.s.prepare_request(request)
                r = self.s.send(prepared_request)

                logger.debug(f"HTTP Response: {r.status_code} - {r.reason}")
                r.raise_for_status()
                r.close()
            except:
                sleep(2)
                logger.debug("fetch attempt failed")
            try:
                if r:
                    if r.status_code == 200:
                        return r.text
            except:
                test = ""
            current_attempt = current_attempt + 1
        logger.debug("failed to get {} 3 times".format(url))
        exit(1)

    def post_subnet(self, data):
        url = self.base_url + "/ipam/prefixes/"
        exists = self.check_for_subnet(data)
        if exists[0]:
            logger.info("prefix/subnet: {} already exists, updating with Put".format(data["prefix"]))
            method = "PUT"
            url = "{}{}/".format(url, exists[1]["id"])
            self.uploader(data, url, method)
        else:
            logger.info("Posting data to {}".format(url))
            self.uploader(data, url)

    def check_for_subnet(self, data):
        url_safe_ip = urllib.parse.quote_plus(data["prefix"])
        url = self.base_url + "/ipam/prefixes/?prefix={}".format(url_safe_ip)
        logger.info("checking for existing prefix in netbox: {}".format(url))
        check = self.fetcher(url)
        json_obj = json.loads(check)
        # logger.debug("response: {}".format(check))
        if json_obj["count"] == 1:
            return True, json_obj["results"][0]
        elif json_obj["count"] > 1:
            logger.error("duplicate prefixes exist. cleanup!")
            exit(2)
        else:
            return False, False

    def check_for_ip(self, data):
        url_safe_ip = urllib.parse.quote_plus(data["address"])
        url = self.base_url + "/ipam/ip-addresses/?address={}".format(url_safe_ip)
        logger.info("checking for existing ip in netbox: {}".format(url))
        check = self.fetcher(url)
        json_obj = json.loads(check)
        # logger.debug("response: {}".format(check))
        if json_obj["count"] == 1:
            return True
        elif json_obj["count"] > 1:
            logger.error("duplicate ip's exist. cleanup!")
            exit(2)
        else:
            return False

    def device_type_checker(self, device_model_name, attempt_import=True):
        if not self.device_types:
            self.device_types = {str(item.slug): dict(item) for item in self.py_netbox.dcim.device_types.all()}
        if not attempt_import:
            self.device_types = {str(item.slug): dict(item) for item in self.py_netbox.dcim.device_types.all()}
        slug_id = None
        if str(device_model_name) in device_type_map_preseed["by_key_name"].keys():
            logger.debug("hardware match")
            # print(str(devicedata['hardware']))
            nb_slug = device_type_map_preseed["by_key_name"][str(device_model_name)]["slug"]
            if nb_slug in self.device_types:
                logger.debug("found template in netbox")
                slug_id = self.device_types[nb_slug]["id"]
            elif attempt_import:
                logger.debug("did not find matching device template in netbox, attempting import")
                self.post_device_type(device_model_name, device_type_map_preseed["by_key_name"][str(device_model_name)])
                return self.device_type_checker(device_model_name, False)
            else:
                logger.debug("did not find matching device template in netbox")
                if not config["Misc"]["SKIP_DEVICES_WITHOUT_TEMPLATE"] == True:
                    logger.debug("device with no matching template by slugname {nb_slug} found")
                    exit(112)
        else:
            logger.debug("hardware type missing: {}".format(device_model_name))
        return slug_id

    def post_ip(self, data):
        url = self.base_url + "/ipam/ip-addresses/"
        exists = self.check_for_ip(data)
        if exists:
            logger.info("ip: {} already exists, skipping".format(data["address"]))
        else:
            logger.info("Posting IP data to {}".format(url))
            self.uploader(data, url)

    def get_sites(self):
        url = self.base_url + "/dcim/sites/"
        resp = self.fetcher(url)
        return json.loads(resp)["results"]

    def get_sites_keyd_by_description(self):
        sites = self.get_sites()
        resp = {}
        for site in sites:
            if site["description"] == "":
                logger.debug("site: {} {} has no description set, skipping".format(site["display"], site["url"]))
            else:
                if not site["description"] in resp.keys():
                    resp[site["description"]] = site
                else:
                    logger.debug("duplicate description detected! {}".format(site["description"]))
        return resp

    def post_rack(self, data):
        url = self.base_url + "/dcim/racks/"
        exists = self.check_if_rack_exists(data)
        if exists[0]:
            logger.info("rack: {} already exists, updating".format(data["name"]))
            url = url + "{}/".format(exists[1])
            self.uploader(data, url, "PUT")
        else:
            logger.info("Posting rack data to {}".format(url))
            self.uploader(data, url)

    def check_if_rack_exists(self, data):
        url_safe_ip = urllib.parse.quote_plus(data["name"])
        url = self.base_url + "/dcim/racks/?name={}".format(url_safe_ip)
        logger.info("checking for existing rack in netbox: {}".format(url))
        check = self.fetcher(url)
        json_obj = json.loads(check)
        if json_obj["count"] == 0:
            return False, False
        else:
            for rack in json_obj["results"]:
                if rack["site"]["id"] == data["site"]:
                    return True, rack["id"]
        return False
        # elif json_obj["count"] > 1:
        #     logger.error("duplicate ip's exist. cleanup!")
        #     exit(2)
        # else:
        #     return False

    def post_tag(self, tag, description):
        url = self.base_url + "/extras/tags/"
        data = {}
        data["name"] = str(tag)
        data["slug"] = str(tag).lower().replace(" ", "_")
        if not description is None:
            data["description"] = description
        self.uploader2(data, url)

    def get_tags_key_by_name(self):
        url = self.base_url + "/extras/tags/?limit=10000"
        resp = json.loads(self.fetcher(url))
        tags = {}
        for tag in resp["results"]:
            tags[tag["name"]] = tag
        logger.debug(tags)
        return tags

    def check_for_vlan_group(self, group_name):
        url = self.base_url + "/ipam/vlan-groups/?name={}".format(group_name)
        logger.info("checking for vlan-group in netbox: {}".format(url))
        check = self.fetcher(url)
        json_obj = json.loads(check)
        # logger.debug("response: {}".format(check))
        if json_obj["count"] == 1:
            logger.debug("found matching group")
            return True, json_obj["results"][0]
        elif json_obj["count"] > 1:
            logger.debug("duplcate groups detected, fix this")
            logger.debug(json_obj)
            exit(1)
        else:
            return False, False

    def get_vlan_groups_by_name(self):
        url = self.base_url + "/ipam/vlan-groups/?limit=10000"
        resp = json.loads(self.fetcher(url))
        groups = {}
        for group in resp["results"]:
            if group["name"] in groups.keys():
                logger.debug("duplicate group name exists! fix this. group: {}".format(group["name"]))
                exit(1)
            groups[group["name"]] = group
        logger.debug(groups)
        return groups

    def post_vlan_group(self, group_name, rt_id):
        url = self.base_url + "/ipam/vlan-groups/"
        data = {}
        data["name"] = str(group_name)
        data["description"] = str(group_name)
        slug_prep = str(group_name).lower().replace(" ", "-").replace(":", "")
        data["slug"] = slugify.slugify(slug_prep, separator="_")
        data["custom_fields"] = {"rt_id": rt_id}
        pp.pprint(data)
        if not self.check_for_vlan_group(group_name)[0]:
            self.uploader2(data, url)

    def check_for_vlan(self, data):
        url = self.base_url + "/ipam/vlans/?vid={}&group_id={}".format(data["vid"], data["group"])
        logger.info("checking for vlan in netbox: {}".format(url))
        check = self.fetcher(url)
        json_obj = json.loads(check)
        # logger.debug("response: {}".format(check))
        if json_obj["count"] == 1:
            logger.debug("matching vlan found")
            return True, json_obj["results"][0]
        elif json_obj["count"] > 1:
            logger.debug("duplcate vlans detected, fix this")
            logger.debug(json_obj)
            exit(1)
        else:
            return False, False

    def get_nb_vlans(self):
        vlans_by_netbox_id = {}
        url = self.base_url + "/ipam/vlans/?limit=10000"
        resp = json.loads(self.fetcher(url))
        for vlan in resp["results"]:
            vlans_by_netbox_id[vlan["id"]] = vlan
        return vlans_by_netbox_id

    def post_vlan(self, data):
        url = self.base_url + "/ipam/vlans/"
        exists = self.check_for_vlan(data)
        if exists[0]:
            logger.info("vlan: {} already exists, updating".format(data["name"]))
            url = url + "{}/".format(exists[1]["id"])
            self.uploader(data, url, "PUT")
        else:
            logger.info("Posting vlan data to {}".format(url))
            self.uploader(data, url)

    def post_device_type(self, device_type_key, device_type):
        logger.debug("post_device_type:")
        logger.debug(device_type_key)
        logger.debug(device_type)

        data = {}
        if "device_template_data" in device_type.keys():
            import_source = device_type["device_template_data"]
        else:
            import_source = device_type

        if "yaml_file" in import_source.keys():
            filename = import_source["yaml_file"]
            with open(filename, "r") as stream:
                try:
                    data = yaml.safe_load(stream)
                except yaml.YAMLError as exc:
                    logger.debug(f"failed to load {import_source['yaml_file']} for {device_type_key} template")
                    logger.debug(exc)
        if "yaml_url" in import_source.keys():
            try:
                resp = requests.get(import_source["yaml_url"])
                data = yaml.safe_load(resp.text)
            except:
                logger.debug(f"failed to load {import_source['yaml_url']} for {device_type_key} template")

        pp.pprint(data)
        man_data = {"name": data["manufacturer"], "slug": self.slugFormat(data["manufacturer"])}
        self.createManufacturers([man_data], py_netbox)
        data["manufacturer"] = man_data
        self.createDeviceTypes([data], py_netbox)
        self.device_types = {str(item.slug): dict(item) for item in self.py_netbox.dcim.device_types.all()}

    def post_device(self, data, py_netbox=None, has_problems=False):
        if not py_netbox:
            py_netbox = self.py_netbox
        needs_updating = False
        device_check1 = [item for item in py_netbox.dcim.devices.filter(cf_rt_id=data["custom_fields"]["rt_id"])]
        if len(device_check1) == 1:
            if device_check1[0]["custom_fields"]["rt_id"] == data["custom_fields"]["rt_id"]:
                logger.debug("device already in netbox (via rt_id). sending to update checker")
                needs_updating = True
                matched_by = "cf_rt_id"
        if not needs_updating:
            if "asset_tag" in data.keys():
                device_check2 = [str(item) for item in py_netbox.dcim.devices.filter(asset_tag=data["asset_tag"])]
                if len(device_check2) == 1:
                    logger.debug("device already in netbox (via asset_tag). sending to update checker")
                    needs_updating = True
                    matched_by = "asset_tag"
        if not needs_updating:
            device_check3 = [str(item) for item in py_netbox.dcim.devices.filter(name=data["name"])]
            if len(device_check3) == 1:
                logger.debug("device already in netbox (via name). sending to update checker")
                needs_updating = True
                matched_by = "name"

        if needs_updating:
            self.update_device(data, matched_by, py_netbox, has_problems)

        else:
            try:
                if has_problems:
                    data["status"] = "failed"
                py_netbox.dcim.devices.create(data)
            except pynetbox.RequestError as e:
                logger.debug("matched request error")
                pp.pprint(e.args)
                if "device with this Asset tag already exists" in str(e):
                    logger.debug("matched by asset tag")
                    matched_by = "asset_tag"
                    needs_updating = True
                elif "device with this name already exists" in str(e):
                    logger.debug("matched by name")
                    matched_by = "name"
                    needs_updating = True
            if needs_updating:  # update existing device
                self.update_device(data, matched_by, py_netbox, has_problems)

    def update_device(self, data, match_type, py_netbox, has_problems=False):

        if match_type == "cf_rt_id":
            device = py_netbox.dcim.devices.get(cf_rt_id=data["custom_fields"]["rt_id"])
        elif match_type == "asset_tag":
            device = py_netbox.dcim.devices.get(asset_tag=data["asset_tag"])
        elif match_type == "name":
            device = py_netbox.dcim.devices.get(name=data["name"])
        logger.debug("sending updates (if any) to nb")
        device.update(data)
        logger.info("checking to see if status is currently failed in nb")
        if str(device.status) == "Failed":
            if not has_problems:
                logger.info("attempting to update device status to active")
                device.update({"status": "active"})
        if has_problems:
            logger.info("device has_problems in rt")
            if str(device.status) == "Active":
                logger.info("attempting to update device status to failed")
                device.update({"status": "failed"})
            else:
                logger.info("will not update device status to failed as its been modified in NB")

    def create_device_interfaces(self, dev_id, dev_ints, ip_ints, force_int_type=False, int_type=None):
        print(f"checking for device via rt_dev_id:{dev_id}")
        nb_device = py_netbox.dcim.devices.get(cf_rt_id=str(dev_id))
        # print(dict(nb_device))
        dev_type = "device"

        if isinstance(nb_device, type(None)):
            logger.debug("did not find a device with that rt_id, will check for a vm now")
            nb_device = py_netbox.virtualization.virtual_machines.get(cf_rt_id=dev_id)
            dev_type = "vm"
            if not isinstance(nb_device, type(None)):
                logger.debug("found vm")

        if not "id" in dict(nb_device).keys():
            logger.error("did not find any device or with that rt_id")
            return False

        if dev_type == "device":
            nb_dev_ints = {str(item): item for item in self.py_netbox.dcim.interfaces.filter(device_id=int(nb_device.id))}
        elif dev_type == "vm":
            nb_dev_ints = {str(item): item for item in self.py_netbox.virtualization.interfaces.filter(virtual_machine_id=int(nb_device.id))}
        # pp.pprint(nb_dev_ints)
        if not int_type:
            int_type = "other"
        print(f"dev_ints:{dev_ints}")
        print(f"ip_ints: {ip_ints}")

        for dev_int in ip_ints:
            dev_int = dev_int.strip("\t")  # somehow i found an interafce with a tab at the end..
            if isinstance(dev_int, list):
                description = f"{dev_int[2]} rt_import"
            else:
                description = "rt_import"
            pp.pprint(nb_dev_ints)
            if not dev_int in nb_dev_ints.keys():
                print(f"{dev_int} not in nb_dev_ints, adding")
                dev_data = {
                    # "device":nb_device.id,
                    "name": dev_int,
                    "type": int_type,
                    "enabled": True,
                    "description": description,
                }
                print(dev_type)
                if dev_type == "device":
                    dev_data["device"] = nb_device.id
                    response = py_netbox.dcim.interfaces.create(dev_data)
                elif dev_type == "vm":
                    dev_data["virtual_machine"] = nb_device.id
                    response = py_netbox.virtualization.interfaces.create(dev_data)
                nb_dev_ints[dev_int] = response
            else:
                if not nb_dev_ints[dev_int].description == description:
                    nb_dev_ints[dev_int].update({"description": description})
                # print(response)
            for ip in ip_ints[dev_int]:
                print(ip)
                nb_ip = self.py_netbox.ipam.ip_addresses.get(address=ip)
                ip_update = {
                    "assigned_object_type": "dcim.interface",
                    "assigned_object_id": nb_dev_ints[dev_int].id,
                }
                if dev_type == "vm":
                    ip_update["assigned_object_type"] = "virtualization.vminterface"
                if nb_ip:
                    logger.debug("attempting to assign ip")
                    print(nb_ip.update(ip_update))
                else:
                    split_ip = ip.split("/")[0]
                    nb_ip2 = self.py_netbox.ipam.ip_addresses.get(address=split_ip)
                    if nb_ip2:
                        logger.debug("attempting to assign ip. found by removing /")
                        print(nb_ip2.update(ip_update))
                    else:
                        ip_update["address"] = ip
                        logger.debug(f"ip {ip} does not yet exist in nb. attempting create and assignment")
                        try:
                            print(self.py_netbox.ipam.ip_addresses.create(ip_update))
                        except:
                            logger.error("failed to create ip. probably a duplicate")

        for dev_int in dev_ints:

            if not "AC-" in dev_int[2] and not "RS-232" in dev_int[2]:
                # print(dev_int)
                if "empty" in dev_int[2]:
                    connected = False
                else:
                    connected = True
                description = f"{dev_int[2]} rt_import"
                if not dev_int[0] in nb_dev_ints.keys():
                    print(f"{dev_int[0]} not in nb_dev_ints, adding")
                    if not force_int_type:
                        map_list = {
                            "kvm": "other",
                            "10gbase-sr": "10gbase-x-sfpp",
                            "empty sfp+": "10gbase-x-sfpp",
                            "1000base-lx": "1000base-x-sfp",
                            "empty sfp-1000": "1000base-x-sfp",
                            "10gbase-lr": "1000base-x-sfp",
                            "1000base-sx": "1000base-x-sfp",
                            "empty qsfp": "40gbase-x-qsfpp",
                            "virtual port": "virtual",
                            "10gbase-zr-": "10gbase-x-sfpp",
                            "empty xfp": "1000base-x-sfp",
                            "empty sfp28": "25gbase-x-sfp28",
                            "empty qsfp": "100gbase-x-qsfp28",
                            "100gbase-sr4": "100gbase-x-qsfp28",
                            "100gbase-lr4": "100gbase-x-qsfp28",
                            "100gbase-er4": "100gbase-x-qsfp28",
                            "10gbase-er": "10gbase-x-sfpp",
                            "empty x2": "other",
                        }
                        int_type = dev_int[2].lower().split("dwdm80")[0].split("(")[0].strip()
                        if int_type in map_list.keys():
                            int_type = map_list[int_type]
                    int_data = {"name": dev_int[0], "type": int_type, "enabled": connected, "description": description}
                    if dev_type == "device":
                        int_data["device"] = device = nb_device.id
                        response = py_netbox.dcim.interfaces.create(int_data)
                    elif dev_type == "vm":
                        int_data["virtual_machine"] = nb_device.id
                        response = py_netbox.virtualization.interfaces.create(int_data)
                    nb_dev_ints[dev_int[0]] = response
                else:
                    if not nb_dev_ints[dev_int[0]].description == description:
                        nb_dev_ints[dev_int[0]].update(
                            {
                                "description": description,
                                "enabled": connected,
                            }
                        )
                # print(response)

    def get_sites_by_rt_id(self):
        nb = self.py_netbox
        sites = {str(item): dict(item) for item in nb.dcim.sites.all()}
        sites_by_rt_id = {}
        for site_name, site_data in sites.items():
            rt_id = site_data["custom_fields"]["rt_id"]
            if rt_id:
                sites_by_rt_id[site_data["custom_fields"]["rt_id"]] = site_data
        return sites_by_rt_id

    def get_rooms_by_rt_id(self):
        nb = self.py_netbox
        locations = [dict(item) for item in nb.dcim.locations.all()]
        # pp.pprint(locations)
        locations_by_rt_id = {}
        for location_data in locations:
            rt_id = location_data["custom_fields"]["rt_id"]
            if rt_id:
                locations_by_rt_id[location_data["custom_fields"]["rt_id"]] = location_data
        return locations_by_rt_id

    def manage_rooms(self, roomsdata):
        logger.debug("netbox:manage_rooms: starting")
        nb = self.py_netbox
        locations = [dict(item) for item in nb.dcim.locations.all()]
        # pp.pprint(locations)
        locations_by_rt_id = {}
        for location_data in locations:
            rt_id = location_data["custom_fields"]["rt_id"]
            if rt_id:
                locations_by_rt_id[location_data["custom_fields"]["rt_id"]] = location_data
        # pp.pprint(locations_by_rt_id)
        for room_id, room_data in roomsdata.items():
            pp.pprint(room_data)
            pp.pprint(locations_by_rt_id.keys())
            if not str(room_data["row_id"]) in locations_by_rt_id.keys():
                print(f"need to add location / row {room_data}")
                nb_site = self.get_sites_by_rt_id()[str(room_data["site_id"])]
                if nb_site:
                    print("found matching site, lets create a location")
                    nb_room_data = {
                        "name": room_data["row_name"],
                        "slug": str(slugify.slugify(room_data["row_name"], separator="_", replacements=[["/", ""], ["-", "_"]])),
                        "site": nb_site["id"],
                        "custom_fields": {"rt_id": str(room_data["row_id"])},
                    }
                    resp = nb.dcim.locations.create(nb_room_data)
                    if resp:
                        logger.debug(f"created location {room_data['row_name']} ")
                    else:
                        logger.error(f"failed to create location {room_data['row_name']} ")
                        pp.pprint(room_data)

            # exit(1)

    def post_building(self, data):
        url = self.base_url + "/dcim/sites/"
        logger.info("Uploading building data to {}".format(url))
        self.uploader(data, url)

    # modified/sourced from from: https://github.com/minitriga/Netbox-Device-Type-Library-Import
    def slugFormat(self, name):
        return re.sub("\W+", "-", name.lower())

    # modified/sourced from from: https://github.com/minitriga/Netbox-Device-Type-Library-Import
    def createManufacturers(self, vendors, nb):
        all_manufacturers = {str(item): item for item in nb.dcim.manufacturers.all()}
        need_manufacturers = []
        for vendor in vendors:
            try:
                manGet = all_manufacturers[vendor["name"]]
                logger.debug(f"Manufacturer Exists: {manGet.name} - {manGet.id}")
            except KeyError:
                need_manufacturers.append(vendor)

        if not need_manufacturers:
            return
        created = False
        count = 0
        while created == False and count < 3:
            try:
                manSuccess = nb.dcim.manufacturers.create(need_manufacturers)
                for man in manSuccess:
                    logger.debug(f"Manufacturer Created: {man.name} - " + f"{man.id}")
                    # counter.update({'manufacturer': 1})
                created = True
                count = 3
            except Exception as e:
                logger.debug(e.error)
                created = False
                count = count + 1
                sleep(0.5 * count)

    # modified/sourced from from: https://github.com/minitriga/Netbox-Device-Type-Library-Import
    def createInterfaces(self, interfaces, deviceType, nb):
        all_interfaces = {str(item): item for item in nb.dcim.interface_templates.filter(devicetype_id=deviceType)}
        need_interfaces = []
        for interface in interfaces:
            try:
                ifGet = all_interfaces[interface["name"]]
                logger.debug(f"Interface Template Exists: {ifGet.name} - {ifGet.type}" + f" - {ifGet.device_type.id} - {ifGet.id}")
            except KeyError:
                interface["device_type"] = deviceType
                need_interfaces.append(interface)

        if not need_interfaces:
            return
        created = False
        count = 0
        while created == False and count < 3:
            try:
                ifSuccess = nb.dcim.interface_templates.create(need_interfaces)
                for intf in ifSuccess:
                    logger.debug(f"Interface Template Created: {intf.name} - " + f"{intf.type} - {intf.device_type.id} - " + f"{intf.id}")
                    # counter.update({'updated': 1})
                    created = True
                    count = 3
            except Exception as e:
                logger.debug(e.error)
                created = False
                count = count + 1
                sleep(0.5 * count)

    # modified/sourced from from: https://github.com/minitriga/Netbox-Device-Type-Library-Import
    def createConsolePorts(self, consoleports, deviceType, nb):
        all_consoleports = {str(item): item for item in nb.dcim.console_port_templates.filter(devicetype_id=deviceType)}
        need_consoleports = []
        for consoleport in consoleports:
            try:
                cpGet = all_consoleports[consoleport["name"]]
                logger.debug(f"Console Port Template Exists: {cpGet.name} - " + f"{cpGet.type} - {cpGet.device_type.id} - {cpGet.id}")
            except KeyError:
                consoleport["device_type"] = deviceType
                need_consoleports.append(consoleport)

        if not need_consoleports:
            return
        created = False
        count = 0
        while created == False and count < 3:
            try:
                cpSuccess = nb.dcim.console_port_templates.create(need_consoleports)
                for port in cpSuccess:
                    logger.debug(f"Console Port Created: {port.name} - " + f"{port.type} - {port.device_type.id} - " + f"{port.id}")
                    # counter.update({'updated': 1})
                    created = True
                    count = 3
            except Exception as e:
                logger.debug(e.error)
                created = False
                count = count + 1
                sleep(0.5 * count)

    # modified/sourced from from: https://github.com/minitriga/Netbox-Device-Type-Library-Import
    def createPowerPorts(self, powerports, deviceType, nb):
        all_power_ports = {str(item): item for item in nb.dcim.power_port_templates.filter(devicetype_id=deviceType)}
        need_power_ports = []
        for powerport in powerports:
            try:
                ppGet = all_power_ports[powerport["name"]]
                logger.debug(f"Power Port Template Exists: {ppGet.name} - " + f"{ppGet.type} - {ppGet.device_type.id} - {ppGet.id}")
            except KeyError:
                powerport["device_type"] = deviceType
                need_power_ports.append(powerport)

        if not need_power_ports:
            return
        created = False
        count = 0
        while created == False and count < 3:
            try:
                ppSuccess = nb.dcim.power_port_templates.create(need_power_ports)
                for pp in ppSuccess:
                    logger.debug(f"Interface Template Created: {pp.name} - " + f"{pp.type} - {pp.device_type.id} - " + f"{pp.id}")
                    # counter.update({'updated': 1})
                    created = True
                    count = 3
            except Exception as e:
                logger.debug(e.error)
                created = False
                count = count + 1
                sleep(0.5 * count)

    # modified/sourced from from: https://github.com/minitriga/Netbox-Device-Type-Library-Import
    def createConsoleServerPorts(self, consoleserverports, deviceType, nb):
        all_consoleserverports = {str(item): item for item in nb.dcim.console_server_port_templates.filter(devicetype_id=deviceType)}
        need_consoleserverports = []
        for csport in consoleserverports:
            try:
                cspGet = all_consoleserverports[csport["name"]]
                logger.debug(f"Console Server Port Template Exists: {cspGet.name} - " + f"{cspGet.type} - {cspGet.device_type.id} - " + f"{cspGet.id}")
            except KeyError:
                csport["device_type"] = deviceType
                need_consoleserverports.append(csport)

        if not need_consoleserverports:
            return
        created = False
        count = 0
        while created == False and count < 3:
            try:
                cspSuccess = nb.dcim.console_server_port_templates.create(need_consoleserverports)
                for csp in cspSuccess:
                    logger.debug(f"Console Server Port Created: {csp.name} - " + f"{csp.type} - {csp.device_type.id} - " + f"{csp.id}")
                    # counter.update({'updated': 1})
                    created = True
                    count = 3
            except Exception as e:
                logger.debug(e.error)
                created = False
                count = count + 1
                sleep(0.5 * count)

    # modified/sourced from from: https://github.com/minitriga/Netbox-Device-Type-Library-Import
    def createFrontPorts(self, frontports, deviceType, nb):
        all_frontports = {str(item): item for item in nb.dcim.front_port_templates.filter(devicetype_id=deviceType)}
        need_frontports = []
        for frontport in frontports:
            try:
                fpGet = all_frontports[frontport["name"]]
                logger.debug(f"Front Port Template Exists: {fpGet.name} - " + f"{fpGet.type} - {fpGet.device_type.id} - {fpGet.id}")
            except KeyError:
                frontport["device_type"] = deviceType
                need_frontports.append(frontport)

        if not need_frontports:
            return

        all_rearports = {str(item): item for item in nb.dcim.rear_port_templates.filter(devicetype_id=deviceType)}
        for port in need_frontports:
            try:
                rpGet = all_rearports[port["rear_port"]]
                port["rear_port"] = rpGet.id
            except KeyError:
                logger.debug(f'Could not find Rear Port for Front Port: {port["name"]} - ' + f'{port["type"]} - {deviceType}')
        created = False
        count = 0
        while created == False and count < 3:
            try:
                fpSuccess = nb.dcim.front_port_templates.create(need_frontports)
                for fp in fpSuccess:
                    logger.debug(f"Front Port Created: {fp.name} - " + f"{fp.type} - {fp.device_type.id} - " + f"{fp.id}")
                    # counter.update({'updated': 1})
                    created = True
                    count = 3
            except Exception as e:
                logger.debug(e.error)
                created = False
                count = count + 1
                sleep(0.5 * count)

    # modified/sourced from from: https://github.com/minitriga/Netbox-Device-Type-Library-Import
    def createRearPorts(self, rearports, deviceType, nb):
        all_rearports = {str(item): item for item in nb.dcim.rear_port_templates.filter(devicetype_id=deviceType)}
        need_rearports = []
        for rearport in rearports:
            try:
                rpGet = all_rearports[rearport["name"]]
                logger.debug(f"Rear Port Template Exists: {rpGet.name} - {rpGet.type}" + f" - {rpGet.device_type.id} - {rpGet.id}")
            except KeyError:
                rearport["device_type"] = deviceType
                need_rearports.append(rearport)

        if not need_rearports:
            return
        created = False
        count = 0
        while created == False and count < 3:
            try:
                rpSuccess = nb.dcim.rear_port_templates.create(need_rearports)
                for rp in rpSuccess:
                    logger.debug(f"Rear Port Created: {rp.name} - {rp.type}" + f" - {rp.device_type.id} - {rp.id}")
                    # counter.update({'updated': 1})
                    created = True
                    count = 3
            except Exception as e:
                logger.debug(e.error)
                created = False
                count = count + 1
                sleep(0.5 * count)

    # modified/sourced from from: https://github.com/minitriga/Netbox-Device-Type-Library-Import
    def createDeviceBays(self, devicebays, deviceType, nb):
        all_devicebays = {str(item): item for item in nb.dcim.device_bay_templates.filter(devicetype_id=deviceType)}
        need_devicebays = []
        for devicebay in devicebays:
            try:
                dbGet = all_devicebays[devicebay["name"]]
                logger.debug(f"Device Bay Template Exists: {dbGet.name} - " + f"{dbGet.device_type.id} - {dbGet.id}")
            except KeyError:
                devicebay["device_type"] = deviceType
                need_devicebays.append(devicebay)

        if not need_devicebays:
            return
        created = False
        count = 0
        while created == False and count < 3:
            try:
                dbSuccess = nb.dcim.device_bay_templates.create(need_devicebays)
                for db in dbSuccess:
                    logger.debug(f"Device Bay Created: {db.name} - " + f"{db.device_type.id} - {db.id}")
                    # counter.update({'updated': 1})
                created = True
                count = 3
            except Exception as e:
                logger.debug(e.error)
                created = False
                count = count + 1
                sleep(0.5 * count)

    # modified/sourced from from: https://github.com/minitriga/Netbox-Device-Type-Library-Import
    def createPowerOutlets(self, poweroutlets, deviceType, nb):
        all_poweroutlets = {str(item): item for item in nb.dcim.power_outlet_templates.filter(devicetype_id=deviceType)}
        need_poweroutlets = []
        for poweroutlet in poweroutlets:
            try:
                poGet = all_poweroutlets[poweroutlet["name"]]
                logger.debug(f"Power Outlet Template Exists: {poGet.name} - " + f"{poGet.type} - {poGet.device_type.id} - {poGet.id}")
            except KeyError:
                poweroutlet["device_type"] = deviceType
                need_poweroutlets.append(poweroutlet)

        if not need_poweroutlets:
            return

        all_power_ports = {str(item): item for item in nb.dcim.power_port_templates.filter(devicetype_id=deviceType)}
        for outlet in need_poweroutlets:
            try:
                ppGet = all_power_ports[outlet["power_port"]]
                outlet["power_port"] = ppGet.id
            except KeyError:
                pass
        created = False
        count = 0
        while created == False and count < 3:
            try:
                poSuccess = nb.dcim.power_outlet_templates.create(need_poweroutlets)
                for po in poSuccess:
                    logger.debug(f"Power Outlet Created: {po.name} - " + f"{po.type} - {po.device_type.id} - " + f"{po.id}")
                    # counter.update({'updated': 1})
                    created = True
                    count = 3
            except Exception as e:
                logger.debug(e.error)
                created = False
                count = count + 1
                sleep(0.5 * count)

    # modified/sourced from from: https://github.com/minitriga/Netbox-Device-Type-Library-Import
    def createDeviceTypes(self, deviceTypes, nb=None):
        nb = self.py_netbox
        all_device_types = {str(item): item for item in nb.dcim.device_types.all()}
        for deviceType in deviceTypes:
            try:
                dt = all_device_types[deviceType["model"]]
                logger.debug(f"Device Type Exists: {dt.manufacturer.name} - " + f"{dt.model} - {dt.id}")
            except KeyError:
                try:
                    dt = nb.dcim.device_types.create(deviceType)
                    # counter.update({'added': 1})
                    logger.debug(f"Device Type Created: {dt.manufacturer.name} - " + f"{dt.model} - {dt.id}")
                except Exception as e:
                    logger.debug(e.error)

            if "interfaces" in deviceType:
                logger.debug("interfaces")
                self.createInterfaces(deviceType["interfaces"], dt.id, nb)
            if "power-ports" in deviceType:
                logger.debug("power-ports")
                self.createPowerPorts(deviceType["power-ports"], dt.id, nb)
            if "power-port" in deviceType:
                logger.debug("power-port")
                self.createPowerPorts(deviceType["power-port"], dt.id, nb)
            if "console-ports" in deviceType:
                logger.debug("console-port")
                self.createConsolePorts(deviceType["console-ports"], dt.id, nb)
            if "power-outlets" in deviceType:
                logger.debug("power-outlets")
                self.createPowerOutlets(deviceType["power-outlets"], dt.id, nb)
            if "console-server-ports" in deviceType:
                logger.debug("console-server-ports")
                self.createConsoleServerPorts(deviceType["console-server-ports"], dt.id, nb)
            if "rear-ports" in deviceType:
                logger.debug("rear-ports")
                self.createRearPorts(deviceType["rear-ports"], dt.id, nb)
            if "front-ports" in deviceType:
                logger.debug("front-ports")
                self.createFrontPorts(deviceType["front-ports"], dt.id, nb)
            if "device-bays" in deviceType:
                logger.debug("device-bays")
                self.createDeviceBays(deviceType["device-bays"], dt.id, nb)

    def change_attrib_type(self, attrib):
        if attrib in ["uint", "int", "float"]:
            attrib = "text"
        if attrib in ["bool"]:
            attrib = "boolean"
        if attrib in ["string", "dict"]:
            attrib = "text"
        return attrib

    def cleanup_attrib_value(self, attrib_val, attrib_type):
        if attrib_type in ["uint", "int", "float"]:
            return str(attrib_val)
        if attrib_type in ["bool"]:
            return bool(attrib_val)
        if attrib_type in ["string", "dict", "text"]:
            return str(attrib_val)
        if attrib_type == "date":
            datetime_time = datetime.datetime.fromtimestamp(int(attrib_val))
            return datetime_time.strftime("%Y-%m-%d")
        return str(attrib_val)

    def createCustomFields(self, attributes):
        logger.debug(attributes)
        nb = self.py_netbox
        all_custom_fields = {str(item): item for item in nb.extras.custom_fields.all()}
        logger.debug(all_custom_fields)
        for custom_field in attributes:
            custom_field["label"] = copy.copy(custom_field["name"])
            custom_field["name"] = str(slugify.slugify(custom_field["name"], separator="_", replacements=[["/", ""], ["-", "_"]]))
            try:
                # print(custom_field["name"])
                # print(all_custom_fields[custom_field["name"]])
                if custom_field["label"] in all_custom_fields.keys():
                    dt = all_custom_fields[custom_field["label"]]
                    if not str(dt.name) == custom_field["name"]:
                        logger.debug(f"name is not correctly set on custom field {custom_field['label']}, updating, this may take some time")
                        dt.update({"name": custom_field["name"], "label": custom_field["label"]})
                        all_custom_fields = {str(item): item for item in nb.extras.custom_fields.all()}
                dt = all_custom_fields[custom_field["name"]]
                logger.debug(f"Custom Field Exists: {dt.name} - " + f"{dt.type}")
            except KeyError:
                try:
                    custom_field["type"] = self.change_attrib_type(custom_field["type"])
                    custom_field["content_types"] = [
                        "circuits.circuit",
                        "circuits.circuittype",
                        "circuits.provider",
                        "circuits.providernetwork",
                        "dcim.cable",
                        "dcim.consoleport",
                        "dcim.consoleserverport",
                        "dcim.device",
                        "dcim.devicebay",
                        "dcim.devicerole",
                        "dcim.devicetype",
                        "dcim.frontport",
                        "dcim.interface",
                        "dcim.inventoryitem",
                        "dcim.location",
                        "dcim.manufacturer",
                        "dcim.platform",
                        "dcim.powerfeed",
                        "dcim.poweroutlet",
                        "dcim.powerpanel",
                        "dcim.powerport",
                        "dcim.rack",
                        "dcim.rackreservation",
                        "dcim.rackrole",
                        "dcim.rearport",
                        "dcim.region",
                        "dcim.site",
                        "dcim.sitegroup",
                        "dcim.virtualchassis",
                        "ipam.aggregate",
                        "ipam.ipaddress",
                        "ipam.prefix",
                        "ipam.rir",
                        "ipam.role",
                        "ipam.routetarget",
                        "ipam.vrf",
                        "ipam.vlangroup",
                        "ipam.vlan",
                        "ipam.service",
                        "ipam.iprange",
                        "tenancy.tenantgroup",
                        "tenancy.tenant",
                        "virtualization.cluster",
                        "virtualization.clustergroup",
                        "virtualization.clustertype",
                        "virtualization.virtualmachine",
                        "virtualization.vminterface",
                    ]
                    dt = nb.extras.custom_fields.create(custom_field)
                    # counter.update({'added': 1})
                    logger.debug(f"Device Type Created: {dt.name} - " + f"{dt.type} ")
                    # print("test")
                except Exception as e:
                    logger.error(f"failed to add custom field: {custom_field['name']}")
                    logger.debug(e)

    def get_rack_by_rt_id(self, rt_id):
        nb = self.py_netbox
        racks = [item for item in nb.dcim.racks.filter(cf_rt_id=rt_id)]
        logger.debug(racks)
        if len(racks) == 1:
            return racks[0]
        elif len(racks) > 1:
            for rack in racks:
                if rack["custom_fields"]["rt_id"] == str(rt_id):
                    return rack
            return None
        else:
            return None

    def get_site_by_rt_id(self, rt_id):
        nb = self.py_netbox
        sites = [item for item in nb.dcim.sites.filter(cf_rt_id=rt_id)]
        logger.debug(sites)
        if len(sites) == 1:
            return sites[0]
        elif len(sites) > 1:
            for rack in sites:
                if rack["custom_fields"]["rt_id"] == str(rt_id):
                    return rack
            return None
        else:
            return None

    def manage_sites(self, rt_sites_map):
        nb = self.py_netbox
        current_sites = [str(item) for item in nb.dcim.sites.all()]

        for rt_id, name in rt_sites_map.items():
            if config["Misc"]["SITE_NAME_CLEANUP"]:
                description = copy.deepcopy(name)
                name = name.split(" (")[0]
            site_data = {"description": description, "name": name, "slug": slugify.slugify(name), "custom_fields": {"rt_id": str(rt_id)}}
            if not name in current_sites:
                pp.pprint(f"{name} not in netbox, adding")
                print(nb.dcim.sites.create(site_data))
            else:
                site = nb.dcim.sites.get(name=name)
                site.update(site_data)

    def create_cable(self, int_1_id, int_2_id):
        nb = self.py_netbox
        data = {
            "termination_a_type": "dcim.interface",
            "termination_a_id": int_1_id,
            "termination_b_type": "dcim.interface",
            "termination_b_id": int_2_id,
        }
        try:
            created = nb.dcim.cables.create(data)
            pp.pprint(created)
        except Exception as e:
            logger.debug("unable to create cable, usually means a cable already exists...")
            logger.error(e)

    def create_cables_between_devices(self, connection_data):
        nb = self.py_netbox
        local_device_obj = nb.dcim.devices.filter(cf_rt_id=connection_data["local_device_rt_id"])
        local_device = {str(item): dict(item) for item in local_device_obj}
        if bool(local_device):
            local_device = list(local_device.values())[0]
        # local_device_dict = { str(local_device): dict(local_device) }
        # pp.pprint(local_device)

        remote_device_obj = nb.dcim.devices.filter(cf_rt_id=connection_data["remote_device"]["id"])
        remote_device = {str(item): dict(item) for item in remote_device_obj}
        if bool(remote_device):
            remote_device = list(remote_device.values())[0]
        # remote_device = nb.dcim.devices.filter(cf_rt_id=connection_data["remote_device"]["id"])
        # pp.pprint(remote_device)
        if bool(local_device) and bool(remote_device):

            local_device_ints_objs = nb.dcim.interfaces.filter(device_id=local_device["id"])
            local_device_ints = {str(item): item for item in local_device_ints_objs}
            # pp.pprint(local_device_ints)
            remote_device_ints_objs = nb.dcim.interfaces.filter(device_id=remote_device["id"])
            remote_device_ints = {str(item): item for item in remote_device_ints_objs}
            # pp.pprint(remote_device_ints)

            local_port_found = False

            if connection_data["local_port"] in local_device_ints.keys():
                logger.debug("found local_port in netbox")
                local_port_found = True
                local_port = local_device_ints[connection_data["local_port"]]
                # local_port_dict = {str(item): item for item in local_port}

            else:
                logger.error(f"did not find local_port({connection_data['local_port']}) in netbox...")
            remote_port_found = False
            if connection_data["remote_port"] in remote_device_ints.keys():
                logger.debug("found remote_port in netbox")
                remote_port_found = True
                remote_port = remote_device_ints[connection_data["remote_port"]]
                # remote_port_dict = {str(item): item for item in remote_port}
            else:
                logger.error(f"did not find remote_port({connection_data['remote_port']}) in netbox for device {remote_device['name']}")

            if local_port_found and remote_port_found:
                # port may be set to Virtual if it didnt exist in device template when syned over. fix if needed
                if str(remote_port.type) == "Virtual":
                    remote_port.update({"type": "other"})
                if str(local_port.type) == "Virtual":
                    local_port.update({"type": "other"})
                # the actual meat of the function.... why did it take soo much to get here? definately monday code....
                self.create_cable(local_port.id, remote_port.id)

        else:
            logger.warning("remote device doesnt exist in nb yet. connections will be added when it gets added")

    def manage_vm(self, vm_data):
        nb = self.py_netbox
        rt_id = vm_data["custom_fields"]["rt_id"]
        vm_data = self.get_vm_cluster_from_device(vm_data)
        pp.pprint(vm_data)
        device_check1 = nb.virtualization.virtual_machines.get(cf_rt_id=rt_id)
        # device_check2 = nb.virtualization.virtual_machines.filter(name=vm_data["name"])
        device_check2 = None
        if device_check1:
            logger.debug("found existing vm in netbox, will update")
            device_check1.update(vm_data)
        elif device_check2:
            logger.debug("found existing vm in netbox by name (dangerious)")
            device_check2.update(vm_data)
        else:
            logger.debug("did not find an existing vm in nb, will add!")
            new_device = nb.virtualization.virtual_machines.create(vm_data)

    def get_vm_cluster_from_device(self, vm_data):
        nb = self.py_netbox
        vm_data["cluster"] = str(config["Misc"]["DEFAULT_VM_CLUSTER_ID"])
        if "rt_id_parent" in vm_data["custom_fields"].keys():

            cluster = nb.virtualization.clusters.get(cf_rt_id=vm_data["custom_fields"]["rt_id_parent"])
            if cluster:
                logger.debug(f"cluster {cluster.name} found in nb")
                vm_data["cluster"] = cluster.id
            else:
                parent_device = nb.dcim.devices.get(cf_rt_id=vm_data["custom_fields"]["rt_id_parent"])
                if parent_device:
                    logger.debug(f"parent {parent_device.name} found in nb, attempting to create matching cluster")
                    cluster_type = nb.virtualization.cluster_types.get(name="rt_import")
                    if not cluster_type:
                        cluster_type = nb.virtualization.cluster_types.create({"name": "rt_import", "slug": "rt_import"})
                        if not cluster_type:
                            logger.debug("something went wrong. defaulting clusterid to conf")
                            return vm_data
                    cluster = nb.virtualization.clusters.create(
                        {"name": parent_device.name, "type": cluster_type.id, "custom_fields": {"rt_id": vm_data["custom_fields"]["rt_id_parent"]}}
                    )
                    if cluster:
                        logger.debug(f"cluster {cluster.name} created")
                        parent_device.update({"cluster": cluster.id})
                        vm_data["cluster"] = cluster.id

        return vm_data

    def remove_device_by_rt_id(self, rt_id):
        nb = self.py_netbox
        try:
            nb_device = nb.dcim.devices.get(cf_rt_id=str(rt_id))

            if not dict(nb_device):
                logger.info("found device in netbox by rt_id, removing")
                nb_device.delete()

        except:
            logger.info("failed to find / remove device from netbox")

    def get_ip_prefix_size(self, ip):
        nb = self.py_netbox
        if not netbox.all_prefixes:
            print("getting all prefixes(s) currently in netbox")
            netbox.all_prefixes = {str(item): dict(item) for item in netbox.py_netbox.ipam.prefixes.all()}
            # print(json.dumps(netbox.all_prefixes))
            # exit()
        nb_all_prefixes = netbox.all_prefixes
        smallest_prefix = 0
        found_prefix = None
        for prefix in nb_all_prefixes.keys():
            if ip in ipcalc.Network(prefix):
                found_prefix = True
                print(f"ip: {ip} in prefix: {prefix}")
                subnet_size = prefix.split("/")[1]
                if int(subnet_size) > smallest_prefix:
                    smallest_prefix = int(subnet_size)
                    found_prefix = prefix
        if found_prefix:
            return smallest_prefix
        else:
            return None

    def update_object_file_links(self, object_type, object_id, file_links):
        nb = self.py_netbox
        update_data = {"custom_fields": {"external_urls": file_links}}
        if object_type == "object":
            # might be device or vm
            print(f"checking for device via rt_dev_id:{object_id}")
            nb_device = py_netbox.dcim.devices.get(cf_rt_id=str(object_id))
            # print(dict(nb_device))
            dev_type = "device"

            if isinstance(nb_device, type(None)):
                logger.debug("did not find a device with that rt_id, will check for a vm now")
                nb_device = py_netbox.virtualization.virtual_machines.get(cf_rt_id=str(object_id))
                dev_type = "vm"
                if not isinstance(nb_device, type(None)):
                    logger.debug("found vm")
                else:
                    logger.error("did not find device or vm with that ID")
                    dev_type = None
            if dev_type:
                nb_device.update(update_data)
        elif object_type == "rack":
            dev_type = "rack"
            nb_rack = py_netbox.dcim.racks.get(cf_rt_id=str(object_id))
            if nb_rack:
                nb_rack.update(update_data)
        else:
            dev_type = object_type

        print(dev_type)


class DB(object):
    """
    Fetching data from Racktables and converting them to Device42 API format.
    """

    def __init__(self):
        self.con = None
        self.hardware = None
        self.tag_map = None
        self.vlan_group_map = None
        self.vlan_map = None
        self.tables = []
        self.rack_map = []
        self.vm_hosts = {}
        self.chassis = {}
        self.rack_id_map = {}
        self.container_map = {}
        self.building_room_map = {}
        self.skipped_devices = {}
        self.all_ports = None
        self.nb_roles = None

    def custom_field_name_slugger(self, name):
        return str(slugify.slugify(name, separator="_", replacements=[["/", ""], ["-", "_"]]))

    def connect(self):
        """
        Connection to RT database
        :return:
        """
        self.con = pymysql.connect(
            host=config["MySQL"]["DB_IP"],
            port=int(config["MySQL"]["DB_PORT"]),
            db=config["MySQL"]["DB_NAME"],
            user=config["MySQL"]["DB_USER"],
            passwd=config["MySQL"]["DB_PWD"],
        )

        self.con.query("SET SESSION interactive_timeout=60")
        # self.con.query('SET SESSION wait_timeout=3600')

    @staticmethod
    def convert_ip(ip_raw):
        """
        IP address conversion to human readable format
        :param ip_raw:
        :return:
        """
        ip = socket.inet_ntoa(struct.pack("!I", ip_raw))
        return ip

    @staticmethod
    def convert_ip_v6(ip_raw):
        ip = socket.inet_ntop(socket.AF_INET6, ip_raw)
        return ip

    def nb_role_id(self, role_name):
        if not self.nb_roles:
            self.nb_roles = {str(item.name): dict(item) for item in py_netbox.dcim.device_roles.all()}
        if not role_name in self.nb_roles.keys():
            create_role = {
                "name": role_name,
                "slug": self.custom_field_name_slugger(role_name),
            }
            py_netbox.dcim.device_roles.create(create_role)
            self.nb_roles = {str(item.name): dict(item) for item in py_netbox.dcim.device_roles.all()}
        return self.nb_roles[role_name]["id"]

    def get_ips(self):
        """
        Fetch IPs from RT and send them to upload function
        :return:
        """
        adrese = []
        if not self.con:
            self.connect()
        with self.con:
            cur = self.con.cursor()
            q = "SELECT * FROM IPv4Address;"
            cur.execute(q)
            ips = cur.fetchall()
            if config["Log"]["DEBUG"]:
                msg = ("IPs", str(ips))
                logger.debug(msg)
            cur.close()
            cur2 = self.con.cursor()
            q2 = "SELECT object_id,ip FROM IPv4Allocation;"
            cur2.execute(q2)
            ip_by_allocation = cur2.fetchall()
            if config["Log"]["DEBUG"]:
                msg = ("IPs", str(ip_by_allocation))
                logger.debug(msg)
            cur2.close()
            self.con = None

        if not netbox.all_prefixes:
            print("getting all prefixes(s) currently in netbox")
            netbox.all_prefixes = {str(item): dict(item) for item in netbox.py_netbox.ipam.prefixes.all()}
            # print(json.dumps(netbox.all_prefixes))
            # exit()
        nb_all_prefixes = netbox.all_prefixes

        if not netbox.all_ips:
            print("getting all ip(s) currently in netbox")
            netbox.all_ips = {str(f"{item}_{item.id}"): item for item in netbox.py_netbox.ipam.ip_addresses.all()}
        nb_ips = netbox.all_ips

        print("checking ips")
        for line in ips:
            net = {}
            found_matching_prefix = False
            smallest_prefix = 0
            found_prefix = None

            ip_raw, name, comment, reserved = line
            ip = self.convert_ip(ip_raw)
            adrese.append(ip)

            net.update({"address": ip})
            msg = "IP Address: %s" % ip
            logger.info(msg)

            desc = " ".join([name, comment]).strip()
            net.update({"description": desc})
            msg = "Label: %s" % desc
            logger.info(msg)
            if not desc in ["network", "broadcast"]:
                # this is disgusting...
                for prefix in nb_all_prefixes.keys():
                    if ip in ipcalc.Network(prefix):
                        print(f"ip: {ip} in prefix: {prefix}")
                        subnet_size = prefix.split("/")[1]
                        if int(subnet_size) > smallest_prefix:
                            smallest_prefix = int(subnet_size)
                            found_prefix = prefix
                print(f"prefix to be used: {found_prefix}")
                if smallest_prefix > 0:
                    net["address"] = f"{ip}/{smallest_prefix}"
                    # net['display'] = net['address']
                found_in_nb = False
                found_in_nb_obj = None
                for nb_ip, nb_ip_obj in nb_ips.items():
                    if nb_ip.startswith(f"{ip}/"):
                        if found_in_nb:
                            # duplicate cound as its already found. nuke
                            logger.info("duplicate found. removing")
                            try:
                                nb_ip_obj.delete()
                            except:
                                logger.error("failed to delete. might already be gone")
                        else:
                            found_in_nb = True
                            found_in_nb_obj = nb_ip_obj
                            print(f"found in nb!: {nb_ip_obj.address}")
                if found_in_nb:
                    print("i should update the nb ip here")
                    print(net)
                    print(found_in_nb_obj)
                    print(found_in_nb_obj.update(net))
                    print(found_in_nb_obj)
                else:
                    netbox.post_ip(net)
            else:
                logger.info("skipping due to network/broadcast ip")
        print("checking ip alocations")
        for line in ip_by_allocation:
            net = {}
            found_matching_prefix = False
            smallest_prefix = 0
            found_prefix = None
            object_id, allocationip_raw = line
            ip = self.convert_ip(allocationip_raw)
            if not ip in adrese:
                # this is disgusting...
                for prefix in nb_all_prefixes.keys():
                    if ip in ipcalc.Network(prefix):
                        print(f"ip: {ip} in prefix: {prefix}")
                        subnet_size = prefix.split("/")[1]
                        if int(subnet_size) > smallest_prefix:
                            smallest_prefix = int(subnet_size)
                            found_prefix = prefix
                print(f"prefix to be used: {found_prefix}")
                if smallest_prefix > 0:
                    net["address"] = f"{ip}/{smallest_prefix}"
                    # net['display'] = net['address']
                found_in_nb = False
                found_in_nb_obj = None
                for nb_ip, nb_ip_obj in nb_ips.items():
                    if nb_ip.startswith(f"{ip}/"):
                        if found_in_nb:
                            # duplicate cound as its already found. nuke
                            logger.info("duplicate found. removing")
                            try:
                                nb_ip_obj.delete()
                            except:
                                logger.error("failed to delete. might already be gone")
                        else:
                            found_in_nb = True
                            found_in_nb_obj = nb_ip_obj
                            print(f"found in nb!: {nb_ip_obj.address}")
                if found_in_nb:
                    print("i should update the nb ip here")
                    print(net)
                    print(found_in_nb_obj.update(net))
                else:
                    logger.info(msg)
                    netbox.post_ip(net)

    def get_ips_v6(self):
        """
        Fetch v6 IPs from RT and send them to upload function
        :return:
        """
        adrese = []
        if not self.con:
            self.connect()
        with self.con:
            cur = self.con.cursor()
            q = "SELECT * FROM IPv6Address;"
            cur.execute(q)
            ips = cur.fetchall()
            if config["Log"]["DEBUG"]:
                msg = ("IPs", str(ips))
                logger.debug(msg)
            cur.close()
            cur2 = self.con.cursor()
            q2 = "SELECT object_id,ip FROM IPv6Allocation;"
            cur2.execute(q2)
            ip_by_allocation = cur2.fetchall()
            if config["Log"]["DEBUG"]:
                msg = ("IPs", str(ip_by_allocation))
                logger.debug(msg)
            cur2.close()
            self.con = None
        if not netbox.all_ips:
            netbox.all_ips = {str(f"{item}_{item.id}"): item for item in netbox.py_netbox.ipam.ip_addresses.all()}
        nb_ips = netbox.all_ips
        if not netbox.all_prefixes:
            print("getting all prefixes(s) currently in netbox")
            netbox.all_prefixes = {str(item): dict(item) for item in netbox.py_netbox.ipam.prefixes.all()}
        nb_all_prefixes = netbox.all_prefixes
        for line in ips:
            net = {}
            found_matching_prefix = False
            smallest_prefix = 0
            found_prefix = None
            ip_raw, name, comment, reserved = line
            ip = self.convert_ip_v6(ip_raw)
            adrese.append(ip)

            net.update({"address": ip})
            msg = "IP Address: %s" % ip
            logger.info(msg)

            desc = " ".join([name, comment]).strip()
            net.update({"description": desc})
            msg = "Label: %s" % desc
            logger.info(msg)
            if not desc in ["network", "broadcast"]:
                # dry this out with get_ip_prefix_size
                for prefix in nb_all_prefixes.keys():
                    if ip in ipcalc.Network(prefix):
                        print(f"ip: {ip} in prefix: {prefix}")
                        subnet_size = prefix.split("/")[1]
                        if int(subnet_size) > smallest_prefix:
                            smallest_prefix = int(subnet_size)
                            found_prefix = prefix
                print(f"prefix to be used: {found_prefix}")
                if smallest_prefix > 0:
                    net["address"] = f"{ip}/{smallest_prefix}"
                    # net['display'] = net['address']
                found_in_nb = False
                found_in_nb_obj = None
                for nb_ip, nb_ip_obj in nb_ips.items():
                    if nb_ip.startswith(f"{ip}/"):
                        if found_in_nb:
                            # duplicate cound as its already found. nuke
                            logger.info("duplicate found. removing")
                            try:
                                nb_ip_obj.delete()
                            except:
                                logger.error("failed to delete. might already be gone")
                        else:
                            found_in_nb = True
                            found_in_nb_obj = nb_ip_obj
                            print(f"found in nb!: {nb_ip_obj.address}")
                if found_in_nb:
                    print("i should update the nb ip here")
                    print(net)
                    print(found_in_nb_obj.update(net))
                else:
                    netbox.post_ip(net)

        for line in ip_by_allocation:
            net = {}
            smallest_prefix = 0
            found_prefix = None
            object_id, allocationip_raw = line
            ip = self.convert_ip_v6(allocationip_raw)
            if not ip in adrese:
                # dry this out with get_ip_prefix_size
                for prefix in nb_all_prefixes.keys():
                    if ip in ipcalc.Network(prefix):
                        print(f"ip: {ip} in prefix: {prefix}")
                        subnet_size = prefix.split("/")[1]
                        if int(subnet_size) > smallest_prefix:
                            smallest_prefix = int(subnet_size)
                            found_prefix = prefix
                print(f"prefix to be used: {found_prefix}")
                if smallest_prefix > 0:
                    net["address"] = f"{ip}/{smallest_prefix}"
                    # net['display'] = net['address']
                found_in_nb = False
                found_in_nb_obj = None
                for nb_ip, nb_ip_obj in nb_ips.items():
                    if nb_ip.startswith(f"{ip}/"):
                        if found_in_nb:
                            # duplicate cound as its already found. nuke
                            logger.info("duplicate found. removing")
                            try:
                                nb_ip_obj.delete()
                            except:
                                logger.error("failed to delete. might already be gone")
                        else:
                            found_in_nb = True
                            found_in_nb_obj = nb_ip_obj
                            print(f"found in nb!: {nb_ip_obj.address}")
                if found_in_nb:
                    print("i should update the nb ip here")
                    print(net)
                    print(found_in_nb_obj.update(net))
                else:
                    logger.info(msg)
                    netbox.post_ip(net)

    def create_tag_map(self):
        logger.debug("creating tag map")
        self.tag_map = netbox.get_tags_key_by_name()
        logger.debug("there are {} tags cached".format(len(self.tag_map)))
        logger.debug(self.tag_map.keys())

    def get_subnets(self):
        """
        Fetch subnets from RT and send them to upload function
        :return:
        """

        if not self.vlan_group_map:
            self.create_vlan_domains_nb_group_map()
        if not self.vlan_map:
            self.create_vlan_nb_map()
        if not self.con:
            self.connect()
        with self.con:
            cur = self.con.cursor()
            q = "SELECT * FROM IPv4Network LEFT JOIN VLANIPv4 on IPv4Network.id = VLANIPv4.ipv4net_id"
            cur.execute(q)
            subnets = cur.fetchall()
            if config["Log"]["DEBUG"]:
                msg = ("Subnets", str(subnets))
                logger.debug(msg)
            cur.close()
            self.con = None

        for line in subnets:
            subs = {}
            if not self.tag_map:
                self.create_tag_map()
            sid, raw_sub, mask, name, comment, vlan_domain_id, vlan_id, ipv4net_id = line
            subnet = self.convert_ip(raw_sub)
            rt_tags = self.get_tags_for_obj("ipv4net", sid)
            # print(rt_tags)
            tags = []
            # print (self.tag_map)
            # if not comment == None:
            #     name = "{} {}".format(name, comment)
            for tag in rt_tags:
                try:
                    # print(tag)
                    tags.append(self.tag_map[tag]["id"])
                except:
                    logger.debug("failed to find tag {} in lookup map".format(tag))
            if not vlan_id is None:
                try:
                    vlan = self.vlan_map["{}_{}".format(vlan_domain_id, vlan_id)]["id"]
                    subs.update({"vlan": vlan})
                except:
                    logger.debug("failed to find vlan for subnet {}".format(subnet))
            else:
                subs.update({"vlan": None})
            subs.update({"prefix": "/".join([subnet, str(mask)])})
            subs.update({"status": "active"})
            # subs.update({'mask_bits': str(mask)})
            subs.update({"description": name})
            subs.update({"tags": tags})
            netbox.post_subnet(subs)

    def get_subnets_v6(self):
        """
        Fetch subnets from RT and send them to upload function
        :return:
        """
        if not self.vlan_group_map:
            self.create_vlan_domains_nb_group_map()
        if not self.vlan_map:
            self.create_vlan_nb_map()
        if not self.con:
            self.connect()
        with self.con:
            cur = self.con.cursor()
            q = "SELECT * FROM IPv6Network LEFT JOIN VLANIPv6 on IPv6Network.id = VLANIPv6.ipv6net_id"
            cur.execute(q)
            subnets = cur.fetchall()
            if config["Log"]["DEBUG"]:
                msg = ("Subnets", str(subnets))
                logger.debug(msg)
            cur.close()
            self.con = None

        for line in subnets:
            subs = {}
            if not self.tag_map:
                self.create_tag_map()
            sid, raw_sub, mask, last_ip, name, comment, vlan_domain_id, vlan_id, ipv6net_id = line
            subnet = self.convert_ip_v6(raw_sub)

            rt_tags = self.get_tags_for_obj("ipv6net", sid)
            # print(rt_tags)
            tags = []
            # print (self.tag_map)
            if not comment == None:
                name = "{} {}".format(name, comment)
            for tag in rt_tags:
                try:
                    # print(tag)
                    tags.append(self.tag_map[tag]["id"])
                except:
                    logger.debug("failed to find tag {} in lookup map".format(tag))
            if not vlan_id is None:
                try:
                    vlan = self.vlan_map["{}_{}".format(vlan_domain_id, vlan_id)]["id"]
                    subs.update({"vlan": vlan})
                except:
                    logger.debug("failed to find vlan for subnet {}".format(subnet))
            else:
                subs.update({"vlan": None})
            subs.update({"prefix": "/".join([subnet, str(mask)])})
            ip_calc_net = ipcalc.Network(subs["prefix"])
            ip_calc_net2 = ipcalc.Network(str(ip_calc_net.network()) + "/" + str(ip_calc_net.subnet()))
            cleaned_prefix = str(ip_calc_net2.to_compressed()) + "/" + str(ip_calc_net2.subnet())
            subs.update({"prefix": cleaned_prefix})
            subs.update({"status": "active"})
            # subs.update({'mask_bits': str(mask)})
            subs.update({"description": name})
            subs.update({"tags": tags})
            netbox.post_subnet(subs)

    def get_tags_for_obj(self, tag_type, object_id):
        subs = {}
        if not self.con:
            self.connect()
        with self.con:
            cur = self.con.cursor()
            q = """SELECT tag FROM TagStorage
                LEFT JOIN TagTree ON TagStorage.tag_id = TagTree.id
                WHERE entity_realm = "{}" AND entity_id = "{}" """.format(
                tag_type, object_id
            )
            cur.execute(q)

            resp = cur.fetchall()
            if config["Log"]["DEBUG"]:
                msg = ("tags", str(resp))
                logger.debug(msg)
            cur.close()
            self.con = None
        tags = []
        for tag in resp:
            tags.append(tag[0])
        if not self.tag_map:
            self.create_tag_map()
        return tags

    def get_attribs_for_obj(self, object_id, remove_links=False):
        attribs = {}
        if not self.con:
            self.connect()
        with self.con:
            cur = self.con.cursor()
            q = f"""SELECT
                    Attribute.name as attrib_key,                   
                    Attribute.type as _attrib_type,
                    AttributeValue.string_value as string_val, 
                    AttributeValue.uint_value as uint_val, 
                    AttributeValue.float_value as float_val, 
                    Dictionary.dict_value as dict_val
                    FROM AttributeValue
                    LEFT JOIN Attribute ON AttributeValue.attr_id = Attribute.id
                    LEFT JOIN Dictionary ON Dictionary.dict_key = AttributeValue.uint_value
                    WHERE AttributeValue.object_id = {object_id}"""
            cur.execute(q)

            resp = cur.fetchall()
            if config["Log"]["DEBUG"]:
                msg = "attribs_db_resp: " + str(resp)
                logger.debug(msg)
            cur.close()
            self.con = None

        for attrib_data in resp:
            if attrib_data[1] == "uint":
                attrib_val = attrib_data[3]
            elif attrib_data[1] == "dict":
                attrib_val = attrib_data[5]
            elif attrib_data[1] == "string":
                attrib_val = attrib_data[2]
            elif attrib_data[1] == "date":
                attrib_val = attrib_data[3]
            elif attrib_data[1] == "float":
                attrib_val = attrib_data[4]
            attrib_name = self.custom_field_name_slugger(attrib_data[0])
            if attrib_data[1] == "date":
                datetime_time = datetime.datetime.fromtimestamp(int(attrib_val))
                attribs[attrib_name] = datetime_time.strftime("%Y-%m-%d")
            else:
                if remove_links:
                    attrib_val = self.remove_links(attrib_val)
                attribs[attrib_name] = str(attrib_val)
        return attribs

    def get_tags(self):
        tags = []

        if not self.con:
            self.connect()
        with self.con:
            cur = self.con.cursor()
            q = 'SELECT tag,description FROM TagTree where is_assignable = "yes";'
            cur.execute(q)
            tags = cur.fetchall()
            if config["Log"]["DEBUG"]:
                msg = ("tags", str(tags))
                logger.debug(msg)
            cur.close()
            self.con = None

        for line in tags:
            tag, description = line
            netbox.post_tag(tag, description)

    def get_custom_attribs(self):
        attributes = []

        if not self.con:
            self.connect()
        with self.con:
            cur = self.con.cursor()
            q = "SELECT type,name FROM Attribute;"
            cur.execute(q)
            tags = cur.fetchall()
            if config["Log"]["DEBUG"]:
                msg = ("attributes", str(tags))
                logger.debug(msg)
            cur.close()
            self.con = None

        for line in tags:
            attrib_type, attrib_name = line
            attributes.append({"name": attrib_name, "type": attrib_type})
        attributes.append({"name": "rt_id", "type": "text", "filter_logic": "exact"})  # custom field for racktables source objid
        attributes.append({"name": "rt_id_parent", "type": "text", "filter_logic": "exact"})  # used for child devices (vms) to link to parent (server)
        attributes.append({"name": "Visible label", "type": "text"})
        attributes.append({"name": "SW type", "type": "text"})
        attributes.append({"name": "Operating System", "type": "text"})
        attributes.append({"name": "External URLs", "type": "longtext"})

        netbox.createCustomFields(attributes)

    def get_vlan_domains(self):
        if not self.con:
            self.connect()
        with self.con:
            cur = self.con.cursor()
            q = "SELECT * FROM VLANDomain;"
            cur.execute(q)
            resp = cur.fetchall()
            if config["Log"]["DEBUG"]:
                msg = ("vlan_domains", str(resp))
                logger.debug(msg)
            cur.close()
            self.con = None

        for line in resp:
            id, group_id, description = line
            print(description)
            netbox.post_vlan_group(description, group_id)

    def create_vlan_domains_nb_group_map(self):
        nb_groups = netbox.get_vlan_groups_by_name()
        pp.pprint(nb_groups)
        # self.vlan_group_map
        groups_by_rt_id = {}
        if not self.con:
            self.connect()
        with self.con:
            cur = self.con.cursor()
            q = "SELECT * FROM VLANDomain;"
            cur.execute(q)
            resp = cur.fetchall()
            if config["Log"]["DEBUG"]:
                msg = ("vlan_domains", str(resp))
                logger.debug(msg)
            cur.close()
            self.con = None

        for line in resp:
            id, group_id, description = line
            print(line)
            lookup_name = copy.deepcopy(description)
            description = re.sub(r"\W+", "", description)
            groups_obj = nb_groups[lookup_name]
            groups_by_rt_id[id] = groups_obj
        self.vlan_group_map = groups_by_rt_id

    def create_vlan_nb_map(self):
        if not self.vlan_group_map:
            self.create_vlan_domains_nb_group_map()
        rt_vlans = self.get_vlans_data()
        nb_vlans = netbox.get_nb_vlans()

        # pp.pprint(rt_vlans)
        rt_vlan_table = {}
        for line in rt_vlans:
            vlan_domain_id, vlan_id, vlan_type, vlan_descr = line
            vlan_domain_data = self.vlan_group_map[vlan_domain_id]

            found = False
            for nb_vlan_id, nb_vlan_data in nb_vlans.items():
                if nb_vlan_data["vid"] == vlan_id:
                    if nb_vlan_data["group"]["name"] == vlan_domain_data["name"]:
                        logger.debug(nb_vlan_data)
                        found = True
                        key = "{}_{}".format(vlan_domain_id, vlan_id)
                        rt_vlan_table[key] = nb_vlan_data
            if not found:
                logger.debug("unable to find a vlan. dying")
                logger.debug(line)
                exit(1)
        self.vlan_map = rt_vlan_table

    def get_vlans(self):
        resp = self.get_vlans_data()

        for line in resp:
            vlan_domain_id, vlan_id, vlan_type, vlan_descr = line
            vlan = {}
            vlan["group"] = self.vlan_group_map[vlan_domain_id]["id"]
            vlan["name"] = vlan_descr[: min(len(vlan_descr), 64)]  # limit char lenght
            vlan["vid"] = vlan_id
            vlan["description"] = vlan_descr
            logger.debug("adding vlan {}".format(vlan))
            netbox.post_vlan(vlan)

    def get_vlans_data(self):
        if not self.vlan_group_map:
            self.create_vlan_domains_nb_group_map()
        if not self.con:
            self.connect()
        with self.con:
            cur = self.con.cursor()
            q = "SELECT * FROM VLANDescription order by domain_id desc;"
            cur.execute(q)
            resp = cur.fetchall()
            if config["Log"]["DEBUG"]:
                msg = ("vlans", str(resp))
                logger.debug(msg)
            cur.close()
            self.con = None
        return resp

    def get_infrastructure(self, do_updates=True):
        """
        Get locations, rows and racks from RT, convert them to buildings and rooms and send to uploader.
        :return:
        """
        sites_map = {}
        rooms_map = {}
        rows_map = {}
        rackgroups = []
        racks = []

        if not self.con:
            self.connect()

        # ============ BUILDINGS ============
        with self.con:
            cur = self.con.cursor()
            q = """SELECT id, name, parent_id, parent_name FROM Location"""
            cur.execute(q)
            raw = cur.fetchall()

            for rec in raw:
                location_id, location_name, parent_id, parent_name = rec
                sites_map.update({location_id: location_name})
            cur.close()
            self.con = None
        print("Sites:")
        pp.pprint(sites_map)
        sites_map[0] = "Unknown"
        netbox.manage_sites(sites_map)

        # ============ ROWS AND RACKS ============
        netbox_sites_by_comment = netbox.get_sites_keyd_by_description()
        pp.pprint(netbox_sites_by_comment)
        if not self.con:
            self.connect()
        with self.con:
            cur = self.con.cursor()
            q = """SELECT id, name ,height, row_id, row_name, location_id, location_name,asset_no,comment  from Rack;"""
            cur.execute(q)
            raw = cur.fetchall()
            cur.close()
            self.con = None

        for rec in raw:
            rack_id, rack_name, height, row_id, row_name, location_id, location_name, asset_no, comment = rec

            rows_map.update({row_id: {"site_name": location_name, "site_id": location_id, "row_name": row_name, "row_id": row_id}})

            # prepare rack data. We will upload it a little bit later
            rack = {}
            rack["custom_fields"] = {}
            rack.update({"name": rack_name})
            rack.update({"size": height})
            rack.update({"rt_id": rack_id})  # we will remove this later
            rack["asset_tag"] = asset_no
            if comment:
                rack["comments"] = "\n\n" + comment.replace("\n", "\n\n")
            else:
                rack["comments"] = ""
            rack.update({"room": row_name})
            rack.update({"building": location_name})
            rack.update({"row_rt_id": str(row_id)})

            racks.append(rack)
        pprint.pprint(racks)

        # upload rows as rooms
        if config["Log"]["DEBUG"] == True:
            msg = ("Rooms", str(rows_map))
            logger.debug(msg)
        # print("roomdata:")
        netbox.manage_rooms(rows_map)
        rooms_by_rt_id = netbox.get_rooms_by_rt_id()

        # upload racks
        if config["Log"]["DEBUG"]:
            msg = ("Racks", str(racks))
            # logger.debug(msg)
        for rack in racks:
            netbox_rack = {}
            netbox_rack["name"] = rack["name"]
            logger.debug("attempting to get site {} from netbox dict".format(rack["building"]))
            netbox_rack["site"] = netbox_sites_by_comment[rack["building"]]["id"]
            netbox_rack["comments"] = rack["room"] + rack["comments"]
            netbox_rack["custom_fields"] = {}
            netbox_rack["custom_fields"]["rt_id"] = str(rack["rt_id"])
            if rack["asset_tag"]:
                netbox_rack["asset_tag"] = rack["asset_tag"]
            rt_tags = self.get_tags_for_obj("rack", rack["rt_id"])
            # print(rt_tags)
            tags = []
            # print (self.tag_map)
            for tag in rt_tags:
                try:
                    # print(tag)
                    tags.append(self.tag_map[tag]["id"])
                except:
                    logger.debug("failed to find tag {} in lookup map".format(tag))
            netbox_rack["tags"] = tags
            if rack["size"] == None:
                netbox_rack["u_height"] = 100
            else:
                netbox_rack["u_height"] = rack["size"]
            if rack["row_rt_id"] in rooms_by_rt_id.keys():
                netbox_rack["location"] = rooms_by_rt_id[rack["row_rt_id"]]["id"]
            logger.debug(netbox_rack)
            netbox.post_rack(netbox_rack)
            # response = netbox.post_rack(rack)

        #     self.rack_id_map.update({rt_rack_id: d42_rack_id})

        # self.all_ports = self.get_ports()

    def get_hardware(self):
        """
        Get hardware from RT
        :return:
        """
        if not self.con:
            self.connect()
        with self.con:
            # get hardware items (except PDU's)
            cur = self.con.cursor()
            q = (
                """SELECT
                    Object.id,Object.name as Description,
                    Object.label as Name,
                    Object.asset_no as Asset,
                    Dictionary.dict_value as Type,
                    Chapter.name
                    FROM Object
                    LEFT JOIN AttributeValue ON Object.id = AttributeValue.object_id
                    LEFT JOIN Attribute ON AttributeValue.attr_id = Attribute.id
                    LEFT JOIN Dictionary ON Dictionary.dict_key = AttributeValue.uint_value
                    LEFT JOIN Chapter on Dictionary.chapter_id = Chapter.id
                    WHERE 
                        Attribute.id=2 
                        AND Object.objtype_id != 2
                        """
                + config["Misc"]["hardware_data_filter"]
            )
            logger.debug(q)
            cur.execute(q)
        data = cur.fetchall()
        cur.close()
        self.con = None

        if config["Log"]["DEBUG"]:
            msg = ("Hardware", str(data))
            logger.debug(msg)

        # create map device_id:height
        # RT does not impose height for devices of the same hardware model so it might happen that -
        # two or more devices based on same HW model have different size in rack
        # here we try to find and set smallest U for device
        hwsize_map = {}
        logger.debug("about to get hardware sizes for existing services. this may take some time")
        for line in data:
            line = [0 if not x else x for x in line]
            data_id, description, name, asset, dtype, device_section = line
            size = self.get_hardware_size(data_id)
            if size:
                floor, height, depth, mount = size
                if data_id not in hwsize_map:
                    hwsize_map.update({data_id: height})
                else:
                    h = float(hwsize_map[data_id])
                    if float(height) < h:
                        hwsize_map.update({data_id: height})

        logger.debug(hwsize_map)
        hardware = {}
        for line in data:
            hwddata = {}
            line = [0 if not x else x for x in line]
            data_id, description, name, asset, dtype, device_section = line

            if "%GPASS%" in dtype:
                vendor, model = dtype.split("%GPASS%")
            elif len(dtype.split()) > 1:
                venmod = dtype.split()
                vendor = venmod[0]
                model = " ".join(venmod[1:])
            else:
                vendor = dtype
                model = dtype
            if "[[" in vendor:
                vendor = vendor.replace("[[", "").strip()
                name = model[:48].split("|")[0].strip()
            else:
                name = model[:48].strip()
            device_section = device_section.strip()
            if "models" in device_section:
                device_section = device_section.replace("models", "").strip()

            size = self.get_hardware_size(data_id)
            if size:
                floor, height, depth, mount = size
                # patching height
                height = hwsize_map[data_id]
                hwddata.update({"description": description})
                hwddata.update({"type": 1})
                hwddata.update({"size": height})
                hwddata.update({"depth": depth})
                hwddata.update({"name": str(name)})
                hwddata.update({"manufacturer": str(vendor)})
                hwddata.update({"rt_device_section": device_section})
                hwddata.update({"rt_dev_id": data_id})
                hardware[data_id] = hwddata
        return hardware

    def get_hardware_size(self, data_id):
        """
        Calculate hardware size.
        :param data_id: hw id
        :return:
            floor   - starting U location for the device in the rack
            height  - height of the device
            depth   - depth of the device (full, half)
            mount   - orientation of the device in the rack. Can be front or back
        """
        if not self.con:
            self.connect()
        with self.con:
            # get hardware items
            cur = self.con.cursor()
            q = """SELECT unit_no,atom FROM RackSpace WHERE object_id = %s""" % data_id
            cur.execute(q)
        data = cur.fetchall()
        cur.close()
        self.con = None
        if data != ():
            front = 0
            interior = 0
            rear = 0
            floor = 0
            depth = 1  # 1 for full depth (default) and 2 for half depth
            mount = "front"  # can be [front | rear]
            i = 1

            for line in data:
                flr, tag = line

                floor = int(flr)

                i += 1
                if tag == "front":
                    front += 1
                elif tag == "interior":
                    interior += 1
                elif tag == "rear":
                    rear += 1

            if front and interior and rear:  # full depth
                height = front
                if height > 1:
                    floor = floor - (height - 1)
                return floor, height, depth, mount

            elif front and interior and not rear:  # half depth, front mounted
                height = front
                depth = 2
                if height > 1:
                    floor = floor - (height - 1)
                return floor, height, depth, mount

            elif interior and rear and not front:  # half depth,  rear mounted
                height = rear
                depth = 2
                mount = "rear"
                if height > 1:
                    floor = floor - (height - 1)
                return floor, height, depth, mount

            # for devices that look like less than half depth:
            elif front and not interior and not rear:
                height = front
                depth = 2
                if height > 1:
                    floor = floor - (height - 1)
                return floor, height, depth, mount
            elif rear and not interior and not front:
                height = rear
                depth = 2
                mount = "rear"
                if height > 1:
                    floor = floor - (height - 1)
                return floor, height, depth, mount
            elif interior and not rear and not front:
                logger.warn("interior only mounted device. this is not nb compatible")
                return None, None, None, None
            else:
                return None, None, None, None
        else:
            return None, None, None, None

    def remove_links(self, item):
        if "[[" in item and "|" in item:
            item = item.replace("[[", "").strip()
            item = item.split("|")[0].strip()
        return item

    def get_device_types(self):
        if not self.hardware:
            self.hardware = self.get_hardware()
        rt_hardware = self.hardware
        rt_device_types = {}

        for device_id, device in rt_hardware.items():
            logger.debug(device)
            if device["name"] == device["manufacturer"]:
                key = device["name"]
            else:
                key = "{} {}".format(device["manufacturer"], device["name"])
            if not key in rt_device_types.keys():
                device_type = copy.deepcopy(device)
                if "description" in device_type.keys():
                    del device_type["description"]
                    del device_type["rt_dev_id"]
                rt_device_types[key] = device_type
        device_templates = self.match_device_types_to_netbox_templates(rt_device_types)
        # pp.pprint(device_templates)
        for device_type in device_templates["matched"].keys():
            # print(device_type)
            netbox.post_device_type(device_type, device_templates["matched"][device_type])

    def match_device_types_to_netbox_templates(self, device_types):
        unmatched = {}
        matched = {}

        for device_type_key in device_types.keys():
            if device_type_key in device_type_map_preseed["by_key_name"].keys():
                # print("found device type for {}".format(device_type_key))
                matched[device_type_key] = device_types[device_type_key]
                matched[device_type_key]["device_template_data"] = device_type_map_preseed["by_key_name"][device_type_key]
            else:
                # print("did not find device type {} in hardware_map.yaml".format(device_type_key))
                unmatched[device_type_key] = device_types[device_type_key]
        logger.debug("device templates found for importing: ")
        pp.pprint(matched)

        logger.debug("the following device types have no matching device templates:")
        for unmatched_device_type in sorted(unmatched.keys()):
            logger.debug(unmatched_device_type)
        if not config["Misc"]["SKIP_DEVICES_WITHOUT_TEMPLATE"] == True:
            if len(unmatched) > 0:
                logger.debug("")
                logger.debug(
                    "please update hardware_map.yml with device maps or set SKIP_DEVICES_WITHOUT_TEMPLATE to True in conf file to skip devices without a matching template"
                )
                exit(22)
        return {"matched": matched, "unmatched": unmatched}

    @staticmethod
    def add_hardware(height, depth, name):
        """

        :rtype : object
        """
        hwddata = {}
        hwddata.update({"type": 1})
        if height:
            hwddata.update({"size": height})
        if depth:
            hwddata.update({"depth": depth})
        if name:
            hwddata.update({"name": name[:48]})
        logger.debug(hwddata)
        # netbox.post_hardware(hwddata)

    def get_vmhosts(self):
        if not self.con:
            self.connect()
        with self.con:
            cur = self.con.cursor()
            q = """SELECT id, name FROM Object WHERE objtype_id='1505'"""
            cur.execute(q)
            raw = cur.fetchall()
        cur.close()
        self.con = None
        dev = {}
        for rec in raw:
            host_id = int(rec[0])
            try:
                name = rec[1].strip()
            except AttributeError:
                continue
            self.vm_hosts.update({host_id: name})
            dev.update({"name": name})
            dev.update({"is_it_virtual_host": "yes"})

    def get_chassis(self):
        if not self.con:
            self.connect()
        with self.con:
            cur = self.con.cursor()
            q = """SELECT id, name FROM Object WHERE objtype_id='1502'"""
            cur.execute(q)
            raw = cur.fetchall()
        cur.close()
        self.con = None
        dev = {}
        for rec in raw:
            host_id = int(rec[0])
            try:
                name = rec[1].strip()
            except AttributeError:
                continue
            self.chassis.update({host_id: name})
            dev.update({"name": name})
            dev.update({"is_it_blade_host": "yes"})

    def get_container_map(self):
        """
        Which VM goes into which VM host?
        Which Blade goes into which Chassis ?
        :return:
        """
        if not self.con:
            self.connect()
        with self.con:
            cur = self.con.cursor()
            q = """SELECT parent_entity_id AS container_id, child_entity_id AS object_id
                    FROM EntityLink WHERE child_entity_type='object' AND parent_entity_type = 'object'"""
            cur.execute(q)
            raw = cur.fetchall()
        cur.close()
        self.con = None
        for rec in raw:
            container_id, object_id = rec
            self.container_map.update({object_id: container_id})

    def get_devices(self):

        self.get_vmhosts()
        self.get_chassis()
        if not self.tag_map:
            self.create_tag_map()
        if not self.all_ports:
            self.get_ports()
        if not netbox.device_types:
            netbox.device_types = {str(item.slug): dict(item) for item in py_netbox.dcim.device_types.all()}

        if not config["Misc"]["DEFAULT_DEVICE_ROLE_ID"]:
            roles = {str(item.name): dict(item) for item in py_netbox.dcim.device_roles.all()}
            pp.pprint(roles)
            if not "rt_import" in roles.keys():
                create_role = {
                    "name": "rt_import",
                    "slug": "rt_import",
                }
                py_netbox.dcim.device_roles.create(create_role)
            roles = {str(item.name): dict(item) for item in py_netbox.dcim.device_roles.all()}
            config["Misc"]["DEFAULT_DEVICE_ROLE_ID"] = roles["rt_import"]["id"]

        else:
            # check to see if device_role_id exists in nb. if not. blow up
            roles = {str(item.id): dict(item) for item in py_netbox.dcim.device_roles.all()}
            if not str(config["Misc"]["DEFAULT_DEVICE_ROLE_ID"]) in roles:
                logger.error(f"No device-role found in netbox with id: {config['Misc']['DEFAULT_DEVICE_ROLE_ID']}")
                exit(5)

        if not self.con:
            self.connect()
        with self.con:
            cur = self.con.cursor()
            # get object IDs
            q = f"SELECT id FROM Object WHERE "
            # q = q + "Object.id = 7461 and "
            q = q + f"""{config["Misc"]["device_data_filter_obj_only"]} """
            cur.execute(q)
            idsx = cur.fetchall()
        ids = [x[0] for x in idsx]
        cur.close()
        self.con = None

        for dev_id in ids:
            # try:
            if not self.con:
                self.connect()
                cur = self.con.cursor()
            q = f"""Select
                        Object.id,
                        Object.objtype_id,
                        Object.name as Description,
                        Object.label as Name,
                        Object.asset_no as Asset,
                        Attribute.name as Name,
                        Dictionary.dict_value as Type,
                        Object.comment as Comment,
                        RackSpace.rack_id as RackID,
                        Rack.name as rack_name,
                        Rack.row_name,
                        Rack.location_id,
                        Rack.location_name,
                        Location.parent_name,
                        COALESCE(AttributeValue.string_value,AttributeValue.uint_value,AttributeValue.float_value,'') as attrib_value,
                        Attribute.type,
                        Object.has_problems,
                        Dictionary2.dict_value as object_class_type

                        FROM Object
                        left join Dictionary as Dictionary2 on Dictionary2.dict_key = Object.objtype_id
                        LEFT JOIN AttributeValue ON Object.id = AttributeValue.object_id
                        LEFT JOIN Attribute ON AttributeValue.attr_id = Attribute.id
                        LEFT JOIN RackSpace ON Object.id = RackSpace.object_id
                        LEFT JOIN Dictionary ON Dictionary.dict_key = AttributeValue.uint_value
                        LEFT JOIN Rack ON RackSpace.rack_id = Rack.id
                        LEFT JOIN Location ON Rack.location_id = Location.id
                        LEFT JOIN Chapter on Dictionary.chapter_id = Chapter.id
                        WHERE Object.id = {dev_id}
                        AND Object.objtype_id not in (2,9,1504,1505,1506,1507,1560,1561,1562,50275) 
                        {config["Misc"]["device_data_filter"]} """
            logger.debug(q)

            cur.execute(q)
            data = cur.fetchall()
            # print(json.dumps(data))
            cur.close()
            self.con = None
            if data:  # RT objects that do not have data are locations, racks, rows etc...
                self.process_data(data, dev_id)
            # except:
            #     sleep(2)
            #     if not self.con:
            #         self.connect()
            #         cur = self.con.cursor()
            #     q = f"""Select
            #                 Object.id,
            #                 Object.objtype_id,
            #                 Object.name as Description,
            #                 Object.label as Name,
            #                 Object.asset_no as Asset,
            #                 Attribute.name as Name,
            #                 Dictionary.dict_value as Type,
            #                 Object.comment as Comment,
            #                 RackSpace.rack_id as RackID,
            #                 Rack.name as rack_name,
            #                 Rack.row_name,
            #                 Rack.location_id,
            #                 Rack.location_name,
            #                 Location.parent_name,
            #                 COALESCE(AttributeValue.string_value,AttributeValue.uint_value,AttributeValue.float_value,'') as attrib_value,
            #                 Attribute.type

            #                 FROM Object
            #                 left join Dictionary as Dictionary2 on Dictionary2.dict_key = Object.objtype_id
            #                 LEFT JOIN AttributeValue ON Object.id = AttributeValue.object_id
            #                 LEFT JOIN Attribute ON AttributeValue.attr_id = Attribute.id
            #                 LEFT JOIN RackSpace ON Object.id = RackSpace.object_id
            #                 LEFT JOIN Dictionary ON Dictionary.dict_key = AttributeValue.uint_value
            #                 LEFT JOIN Rack ON RackSpace.rack_id = Rack.id
            #                 LEFT JOIN Location ON Rack.location_id = Location.id
            #                 LEFT JOIN Chapter on Dictionary.chapter_id = Chapter.id
            #                 WHERE Object.id = {dev_id}
            #                 AND Object.objtype_id not in (2,9,1504,1505,1506,1507,1560,1561,1562,50275)
            #                 {config["Misc"]["device_data_filter"]} """
            #     logger.debug(q)

            #     cur.execute(q)
            #     data = cur.fetchall()
            #     # print(json.dumps(data))
            #     cur.close()
            #     self.con = None
            #     if data:  # RT objects that do not have data are locations, racks, rows etc...
            #         self.process_data(data, dev_id)
        logger.debug("skipped devices:")
        pp.pprint(self.skipped_devices)

    def get_obj_location(self, obj_id):
        # position check:
        position, height, depth, mount = self.get_hardware_size(obj_id)

        if position:  # u position exists. can find rack id in rackspace table
            if not self.con:
                self.connect()

            cur = self.con.cursor()
            # get object IDs
            q = f"""
                SELECT rack_id,Rack.location_name, Rack.name FROM RackSpace left join Rack on RackSpace.rack_id = Rack.id where object_id = {obj_id}
            """
            cur.execute(q)
            idsx = cur.fetchall()
            cur.close()
            self.con = None
            pp.pprint(idsx)
            rack_id = idsx[0][0]
            location_name = idsx[0][1]
            rack_name = idsx[0][2]
            output_data = {
                "rack_mounted": True,
                "rack_id": rack_id,
                "rack_name": rack_name,
                "location": location_name,
                "position_data": {
                    "u": position,
                    "height": height,
                    "depth": depth,
                    "face": mount,
                },
            }

        else:
            data = self.get_0u_obj_location(obj_id)
            output_data = {
                "rack_mounted": False,
                "rack_id": data[0],
                "rack_name": data[1],
                "location": data[5],
            }

        return output_data

    def get_0u_obj_location(self, obj_id):
        if not self.con:
            self.connect()

        cur = self.con.cursor()
        # get object IDs
        q = f"""
            SELECT Rack.id,Rack.name,Rack.row_id,Rack.row_name,Rack.location_id,Rack.location_name 
            FROM EntityLink 
            left join Rack on EntityLink.parent_entity_id = Rack.id 
            WHERE parent_entity_type = 'rack' 
            AND child_entity_type = 'object' 
            AND child_entity_id = {obj_id}
        """
        cur.execute(q)
        idsx = cur.fetchall()
        try:
            resp = [x for x in idsx][0]
        except:
            resp = [None, None, None, None, None, "Unknown"]

        cur.close()
        self.con = None
        return resp

    def process_data(self, data, dev_id):
        devicedata = {}
        devicedata["custom_fields"] = {}
        device2rack = {}
        name = None
        opsys = None
        hardware = None
        note = None
        rrack_id = None
        floor = None
        dev_type = 0
        process_object = True
        bad_tag = False

        if process_object:
            for x in data:
                (
                    rt_object_id,
                    dev_type,
                    rdesc,
                    rname,
                    rasset,
                    rattr_name,
                    dict_dictvalue,
                    rcomment,
                    rrack_id,
                    rrack_name,
                    rrow_name,
                    rlocation_id,
                    rlocation_name,
                    rparent_name,
                    attrib_value,
                    attrib_type,
                    has_problems,
                    object_class_type,
                ) = x
                logger.debug(x)
                if rdesc is None:
                    rdesc = f"No Name rt_id {rt_object_id}"
                name = self.remove_links(rdesc)
                if rcomment:
                    try:
                        note = rname + "\n" + rcomment
                    except:
                        note = rcomment
                else:
                    note = rname

                if "Operating System" in x:
                    opsys = dict_dictvalue
                    opsys = self.remove_links(opsys)
                    if "%GSKIP%" in opsys:
                        opsys = opsys.replace("%GSKIP%", " ")
                    if "%GPASS%" in opsys:
                        opsys = opsys.replace("%GPASS%", " ")
                    devicedata["custom_fields"][self.custom_field_name_slugger("Operating System")] = str(opsys)
                elif "SW type" in x:
                    opsys = dict_dictvalue
                    opsys = self.remove_links(opsys)
                    if "%GSKIP%" in opsys:
                        opsys = opsys.replace("%GSKIP%", " ")
                    if "%GPASS%" in opsys:
                        opsys = opsys.replace("%GPASS%", " ")
                    devicedata["custom_fields"][self.custom_field_name_slugger("SW type")] = str(opsys)

                elif "Server Hardware" in x:
                    hardware = dict_dictvalue
                    hardware = self.remove_links(hardware)
                    if "%GSKIP%" in hardware:
                        hardware = hardware.replace("%GSKIP%", " ")
                    if "%GPASS%" in hardware:
                        hardware = hardware.replace("%GPASS%", " ")
                    if "\t" in hardware:
                        hardware = hardware.replace("\t", " ")

                elif "HW type" in x:
                    hardware = dict_dictvalue
                    hardware = self.remove_links(hardware)
                    if "%GSKIP%" in hardware:
                        hardware = hardware.replace("%GSKIP%", " ")
                    if "%GPASS%" in hardware:
                        hardware = hardware.replace("%GPASS%", " ")
                    if "\t" in hardware:
                        hardware = hardware.replace("\t", " ")
                elif "BiosRev" in x:
                    biosrev = self.remove_links(dict_dictvalue)
                    devicedata["custom_fields"][self.custom_field_name_slugger("BiosRev")] = biosrev
                else:
                    if not rattr_name == None:
                        if attrib_type == "dict":
                            attrib_value_unclean = dict_dictvalue
                        else:
                            attrib_value_unclean = attrib_value
                        cleaned_val = netbox.cleanup_attrib_value(attrib_value_unclean, attrib_type)
                        # print(cleaned_val)
                        devicedata["custom_fields"][self.custom_field_name_slugger(rattr_name)] = cleaned_val
                        config_cust_field_map = config["Misc"]["CUSTOM_FIELD_MAPPER"]
                        if rattr_name in config_cust_field_map.keys():
                            devicedata[self.custom_field_name_slugger(config_cust_field_map[rattr_name])] = cleaned_val
                if rasset:
                    devicedata["asset_tag"] = rasset
                devicedata["custom_fields"]["rt_id"] = str(rt_object_id)
                devicedata["custom_fields"][self.custom_field_name_slugger("Visible label")] = str(rname)

                if note:
                    note = note.replace("\n", "\n\n")  # markdown. all new lines need two new lines

            if has_problems == "yes":
                has_problems = True
            else:
                has_problems = False

            if hardware:
                if note:
                    note = "hardware: " + hardware + "\n\n" + note
                else:
                    note = "hardware: " + hardware

            if not "tags" in devicedata.keys():
                rt_tags = self.get_tags_for_obj("object", int(devicedata["custom_fields"]["rt_id"]))
                tags = []
                # print (self.tag_map)

                for tag in rt_tags:
                    try:
                        # print(tag)
                        tags.append(self.tag_map[tag]["id"])
                    except:
                        logger.debug("failed to find tag {} in lookup map".format(tag))
                devicedata["tags"] = tags

            bad_tags = []
            for tag_check in config["Misc"]["SKIP_OBJECTS_WITH_TAGS"].strip().split(","):
                logger.debug(f"checking for tag '{tag_check}'")
                if self.tag_map[tag_check]["id"] in devicedata["tags"]:
                    logger.debug(f"tag matched by id")
                    bad_tag = True
                    bad_tags.append(tag_check)
            if bad_tag:
                process_object = False
                name = None
                logger.info(f"skipping object rt_id:{rt_object_id} as it has tags: {str(bad_tags)}")
                netbox.remove_device_by_rt_id(str(rt_object_id))

            # 0u device logic
            zero_location_obj_data = None
            if rlocation_name == None and process_object:
                zero_location_obj_data = self.get_0u_obj_location(rt_object_id)
                rlocation_name = zero_location_obj_data[5]
                rrack_id = zero_location_obj_data[0]
                rrack_name = zero_location_obj_data[1]
                print(zero_location_obj_data)
                print(f"obj location (probably 0u device): {rlocation_name}")
                print(f"rackid: {rrack_id}, rackname: {rrack_name}")

            if name:
                # set device data
                devicedata.update({"name": name})
                if hardware:
                    devicedata.update({"hardware": hardware[:48]})
                if opsys:
                    devicedata.update({"os": opsys})
                if note:
                    devicedata.update({"comments": note})
                if dev_id in self.vm_hosts:
                    devicedata.update({"is_it_virtual_host": "yes"})
                if dev_type == 8:
                    devicedata.update({"is_it_switch": "yes"})
                elif dev_type == 1502:
                    devicedata.update({"is_it_blade_host": "yes"})
                elif dev_type == 4:
                    try:
                        blade_host_id = self.container_map[dev_id]
                        blade_host_name = self.chassis[blade_host_id]
                        devicedata.update({"type": "blade"})
                        devicedata.update({"blade_host": blade_host_name})
                    except KeyError:
                        # print("ERROR: failed to track down blade info")
                        pass
                elif dev_type == 1504:
                    devicedata.update({"type": "virtual"})
                    devicedata.pop("hardware", None)
                    try:
                        vm_host_id = self.container_map[dev_id]
                        vm_host_name = self.vm_hosts[vm_host_id]
                        devicedata.update({"virtual_host": vm_host_name})
                    except KeyError:
                        logger.debug("ERROR: failed to track down virtual host info")
                        pass

                d42_rack_id = None

                if rrack_id:
                    print(f"rack name: {rrack_name}")
                    rack_detail = dict(py_netbox.dcim.racks.get(name=rrack_name))
                    rack_id = rack_detail["id"]
                    pp.pprint(rack_detail)
                    devicedata.update({"rack": rack_id})
                    devicedata.update({"site": rack_detail["site"]["id"]})
                    if rack_detail["location"]["id"]:
                        devicedata.update({"location": rack_detail["location"]["id"]})
                    d42_rack_id = rack_id

                    # if the device is mounted in RT, we will try to add it to D42 hardwares.
                    position, height, depth, mount = self.get_hardware_size(dev_id)
                    devicedata.update({"position": position})
                    devicedata.update({"face": mount})
                    # 0u device logic
                    if height == None and not zero_location_obj_data == None:
                        height = 0
                        depth = 0
                else:
                    height = 0
                    depth = 0
                    devicedata.update({"rack": None})
                    devicedata.update({"location": None})
                    devicedata.update({"face": None})
                    devicedata.update({"position": None})

                if not "site" in devicedata.keys():
                    netbox_sites_by_comment = netbox.get_sites_keyd_by_description()
                    devicedata["site"] = netbox_sites_by_comment[rlocation_name]["id"]

                devicedata["device_role"] = self.nb_role_id(object_class_type)

                if not "hardware" in devicedata.keys():
                    if height == None:
                        height = 0
                    generic_depth = ""

                    if depth:
                        print("depth:")
                        print(depth)
                        if depth == 2:
                            generic_depth = "short_"
                    devicedata["hardware"] = f"generic_{height}u_{generic_depth}device"
                logger.debug(devicedata["hardware"])
                devicedata["device_type"] = netbox.device_type_checker(devicedata["hardware"])
                if devicedata["device_type"] == None:
                    if not devicedata["hardware"] in self.skipped_devices.keys():
                        self.skipped_devices[devicedata["hardware"]] = 1
                    else:
                        self.skipped_devices[devicedata["hardware"]] = self.skipped_devices[devicedata["hardware"]] + 1
                    process_object = False
                # upload device
                if devicedata and process_object:
                    if hardware and dev_type != 1504:
                        devicedata.update({"hardware": hardware[:48]})

                    # set default type for racked devices
                    if "type" not in devicedata and d42_rack_id and floor:
                        devicedata.update({"type": "physical"})

                    logger.debug(json.dumps(devicedata))
                    netbox.post_device(devicedata, py_netbox, has_problems)

                    # update ports
                    if process_object:
                        # pp.pprint("got here")
                        # print("")
                        ports = self.get_ports_by_device(self.all_ports, dev_id)
                        print("ports:")
                        pp.pprint(ports)

                        ip_ints = self.get_devices_ips_ints(dev_id)
                        print("ip_ints: ")
                        pp.pprint(ip_ints)
                        netbox.create_device_interfaces(dev_id, ports, ip_ints)
                        # ports = False
                        if ports:
                            for item in ports:
                                switchport_data = {
                                    "local_port": item[0],
                                    "local_device": name,
                                    "local_device_rt_id": dev_id,
                                    "local_label": item[1],
                                }

                                get_links = self.get_links(item[3])
                                pp.pprint("here get_links")
                                pp.pprint(get_links)

                                if get_links:
                                    remote_device_name = self.get_device_by_port(get_links[0])
                                    switchport_data.update({"remote_device": remote_device_name})
                                    switchport_data.update({"remote_port": self.get_port_by_id(self.all_ports, get_links[0])})
                                    pp.pprint(switchport_data)

                                    netbox.create_cables_between_devices(switchport_data)

                else:
                    msg = (
                        "\n-----------------------------------------------------------------------\
                    \n[!] INFO: Device %s (RT id = %d) cannot be uploaded. Data was: %s"
                        % (name, dev_id, str(devicedata))
                    )
                    logger.info(msg)

            else:
                # device has no name thus it cannot be migrated
                if bad_tag:
                    msg2 = f"Device with RT id={dev_id} cannot be migrated because it has bad tags."
                else:
                    msg2 = f"Device with RT id={dev_id} cannot be migrated because it has no name."
                msg = f"\n-----------------------------------------------------------------------\
                \n[!] INFO: {msg2} "
                logger.info(msg)

    def get_devices_ips_ints(self, dev_id):
        ipv4_ints = self.get_device_ipv4_ints(dev_id)
        ipv6_ints = self.get_device_ipv6_ints(dev_id)
        return_obj = ipv4_ints
        for interface in ipv6_ints.keys():
            if interface in return_obj:
                return_obj[interface] = return_obj[interface] + ipv6_ints[interface]
            else:
                return_obj[interface] = ipv6_ints[interface]
        return return_obj

    def get_device_ipv4_ints(self, dev_id):
        if not self.con:
            self.connect()
        cur = self.con.cursor()
        q = f"""SELECT
                IPv4Allocation.ip,IPv4Allocation.name
                FROM IPv4Allocation
                WHERE object_id = {dev_id}"""
        cur.execute(q)
        data = cur.fetchall()
        cur.close()
        self.con = None

        # if config["Log"]["DEBUG"]:
        #     msg = ("Device to IP", str(data))
        #     logger.debug(msg)

        interfaces = {}
        for ip_obj in data:

            rawip, nic_name = ip_obj
            if not nic_name:
                nic_name = "UNKNOWN"
            ip = self.convert_ip(rawip)

            if not nic_name in interfaces.keys():
                interfaces[nic_name] = []
            interfaces[nic_name].append(f"{ip}/{netbox.get_ip_prefix_size(ip)}")
        return interfaces

    def get_device_ipv6_ints(self, dev_id):
        if not self.con:
            self.connect()
        cur = self.con.cursor()
        q = f"""SELECT
                IPv6Allocation.ip,IPv6Allocation.name
                FROM IPv6Allocation
                WHERE object_id = {dev_id}"""
        cur.execute(q)
        data = cur.fetchall()
        cur.close()
        self.con = None

        # if config["Log"]["DEBUG"]:
        #     msg = ("Device to IP", str(data))
        #     logger.debug(msg)

        interfaces = {}
        for ip_obj in data:
            rawip, nic_name = ip_obj
            if not nic_name:
                nic_name = "UNKNOWN"
            ip = self.convert_ip_v6(rawip)
            if not nic_name in interfaces.keys():
                interfaces[nic_name] = []
            interfaces[nic_name].append(f"{ip}/{netbox.get_ip_prefix_size(ip)}")
        return interfaces

    def get_device_to_ip(self):
        if not self.con:
            self.connect()
        with self.con:
            # get hardware items (except PDU's)
            cur = self.con.cursor()
            q = (
                """SELECT
                    IPv4Allocation.ip,IPv4Allocation.name
                    Object.name as hostname
                    FROM %s.`IPv4Allocation`
                    LEFT JOIN Object ON Object.id = object_id"""
                % config["MySQL"]["DB_NAME"]
            )
            cur.execute(q)
        data = cur.fetchall()
        cur.close()
        self.con = None

        if config["Log"]["DEBUG"]:
            msg = ("Device to IP", str(data))
            logger.debug(msg)

        for line in data:
            devmap = {}
            rawip, nic_name, hostname = line
            ip = self.convert_ip(rawip)
            devmap.update({"ipaddress": ip})
            devmap.update({"device": hostname})
            if nic_name:
                devmap.update({"tag": nic_name})
            netbox.post_ip(devmap)

    def get_pdus(self):
        roles = {str(item.name): dict(item) for item in py_netbox.dcim.device_roles.all()}
        pp.pprint(roles)
        if not "Power" in roles.keys():
            create_role = {
                "name": "Power",
                "slug": "power",
            }
            py_netbox.dcim.device_roles.create(create_role)
            roles = {str(item.name): dict(item) for item in py_netbox.dcim.device_roles.all()}
        PDU_DEVICE_ROLE = roles["Power"]["id"]
        if not self.all_ports:
            self.get_ports()
        if not self.con:
            self.connect()
        with self.con:
            cur = self.con.cursor()
            q = """SELECT
                    
                    Object.id, Object.name, Object.label, asset_no, comment, unit_no, 
                    RackSpace.atom as Position, (SELECT Object.id FROM Object WHERE Object.id = RackSpace.rack_id) as RackID,
                    Object.has_problems
                    FROM Object
                    LEFT JOIN RackSpace ON RackSpace.object_id = Object.id
                    WHERE Object.objtype_id = 2
                  """
            # q = q + "and Object.id = 7507 "
            q = q + "and " + config["Misc"]["device_data_filter_obj_only"]
            print(q)
            cur.execute(q)
        data = cur.fetchall()
        cur.close()
        self.con = None
        if config["Log"]["DEBUG"]:
            msg = ("PDUs", str(data))
            logger.debug(msg)

        rack_mounted = []
        pdumap = {}
        pdumodels = []
        pdu_rack_models = []
        processed_ids = []

        for line in data:
            process = True
            pdumodel = {}
            pdudata = {}
            line = ["" if x is None else x for x in line]
            # print(line)
            pdu_id, name, label, asset_num, comment, unit_no, position, rack_id, has_problems = line
            print(pdu_id)
            if has_problems == "yes":
                has_problems = True
            else:
                has_problems = False
            if pdu_id not in processed_ids:  # query may return pdu_id multiple times, skip if already processed
                processed_ids.append(pdu_id)
                # pdu_id, name, asset, comment, pdu_type, position, rack_id = line
                pdu_attribs = racktables.get_attribs_for_obj(pdu_id)

                rt_tags = self.get_tags_for_obj("object", int(pdu_id))
                tags = []
                for tag in rt_tags:
                    try:
                        # print(tag)
                        tags.append(self.tag_map[tag]["id"])
                    except:
                        logger.debug("failed to find tag {} in lookup map".format(tag))

                bad_tags = []
                bad_tag = False
                for tag_check in config["Misc"]["SKIP_OBJECTS_WITH_TAGS"].strip().split(","):
                    logger.debug(f"checking for tag '{tag_check}'")
                    if self.tag_map[tag_check]["id"] in tags:
                        logger.debug(f"tag matched by id")
                        bad_tag = True
                        bad_tags.append(tag_check)
                if bad_tag:
                    process = False
                    name = None
                    logger.info(f"skipping object rt_id:{pdu_id} as it has tags: {str(bad_tags)}")
                    continue
                logger.info(f"pdu_attribs: {pdu_attribs}")
                if not "hw_type" in pdu_attribs:
                    # logger.info(f"skipping object rt_id:{pdu_id} as it has no hw type assigned")
                    # continue
                    if position:
                        pdu_attribs["hw_type"] = "generic_1u_short_device"
                    else:
                        pdu_attribs["hw_type"] = "generic_0u_device"
                    logger.info(f"HW Type(position check) is: {pdu_attribs['hw_type']}")

                # if "%GPASS%" in pdu_attribs['HW type']:
                pdu_type = pdu_attribs["hw_type"].replace("%GPASS%", " ")
                del pdu_attribs["hw_type"]
                pdu_attribs["rt_id"] = str(pdu_id)
                if "asset_tag" in pdu_attribs.keys():
                    del pdu_attribs["asset_tag"]

                pdu_type = self.remove_links(pdu_type[:64])
                name = self.remove_links(name)
                pdudata.update({"name": name})
                pdudata.update({"notes": comment})
                pdudata.update({"pdu_model": pdu_type})
                pdudata.update({"custom_fields": pdu_attribs})
                pdudata.update({"asset_tag": asset_num})
                pdudata.update({"rack": rack_id})
                pdudata["device_type"] = netbox.device_type_checker(pdudata["pdu_model"])
                if pdudata["device_type"] == None:
                    if not pdudata["pdu_model"] in self.skipped_devices.keys():
                        self.skipped_devices[pdudata["pdu_model"]] = 1
                    else:
                        self.skipped_devices[pdudata["pdu_model"]] = self.skipped_devices[pdudata["pdu_model"]] + 1
                    process_object = False
                pdumodel.update({"name": pdu_type})
                pdumodel.update({"pdu_model": pdu_type})
                # print(pdudata)
                # print(pdumodel)
                # print("")

                # post pdus
                if pdu_id not in pdumap:
                    # response = netbox.post_pdu(pdudata)
                    # d42_pdu_id = response["msg"][1]
                    pdumap.update({pdu_id: pdudata})

                # mount to rack
                if position and process:
                    if pdu_id not in rack_mounted:
                        rack_mounted.append(pdu_id)
                        position, height, depth, mount = self.get_hardware_size(pdu_id)
                        if True:
                            # try:
                            rack_data = netbox.get_rack_by_rt_id(pdudata["rack"])
                            site_id = rack_data["site"]["id"]
                            rack_id = rack_data["id"]
                            if rack_data["location"]["id"]:
                                rack_location = rack_data["location"]["id"]
                            else:
                                rack_location = None
                            if position:
                                rdata = {}
                                rdata.update({"position": position})
                                rdata.update({"face": mount})
                                rdata.update({"rack": rack_id})
                                rdata.update({"location": rack_location})
                                rdata["device_role"] = PDU_DEVICE_ROLE
                                rdata["device_type"] = pdudata["device_type"]
                                rdata.update({"name": pdudata["name"]})
                                rdata["site"] = site_id
                                rdata.update({"comments": pdudata["notes"]})
                                rdata["custom_fields"] = pdudata["custom_fields"]
                                if pdudata["asset_tag"]:
                                    if pdudata["asset_tag"].strip() != "":
                                        rdata["asset_tag"] = pdudata["asset_tag"]
                                # pp.pprint(rdata)
                                logger.info(f"adding 0U pdu: {rdata['name']}")

                                logger.debug(rdata)
                                netbox.post_device(rdata)
                                # netbox.post_pdu_to_rack(rdata, d42_rack_id)
                                ports = self.get_ports_by_device(self.all_ports, str(pdu_id))

                                ip_ints = self.get_devices_ips_ints(str(pdu_id))
                                # pp.pprint(ip_ints)
                                netbox.create_device_interfaces(str(pdu_id), ports, ip_ints)
                        # except TypeError:
                        #     msg = (
                        #         '\n-----------------------------------------------------------------------\
                        #     \n[!] INFO: Cannot mount pdu "%s" (RT id = %d) to the rack.\
                        #     \n\tFloor returned from "get_hardware_size" function was: %s'
                        #         % (name, pdu_id, str(floor))
                        #     )
                        #     logger.info(msg)
                        # except KeyError:
                        #     msg = (
                        #         '\n-----------------------------------------------------------------------\
                        #     \n[!] INFO: Cannot mount pdu "%s" (RT id = %d) to the rack.\
                        #     \n\tWrong rack id map value1: %s'
                        #         % (name, pdu_id, str(rack_id))
                        #     )
                        #     logger.info(msg)
                # It's Zero-U then
                elif process:
                    print("0u pdu")

                    rt_rack_id = self.get_rack_id_for_zero_us(pdu_id)
                    if rt_rack_id:
                        rack_data = netbox.get_rack_by_rt_id(rt_rack_id)
                        site_id = rack_data["site"]["id"]
                        rack_id = rack_data["id"]
                        # pp.pprint(dict(rack_data))
                        pdudata["rack"] = rack_id

                        if rack_data["location"]["id"]:
                            rack_location = rack_data["location"]["id"]
                    else:
                        rack_id = None
                        rack_location = None

                    # exit(22)
                    if rack_id:

                        mount = "rear"
                        rdata = {}
                        # pdudata.update({"name": name })
                        # pdudata.update({"notes": comment})
                        # pdudata.update({"pdu_model": pdu_type})
                        # pdudata.update({"custom_fields": pdu_attribs})
                        # pdudata.update({"asset_tag": asset_num})
                        # pdudata.update({"rack":rack_id})
                        device_added = False
                        try:
                            rdata.update({"rack": rack_id})
                            rdata["device_role"] = PDU_DEVICE_ROLE
                            rdata["device_type"] = pdudata["device_type"]
                            rdata.update({"name": pdudata["name"]})
                            rdata["site"] = site_id
                            rdata["location"] = rack_location
                            rdata.update({"comments": pdudata["notes"]})
                            rdata["custom_fields"] = pdudata["custom_fields"]
                            if pdudata["asset_tag"]:
                                if pdudata["asset_tag"].strip() != "":
                                    rdata["asset_tag"] = pdudata["asset_tag"]
                            rdata.update({"face": mount})
                            # pp.pprint(rdata)
                            logger.info(f"adding 0U pdu: {rdata['name']}")
                            logger.debug(rdata)
                            netbox.post_device(rdata)
                            device_added = True
                        except UnboundLocalError:
                            device_added = False
                            msg = (
                                '\n-----------------------------------------------------------------------\
                            \n[!] INFO: Cannot mount pdu "%s" (RT id = %d) to the rack.\
                            \n\tWrong rack id: %s'
                                % (name, pdu_id, str(rack_id))
                            )
                            logger.info(msg)
                        if device_added:
                            ports = self.get_ports_by_device(self.all_ports, str(pdu_id))
                            ip_ints = self.get_devices_ips_ints(str(pdu_id))
                            netbox.create_device_interfaces(str(pdu_id), ports, ip_ints)
                    else:
                        logger.error(f"could not find rack for PDU rt_id: {pdu_id}")
        logger.debug("skipped devices:")
        pp.pprint(self.skipped_devices)

    def get_patch_panels(self):
        roles = {str(item.name): dict(item) for item in py_netbox.dcim.device_roles.all()}
        pp.pprint(roles)
        if not "Patching" in roles.keys():
            create_role = {
                "name": "Patching",
                "slug": "patching",
            }
            py_netbox.dcim.device_roles.create(create_role)
            roles = {str(item.name): dict(item) for item in py_netbox.dcim.device_roles.all()}
        PATCHING_DEVICE_ROLE = roles["Patching"]["id"]
        if not self.all_ports:
            self.get_ports()
        if not self.con:
            self.connect()

        with self.con:
            cur = self.con.cursor()
            q = """SELECT
                   id,
                   name,
                   AttributeValue.uint_value as num_of_ports,
                   label,
                   comment
                   FROM Object
                   LEFT JOIN AttributeValue ON AttributeValue.object_id = id AND AttributeValue.attr_id = 6
                   WHERE Object.objtype_id = 9
                 """
            cur.execute(q)
        data = cur.fetchall()
        cur.close()
        self.con = None

        if config["Log"]["DEBUG"]:
            msg = ("PDUs", str(data))
            logger.debug(msg)

        for item in data:
            pp.pprint(item)
            ports = self.get_ports_by_device(self.all_ports, item[0])
            attribs = self.get_attribs_for_obj(item[0])
            # pp.pprint(attribs)
            location_data = self.get_obj_location(item[0])
            # pp.pprint(location_data)
            rack_data = netbox.get_rack_by_rt_id(location_data["rack_id"])
            site_id = rack_data["site"]["id"]
            rack_id = rack_data["id"]
            patch_type = "singular"
            port_type = None
            port_list = []

            if isinstance(ports, list) and len(ports) > 0:
                if len(ports) > 1:
                    types = []

                    # check patch_type
                    for port in ports:
                        if port[2][:12] not in types:
                            types.append(port[2][:12])

                    if len(types) >= 1:
                        patch_type = "modular"
                        for port in ports:
                            # print(port)
                            pp_data = {
                                "name": port[0],
                                "port_type": port[2][:12],
                                # "number_of_ports": 1,
                                # "number_of_ports_in_row": 1,
                            }
                            port_list.append(pp_data)

                if patch_type == "singular":
                    port_type = ports[0][2][:12]
            # attribs["number_of_ports"] = item[2]
            # attribs["number_of_ports_in_row"] = item[2]
            if item[3]:
                attribs[self.custom_field_name_slugger("Visible label")] = item[3]
            attribs["rt_id"] = str(item[0])
            payload = {
                "name": item[1],
                # "type": patch_type,
                # "comments": item[4],
                "custom_fields": attribs,
                "device_role": PATCHING_DEVICE_ROLE,
                "site": site_id,
            }
            if item[4]:
                payload["comments"] = item[4]
            if location_data["rack_mounted"]:
                payload.update({"position": location_data["position_data"]["u"]})
                payload.update({"face": location_data["position_data"]["face"]})
                payload.update({"device_type": netbox.device_type_checker("generic_1u_patch_panel")})
            else:
                payload.update({"device_type": netbox.device_type_checker("generic_0u_patch_panel")})
            payload.update({"rack": rack_id})

            # if port_type is not None:
            #     payload.update({"port_type": port_type})

            # payload['port_list'] = port_list

            # netbox.post_patch_panel(payload)
            netbox.post_device(payload)

            ip_ints = self.get_devices_ips_ints(item[0])
            # pp.pprint(ip_ints)
            netbox.create_device_interfaces(item[0], ports, ip_ints)
            # ports = False
            if ports:
                for item in ports:
                    switchport_data = {
                        "local_port": item[0],
                        "local_device": payload["name"],
                        "local_device_rt_id": item[0],
                        "local_label": item[1],
                    }

                    get_links = self.get_links(item[3])
                    pp.pprint("here get_links")
                    pp.pprint(get_links)

                    if get_links:
                        remote_device_name = self.get_device_by_port(get_links[0])
                        switchport_data.update({"remote_device": remote_device_name})
                        switchport_data.update({"remote_port": self.get_port_by_id(self.all_ports, get_links[0])})
                        pp.pprint(switchport_data)

                        netbox.create_cables_between_devices(switchport_data)

            print("")

    def get_ports(self):
        if self.all_ports:
            return self.all_ports
        if not self.con:
            self.connect()
        with self.con:
            cur = self.con.cursor()
            q = """SELECT
                    name,
                    label,
                    PortOuterInterface.oif_name,
                    Port.id,
                    object_id
                    FROM Port
                    LEFT JOIN PortOuterInterface ON PortOuterInterface.id = type"""
            cur.execute(q)
        data = cur.fetchall()
        cur.close()
        self.con = None
        if data:
            self.all_ports = data
            return data
        else:
            return False

    # to remove duplication in get pdus devices patchpanels
    def manage_interfaces_obj(self, obj_type, obj_id, obj_name):
        ports = self.get_ports_by_device(self.all_ports, obj_id)
        for item in ports:
            switchport_data = {
                "local_port": item[0],
                "local_device": obj_name,
                "local_device_rt_id": item[0],
                "local_label": item[1],
            }

            get_links = self.get_links(item[3])
            pp.pprint("here get_links")
            pp.pprint(get_links)

            if get_links:
                remote_device_name = self.get_device_by_port(get_links[0])
                switchport_data.update({"remote_device": remote_device_name})
                switchport_data.update({"remote_port": self.get_port_by_id(self.all_ports, get_links[0])})
                pp.pprint(switchport_data)

                netbox.create_cables_between_devices(switchport_data)

    @staticmethod
    def get_ports_by_device(ports, device_id):
        device_ports = []
        ports_found = False
        for port in ports:
            if port[4] == device_id:
                print(port)
                ports_found = True
                if not "AC-" in port[0] and not "RS-232" in port[0]:
                    device_ports.append(port)

        return device_ports

    @staticmethod
    def get_port_by_id(ports, port_id):
        for port in ports:
            if port[3] == port_id:
                return port[0]

    def get_device_by_port(self, port_id):
        if not self.con:
            self.connect()
        with self.con:
            cur = self.con.cursor()
            q = (
                """SELECT
                    id,name
                    FROM Object
                    WHERE id = ( SELECT object_id FROM Port WHERE id = %s )"""
                % port_id
            )
            cur.execute(q)
        data = cur.fetchone()
        cur.close()
        self.con = None
        if data:
            return {"id": data[0], "name": data[1]}
        else:
            return False

    def get_links(self, port_id):
        if not self.con:
            self.connect()
        with self.con:
            cur = self.con.cursor()
            q = (
                """SELECT
                    porta,
                    portb
                    FROM Link
                    WHERE portb = %s"""
                % port_id
            )
            cur.execute(q)
        data = cur.fetchall()
        cur.close()
        self.con = None
        if data:
            return data[0]
        else:
            if not self.con:
                self.connect()
            with self.con:
                cur = self.con.cursor()
                q = (
                    """SELECT
                        portb,
                        porta
                        FROM Link
                        WHERE porta = %s"""
                    % port_id
                )
                cur.execute(q)
            data = cur.fetchall()
            cur.close()
            self.con = None
            if data:
                return data[0]
            else:
                return False

    def get_rack_id_for_zero_us(self, pdu_id):
        if not self.con:
            self.connect()
        with self.con:
            cur = self.con.cursor()
            q = (
                """SELECT
                    EntityLink.parent_entity_id
                    FROM EntityLink
                    WHERE EntityLink.child_entity_id = %s
                    AND EntityLink.parent_entity_type = 'rack'"""
                % pdu_id
            )
            cur.execute(q)
        data = cur.fetchone()
        cur.close()
        self.con = None
        if data:
            return data[0]

    def get_tags_of_obj_false_if_skip(self, obj_id):
        if not self.tag_map:
            self.create_tag_map()
        rt_tags = self.get_tags_for_obj("object", int(obj_id))
        tags = []
        for tag in rt_tags:
            try:
                # print(tag)
                tags.append(self.tag_map[tag]["id"])
            except:
                logger.debug("failed to find tag {} in lookup map".format(tag))

        bad_tags = []
        bad_tag = False
        for tag_check in config["Misc"]["SKIP_OBJECTS_WITH_TAGS"].strip().split(","):
            logger.debug(f"checking for tag '{tag_check}'")
            if self.tag_map[tag_check]["id"] in tags:
                logger.debug(f"tag matched by id")
                bad_tag = True
                bad_tags.append(tag_check)
        if bad_tag:
            logger.info(f"object rt_id:{obj_id} as it has tags: {str(bad_tags)}")
            return False, tags
        else:
            return True, tags

    def get_vms(self):
        if not self.all_ports:
            self.get_ports()
        if not bool(self.container_map):
            self.get_container_map()
        if not self.con:
            self.connect()
        with self.con:
            cur = self.con.cursor()
            q = f"SELECT * FROM Object "
            q = q + f"WHERE Object.objtype_id in (1504 {config['Misc']['vm_objtype_ids']}) ORDER BY Object.id desc"
            # q = q + " and Object.id = 7975 "
            # q = q + " limit 20"
            cur.execute(q)
            data = cur.fetchall()
            cur.close()
        self.con = None

        for vm_data_tupple in data:
            vm_data = {}
            id, name, label, objtypeid, asset_no, has_problems, comment = vm_data_tupple
            logger.debug(f"start of vm: {id} {name}")

            # vm_data["id"] = id
            vm_data["name"] = name
            vm_data["asset_tag"] = asset_no
            if comment:
                vm_data["comments"] = comment
            vm_data["custom_fields"] = self.get_attribs_for_obj(id)
            vm_data["custom_fields"][self.custom_field_name_slugger("Visible Label")] = label
            vm_data["custom_fields"]["rt_id"] = str(id)

            tag_resp = self.get_tags_of_obj_false_if_skip(id)
            if tag_resp[0]:
                vm_data["tags"] = tag_resp[1]
            else:
                logger.debug(f"end of vm: {name} due to skipped tags")
                continue

            # if id in self.container_map.keys():
            if id in self.container_map.keys():
                vm_data["custom_fields"]["rt_id_parent"] = str(self.container_map[id])

            logger.debug(vm_data)
            netbox.manage_vm(vm_data)
            ports = self.get_ports_by_device(self.all_ports, id)

            ip_ints = self.get_devices_ips_ints(id)
            # pp.pprint(ip_ints)
            netbox.create_device_interfaces(id, ports, ip_ints, True, "virtual")
            logger.debug(f"end of vm: {id} {name}")

    def get_files(self):
        if not self.con:
            self.connect()
        with self.con:
            cur = self.con.cursor()
            q = f"""SELECT FileLink.id as link_id,
                    FileLink.file_id as file_id,
                    FileLink.entity_type as entity_type,
                    FileLink.entity_id as entity_id,
                    File.name as file_name,
                    File.type as file_type,
                    File.contents as file_content,
                    File.comment as file_comment
                    FROM FileLink left join File on File.id = FileLink.file_id
                    Order by link_id asc;"""
            cur.execute(q)
            data = cur.fetchall()
            cur.close()
        self.con = None
        entity_links = {}
        for file_tupple_data in data:
            file_link_data = {}
            link_id, file_id, entity_type, entity_id, file_name, file_type, file_content, file_comment = file_tupple_data
            file_link_data["link_id"] = link_id
            file_link_data["file_id"] = file_id
            file_link_data["entity_type"] = entity_type
            file_link_data["entity_id"] = entity_id
            file_link_data["file_name"] = file_name
            file_link_data["file_type"] = file_type
            file_link_data["file_content"] = file_content
            file_link_data["file_comment"] = file_comment

            export_filename = f"{file_id}_{file_name}"
            logger.debug(f"start of link_id: {link_id} - {file_name}")
            current_file = f"./file_exports/{export_filename}"
            file_link_data["export_file_name"] = current_file
            if os.path.exists(f"./file_exports/{export_filename}"):
                print("file already exists")
            else:
                print("writing file")
                f = open(current_file, "wb")
                f.write(file_content)
                f.close()
            entity = f"{entity_type}_{entity_id}"
            print(entity)
            if not entity in entity_links.keys():
                entity_links[entity] = []
            entity_links[entity].append(file_link_data)

        for entity, entity_data in entity_links.items():
            entity_comment_data = ""
            if len(entity_data) > 1:
                # print(entity)
                print(f"I have more than one file attached: {entity}")
            else:
                print("I have only one file attached")
            for linkdata in entity_data:
                filename = linkdata["export_file_name"].split("file_exports/")[1]
                description = f"external_file: {linkdata['file_name']}"
                if not linkdata["file_comment"] == "":
                    comment = f"\n\n{linkdata['file_comment']}"
                else:
                    comment = ""
                entity_comment_data = entity_comment_data + f"\n\n[{description}]({config['Misc']['FILE_SEARCH_URI']}{urllib.parse.quote(filename)}){comment}"
            entity_comment_data = entity_comment_data.strip("\n\n")
            print(entity_comment_data)
            update_device = netbox.update_object_file_links(linkdata["entity_type"], linkdata["entity_id"], entity_comment_data)
            print("")


if __name__ == "__main__":
    # Import config
    # configfile = "conf"
    # config = configparser.RawConfigParser()
    # config.read(configfile)
    if os.environ.get("rt2nb_conf_file_name"):
        conf_file_name = os.environ.get("rt2nb_conf_file_name")
    else:
        conf_file_name = "conf.yaml"
    try:
        with open(conf_file_name, "r") as stream:
            config = yaml.safe_load(stream)
    except:
        with open(os.getcwd() + "/" + conf_file_name, "r") as stream:
            config = yaml.safe_load(stream)

    # Initialize Data pretty printer
    pp = pprint.PrettyPrinter(indent=4, width=100)

    # Initialize logging platform
    logger = logging.getLogger("rt2nb")
    logger.setLevel(logging.DEBUG)

    # Log to file
    fh = logging.FileHandler(config["Log"]["LOGFILE"])
    fh.setLevel(logging.DEBUG)

    # Log to stdout
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)

    # Format log output
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    # Attach handlers to logger
    logger.addHandler(fh)
    logger.addHandler(ch)

    # Load lookup map of yaml data
    if os.environ.get("rt2nb_hardware_map_file_name"):
        conf_file_name = os.environ.get("rt2nb_hardware_map_file_name")
    else:
        conf_file_name = "hardware_map.yaml"
    try:
        with open(conf_file_name, "r") as stream:
            device_type_map_preseed = yaml.safe_load(stream)
    except:
        with open(os.getcwd() + "/" + conf_file_name, "r") as stream:
            device_type_map_preseed = yaml.safe_load(stream)

    py_netbox = pynetbox.api(config["NetBox"]["NETBOX_HOST"], token=config["NetBox"]["NETBOX_TOKEN"])

    tenant_groups = py_netbox.tenancy.tenant_groups.all()

    netbox = NETBOX(py_netbox)
    racktables = DB()
    if config["Migrate"]["TAGS"] == True:
        logger.debug("running get tags")
        racktables.get_tags()
    if config["Migrate"]["CUSTOM_ATTRIBUTES"] == True:
        logger.debug("running get_custom_attribs")
        racktables.get_custom_attribs()
    if config["Migrate"]["INFRA"] == True:
        logger.debug("running get infra")
        racktables.get_infrastructure()
    if config["Migrate"]["VLAN"] == True:
        racktables.get_vlan_domains()
        racktables.get_vlans()
    if config["Migrate"]["SUBNETS"] == True:
        logger.debug("running get subnets")
        racktables.get_subnets()
        racktables.get_subnets_v6()
    if config["Migrate"]["IPS"] == True:
        logger.debug("running get ips")

        racktables.get_ips()
        racktables.get_ips_v6()
    if config["Migrate"]["HARDWARE"] == True:
        # logger.debug("running device types")
        # racktables.get_device_types()
        logger.debug("running manage hardware")
        racktables.get_devices()
    if config["Migrate"]["PDUS"] == True:
        racktables.get_pdus()
    if config["Migrate"]["PATCHPANELS"] == True:
        racktables.get_patch_panels()
    if config["Migrate"]["VMS"] == True:
        racktables.get_vms()
    if config["Migrate"]["FILES"] == True:
        racktables.get_files()

    migrator = Migrator()

    logger.info("[!] Done!")
    # sys.exit()
