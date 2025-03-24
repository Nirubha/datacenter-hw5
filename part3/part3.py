#!/usr/bin/env python3

import argparse
import os
import time
import traceback
import sys
from pprint import pprint

import googleapiclient.discovery
import google.auth
import google.oauth2.service_account as service_account


#
# Use Google Service Account - See https://google-auth.readthedocs.io/en/latest/reference/google.oauth2.service_account.html#module-google.oauth2.service_account
#
credentials = service_account.Credentials.from_service_account_file(filename='part3/service-credentials.json',scopes=['https://www.googleapis.com/auth/cloud-platform'])
service = googleapiclient.discovery.build('compute', 'v1', credentials=credentials)

project = "week5-project-401419"
zone='us-east1-d'
vm1_name="dhba-vm1-outside"
bucket="dharini-week5-bucket1"

def list_instances(compute, project, zone):
    result = compute.instances().list(project=project, zone=zone).execute()
    return result['items'] if 'items' in result else None

def wait_for_operation(compute, project, zone, operation):
    print('Waiting for operation {} to finish...'.format(operation))
    while True:
        result = compute.zoneOperations().get(
            project=project,
            zone=zone,
            operation=operation).execute()

        if result['status'] == 'DONE':
            print("done.")
            if 'error' in result:
                raise Exception(result['error'])
            return result

        time.sleep(30)

def create_instance():
    # Get the latest Debian Jessie image.
    image_response = (
        service.images()
        .getFromFamily(project="ubuntu-os-cloud", family="ubuntu-2204-lts")
        .execute()
    )
    source_disk_image = image_response["selfLink"]

    # Configure the machine
    machine_type = "zones/%s/machineTypes/f1-micro" % zone
    startup_script = open(
        os.path.join(
            os.path.dirname(__file__), 'startup-script-sdk.sh'), 'r').read()
    vm2_startup_script = open(
        os.path.join(
            os.path.dirname(__file__), 'startup-script-remote.sh'), 'r').read()
    vm2_launch_code = open(
        os.path.join(
            os.path.dirname(__file__), 'launch_vm2_inside.py'), 'r').read()
    service_credentials = open(
        os.path.join(
            os.path.dirname(__file__), 'service-credentials.json'), 'r').read()
    config = {
        "name": vm1_name,
        "machineType": machine_type,
        "disks": [
            {
                "boot": True,
                "autoDelete": True,
                "initializeParams": {
                    "sourceImage": source_disk_image,
                },
            }
        ],
        "networkInterfaces": [
            {
                "network": "global/networks/default",
                "accessConfigs": [{"type": "ONE_TO_ONE_NAT", "name": "External NAT"}],
            }
        ],
        "metadata": {
             "items": [
                {
                     'key': 'startup-script',
                     'value': startup_script
                },
                {
                    'key': 'service-credentials',
                    'value': service_credentials
                },
                {
                    'key': 'vm2_startup_script',
                    'value': vm2_startup_script
                },
                {
                    'key': 'vm1_launch_vm2',
                    'value': vm2_launch_code
                },
            ]
        },
    }
    operation = service.instances().insert(project=project, zone=zone, body=config).execute()

    try:
        result = wait_for_operation(service,project,zone,operation['name'])
    except Exception as ex:
        print(traceback.format_exc())
        exit(1)

    print("VM instance {} created successfully.".format(vm1_name))

    print("creating firewall rule...")
    target="allow-5000"
    firewall_rule_body = {
    "name": "allow-5000",
    "allowed": [
        {
            "IPProtocol": "tcp",
            "ports": ["5000"]
        }
    ],
    "sourceRanges": ["0.0.0.0/0"],  # Allow access from anywhere
    "targetTags": ["allow-5000"],
    }
    try:
        request = service.firewalls().insert(project=project, body=firewall_rule_body)
        response = request.execute()
    except Exception as e:
        print('Could not create firewall rule. Check if the rule already exists')
        pass
    current_fingerprint = service.instances().get(project=project, zone=zone, instance=vm1_name).execute()['tags']['fingerprint']

    tags_body = {
        "items": [
            target
        ],
        "fingerprint": current_fingerprint
    }
    requestAdd = service.instances().setTags(project=project, zone=zone, instance=vm1_name, body=tags_body)
    response = requestAdd.execute()
    print("Network tag added to instance:-\n", vm1_name)

create_instance()

print("Your running instances are:")
for instance in list_instances(service, project,zone):
    print(instance['name'])