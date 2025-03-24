import os
import time
import traceback
from pprint import pprint
import sys

import googleapiclient.discovery
import google.auth
import google.oauth2.service_account as service_account

#
# Use Google Service Account - See https://google-auth.readthedocs.io/en/latest/reference/google.oauth2.service_account.html#module-google.oauth2.service_account
#
credentials = service_account.Credentials.from_service_account_file(filename='service-credentials.json',scopes=['https://www.googleapis.com/auth/cloud-platform'])
service = googleapiclient.discovery.build('compute', 'v1', credentials=credentials)

project = "week5-project-401419"
zone='us-east1-d'
vm2_name="dhba-vm2-inside"
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

        time.sleep(1)
def create_instance(compute,project,zone,name,bucket):
    
    image_response = (
        compute.images()
        .getFromFamily(project="ubuntu-os-cloud", family="ubuntu-2204-lts")
        .execute()
    )
    source_disk_image = image_response["selfLink"]

    machine_type = "zones/%s/machineTypes/f1-micro" % zone
    vm2_startup_script = open(
        os.path.join(
            os.path.dirname(__file__), 'startup-script-remote.sh'), 'r').read()
    config = {
        "name": name,
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
                    'value': vm2_startup_script
                },
            ]
        },
    }

    tags_body = {
        "items": [
            "allow-5000"
        ],
        "fingerprint": ""
    }
    operation = service.instances().insert(project=project, zone=zone, body=config).execute()

    try:
        result = wait_for_operation(service, project, zone, operation['name'])
    except Exception as ex:
        print(ex)
        exit(1)
    for instance in list_instances(service, project, zone):
        if instance['name'] == name:
            print(instance['name'])
            break

    ip = instance["networkInterfaces"][0]["accessConfigs"][0]["natIP"]

    tags_body["fingerprint"] = instance["tags"]["fingerprint"]

    response = service.instances().setTags(project=project, zone=zone, instance=name, body=tags_body).execute()


    print("Access the flask app here http://{}:5000".format(ip))

    print("VM instance {} created successfully.".format(vm2_name))

create_instance(service,project,zone,vm2_name,bucket)