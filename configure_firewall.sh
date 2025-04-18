#!/bin/bash
# Script to configure firewall rules for the STT YouTube server

echo "=== Configuring Firewall Rules for STT YouTube Server ==="
echo "This script will create firewall rules to allow HTTP traffic to your VM"

# Set VM parameters
VM_NAME="stt-yt-gpu"
ZONE="asia-northeast3-c"
PROJECT_ID=$(gcloud config get-value project)

echo "VM Name: $VM_NAME"
echo "Zone: $ZONE"
echo "Project: $PROJECT_ID"

# Check if the VM exists
echo "Checking if VM exists..."
VM_INFO=$(gcloud compute instances describe $VM_NAME --zone=$ZONE --format=json 2>/dev/null)
if [ $? -ne 0 ]; then
    echo "❌ VM not found. Please check the VM name and zone."
    exit 1
fi

echo "✅ VM found."

# Add network tag to VM if not already present
echo "Checking network tags on VM..."
TAGS=$(echo $VM_INFO | grep -o '"tags":.*"items":\[.*\]' | grep -o '"http-server"')

if [ -z "$TAGS" ]; then
    echo "Adding http-server tag to VM..."
    gcloud compute instances add-tags $VM_NAME \
        --tags=http-server,https-server \
        --zone=$ZONE
    echo "✅ Tags added to VM."
else
    echo "✅ http-server tag already present."
fi

# Create firewall rules if they don't exist
echo "Checking for existing firewall rules..."

# Check for HTTP rule
HTTP_RULE=$(gcloud compute firewall-rules list --filter="name=allow-http" --format="get(name)" 2>/dev/null)
if [ -z "$HTTP_RULE" ]; then
    echo "Creating allow-http firewall rule..."
    gcloud compute firewall-rules create allow-http \
        --direction=INGRESS \
        --priority=1000 \
        --network=default \
        --action=ALLOW \
        --rules=tcp:80 \
        --source-ranges=0.0.0.0/0 \
        --target-tags=http-server
    echo "✅ HTTP firewall rule created."
else
    echo "✅ HTTP firewall rule already exists."
fi

# Check for HTTPS rule
HTTPS_RULE=$(gcloud compute firewall-rules list --filter="name=allow-https" --format="get(name)" 2>/dev/null)
if [ -z "$HTTPS_RULE" ]; then
    echo "Creating allow-https firewall rule..."
    gcloud compute firewall-rules create allow-https \
        --direction=INGRESS \
        --priority=1000 \
        --network=default \
        --action=ALLOW \
        --rules=tcp:443 \
        --source-ranges=0.0.0.0/0 \
        --target-tags=https-server
    echo "✅ HTTPS firewall rule created."
else
    echo "✅ HTTPS firewall rule already exists."
fi

# Get VM IP
VM_IP=$(gcloud compute instances describe $VM_NAME --zone=$ZONE --format="get(networkInterfaces[0].accessConfigs[0].natIP)")
echo "VM IP: $VM_IP"

# SSH into the VM to check the Docker container status
echo -e "\nChecking Docker container status on VM..."
echo "Run the following command to check if the container is running:"
echo "gcloud compute ssh $VM_NAME --zone=$ZONE --command=\"sudo docker ps\""

# Provide commands to restart the container if needed
echo -e "\nIf the container is not running, you can restart it with:"
echo "gcloud compute ssh $VM_NAME --zone=$ZONE --command=\"sudo docker start stt-yt-container-new\""

# Provide commands to check the Docker logs
echo -e "\nTo check the Docker logs:"
echo "gcloud compute ssh $VM_NAME --zone=$ZONE --command=\"sudo docker logs stt-yt-container-new\""

echo -e "\nFirewall configuration complete! Try connecting to your server again."
echo "python setup_client.py --ip $VM_IP"