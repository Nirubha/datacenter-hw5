#!/usr/bin/env python3

import argparse
import os
import time
from pprint import pprint

import googleapiclient.discovery
import google.auth

credentials, project = google.auth.default()
#service = googleapiclient.discovery.build('compute', 'v1', credentials=credentials)

#
# Stub code - just lists all instances
#
def list_instances(compute, project, zone):
    result = compute.instances().list(project=project, zone=zone).execute()
    return result['items'] if 'items' in result else None

def create_instance(
    compute: object,
    project: str,
    zone: str,
    name: str,
    bucket: str,
) -> str:
 
    # Get the latest Ubuntu image.
    image_response = (
        compute.images()
        .getFromFamily(project="ubuntu-os-cloud", family="ubuntu-2204-lts")
        .execute()
    )
    source_disk_image = image_response["selfLink"]

    # Configure the machine
    machine_type = "zones/%s/machineTypes/f1-micro" % zone
    startup_script = open(
        os.path.join(os.path.dirname(__file__), "startup-script.sh")
    ).read()

    config = {
        "name": name,
        "machineType": machine_type,
        "disks": [
            {
                "boot": True,
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
       "serviceAccounts": [
           {
               "email": "default",
                "scopes": [
                    "https://www.googleapis.com/auth/devstorage.read_write",
                    "https://www.googleapis.com/auth/logging.write",
                ],
            }
        ],
        "metadata": {
            "items": [
                {
                    "key": "startup-script",
                    "value": startup_script,
                },
                {"key": "bucket", "value": bucket},
            ]
        },
    }
    print(f'Instance {name} created')
    return compute.instances().insert(project=project, zone=zone, body=config).execute()

def wait_for_operation(
    compute: object,
    project: str,
    zone: str,
    operation: str,
) -> dict:
    print(f'Waiting for operation {operation} to finish...')
    while True:
        result = (
            compute.zoneOperations()
            .get(project=project, zone=zone, operation=operation)
            .execute()
        )

        if result["status"] == "DONE":
            print("done.")
            if "error" in result:
                raise Exception(result["error"])
            return result

        time.sleep(1)

def create_firewall_rule(compute, project, instance, zone,fingerprint):
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
        request = compute.firewalls().insert(project=project, body=firewall_rule_body)
        response = request.execute()
    except Exception as e:
        print('Could not create firewall rule. Check if the rule already exists')
        pass
    
    tags_body = {
        "items": [
            target
        ],
        "fingerprint": fingerprint
    }
    requestAdd = compute.instances().setTags(project=project, zone=zone, instance=instance, body=tags_body)
    response = requestAdd.execute()
    print("Network tag added to instance:-\n", instance)
    

def main(
    project: str,
    bucket: str,
    zone: str,
    instance_name: str,
    wait=True,
) -> None:

    compute = googleapiclient.discovery.build("compute", "v1")
    print("Creating new instance")
    operation = create_instance(compute, project, zone, instance_name, bucket)
    wait_for_operation(compute, project, zone, operation["name"])

    print("Getting all the running instances")
    instances = list_instances(compute, project, zone)
    print(f"Instances in project {project} and zone {zone}:")
    for instance in instances:
        print(f'INSTANCE:- {instance["name"]}')

    for instance in instances:
        print("\nCreating firewall and network tags")
        create_firewall_rule(compute,project,instance['name'],zone,instance['tags']['fingerprint'])
        print(f'External_IP_address:- {instance["networkInterfaces"][0]["accessConfigs"][0]["natIP"]}\n')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('project_id', default='week5-project-401419', help='Your Google Cloud project ID.')
    parser.add_argument('bucket_name', default='dharini-week5-bucket1', help='Your Google Cloud Storage bucket name.')
    parser.add_argument(
        '--zone',
        default='us-east1-d',
        help='Compute Engine zone to deploy to.')
    parser.add_argument(
        '--name', default='demo-remote-instance', help='New instance name.')
    
    args = parser.parse_args()
    main(args.project_id, args.bucket_name, args.zone, args.name)