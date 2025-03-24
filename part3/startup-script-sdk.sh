#mkdir -p /srv
#cd /srv
cd /home/dhba5060

curl http://metadata/computeMetadata/v1/instance/attributes/service-credentials -H "Metadata-Flavor: Google">service-credentials.json
curl http://metadata/computeMetadata/v1/instance/attributes/vm1_launch_vm2 -H "Metadata-Flavor: Google">launch_vm2_inside.py
curl http://metadata/computeMetadata/v1/instance/attributes/vm2_startup_script -H "Metadata-Flavor: Google">startup-script-remote.sh
export GOOGLE_CLOUD_PROJECT= "week5-project-401419"

sudo apt-get update
sudo apt-get install -y python3 python3-pip git

pip3 install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib
python3 ./launch_vm2_inside.py