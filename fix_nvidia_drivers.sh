#!/bin/bash
# Script to properly install NVIDIA drivers and Docker with GPU support

echo "=== Checking current system status ==="
echo "Kernel version:"
uname -r

echo "=== Installing required packages ==="
sudo apt-get update
sudo apt-get install -y build-essential dkms linux-headers-$(uname -r)

echo "=== Installing NVIDIA drivers ==="
# Remove any existing NVIDIA installation
sudo apt-get purge -y nvidia*
sudo apt-get autoremove -y

# Install NVIDIA drivers using the package manager
sudo apt-get update
sudo apt-get install -y nvidia-driver-525

echo "=== Installing Docker ==="
# Remove existing Docker installations
sudo apt-get purge -y docker docker-engine docker.io containerd runc
sudo apt-get autoremove -y

# Install Docker
sudo apt-get update
sudo apt-get install -y apt-transport-https ca-certificates curl gnupg lsb-release
curl -fsSL https://download.docker.com/linux/debian/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io

echo "=== Installing NVIDIA Container Toolkit ==="
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit

# Configure Docker to use NVIDIA container toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

echo "=== Installation complete ==="
echo "Rebooting system to complete driver installation..."
echo "After reboot, run the command 'nvidia-smi' to verify that NVIDIA drivers are properly installed."
echo "Then rebuild and run your Docker container."
echo "System will reboot in 10 seconds. Press Ctrl+C to cancel."
sleep 10
sudo reboot