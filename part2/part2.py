#!/usr/bin/env python3

import argparse
import sys
import os
import time
from pprint import pprint

main_script_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../part1'))
sys.path.append(main_script_dir)

import part1 as p1
import googleapiclient.discovery
import google.auth
from typing import Any

credentials, project = google.auth.default()
service = googleapiclient.discovery.build('compute', 'v1', credentials=credentials)

#
# Stub code - just lists all instances
#
file_path = "part2/TIMING.md"
copies = 3

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
    image_response = (
        compute.images()
        .getFromFamily(project="ubuntu-os-cloud", family="ubuntu-2204-lts")
        .execute()
    )
    source_disk_image = image_response["selfLink"]

    machine_type = "zones/%s/machineTypes/f1-micro" % zone
    startup_script = open(os.path.join(os.path.dirname(__file__), "startup-script.sh")).read()

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
    target="allow-5000"
    firewall_rule_body = {
    "name": "allow-5000",
    "allowed": [
        {
            "IPProtocol": "tcp",
            "ports": ["5000"]
        }
    ],
    "sourceRanges": ["0.0.0.0/0"],
    "targetTags": [f"allow-5000"],
    }
    try:
        request = compute.firewalls().insert(project=project, body=firewall_rule_body)
        response = request.execute()
    except Exception as e:
        print('Could not create firewall rule. Check if the rule already exists')
        pass

    print("\nFirewall rule added to instance:-", instance)
    return target

def setTags(compute, project, instance, zone, fingerprint,target):
    tags_body = {
        "items": [
            target
        ],
        "fingerprint": fingerprint
    }
    requestAdd = compute.instances().setTags(project=project, zone=zone, instance=instance, body=tags_body)
    response = requestAdd.execute()


def create_snapshot(compute,project, zone, disk_name, snapshot_name):
    snapshot_body = {
        'name': snapshot_name,
        'sourceDisk': f'projects/{project}/zones/{zone}/disks/{disk_name}'
    }

    snapshot = compute.disks().createSnapshot(
        project=project,
        zone=zone,
        disk=disk_name,
        body=snapshot_body
    ).execute()

    # print(f'Snapshot created: {snapshot_name}')
    return snapshot

def create_image_from_snapshot(compute, project, snapshot_name,image_name):
    image_snapshot_body = {
        "name": image_name,
        "sourceSnapshot": "global/snapshots/%s"%(snapshot_name)
    }
    return compute.images().insert(project=project, body=image_snapshot_body).execute()

def create_instance_from_snapshot(compute, project, zone, instance_name, snapshot_name,bucket):
    source_snapshot_url = f"projects/{project}/global/snapshots/{snapshot_name}"
    startup_script = open(os.path.join(os.path.dirname(__file__), "startup-script.sh")).read()
    instance_config = {
        "name": instance_name,
        "machineType": f"zones/%s/machineTypes/f1-micro" % zone,
        "disks": [
            {
                "boot": True,
                "autoDelete": False,
                "initializeParams": {
                    "sourceSnapshot": source_snapshot_url,
                },

            }
        ],
        "networkInterfaces": [
            {
                "network": f'projects/{project}/global/networks/default',
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
        }
    }
    response = compute.instances().insert(project=project, zone=zone, body=instance_config).execute()
    return response


def main(
    project: str,
    bucket: str,
    zone: str,
    instance_name: str,
    wait=True,
) -> None: 
    compute = googleapiclient.discovery.build("compute", "v1")

    print("Creating instance.")
    operation= p1.create_instance(compute, project, zone, instance_name, bucket)
    wait_for_operation(compute, project, zone, operation["name"])

    print("Getting all the running instances")
    instances = list_instances(compute, project, zone)
    print(f"Instances in project {project} and zone {zone}:")
    for instance in instances:
        print(f'INSTANCE:- {instance["name"]}')
        print("Creating firewall and set network tags")
        network_tag=create_firewall_rule(compute,project,instance['name'],zone,instance['tags']['fingerprint'])
        setTags(compute,project,instance['name'],zone,instance['tags']['fingerprint'],network_tag)
        print(f'External_IP_address:- {instance["networkInterfaces"][0]["accessConfigs"][0]["natIP"]}\n')
    
    print("Creating a snapshot from instance")
    snapshot_name = "base-snapshot-"+instance_name
    print(f'Creating snapshot from the instance:- {instance_name}')
    network_tag=create_firewall_rule(compute,project,instance['name'],zone,instance['tags']['fingerprint'])
    operation=create_snapshot(compute,project,zone,instance['name'],snapshot_name)
    wait_for_operation(compute, project, args.zone, operation['name'])
    print(f'snapshot:- {snapshot_name} has been created\n')
    image_name = "image-from-snapshot1"
    print(f'Creating image {image_name} from snapshot {snapshot_name}...')
    image = create_image_from_snapshot(compute, project, snapshot_name,image_name)
    print(f'Image {image_name} created with ID: {image["id"]}\n')

    print("Creating 3 copies from snapshot....")
   
    
    for instance in instances:
        for i in range(copies):
            start_time = time.time()
            new_instance_name=instance['name']+'-copy-'+str(i+1)
            print(f'\nCreating new instance {i+1}')
            print("new instance: " + new_instance_name)
            operation = create_instance_from_snapshot(compute, project, zone, new_instance_name, snapshot_name,bucket)
            wait_for_operation(compute, project, args.zone, operation['name'])
            setTags(compute,project,new_instance_name,zone,instance['tags']['fingerprint'],network_tag)
            print("Added network tags")
            markdown_content = "--- Clone %d took %s seconds ---" % (i+1, time.time() - start_time)
            if i == 0 :
                with open(file_path, "w") as md_file:
                    md_file.write(markdown_content)
            else :
                with open(file_path, "a") as md_file:
                    md_file.write(markdown_content)


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