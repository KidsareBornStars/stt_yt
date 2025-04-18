import os
import sys
import argparse
import subprocess
import requests
import time

def get_vm_ip():
    """Try to get the VM IP address from Google Cloud SDK if installed."""
    try:
        result = subprocess.run(
            ["gcloud", "compute", "instances", "describe", "stt-yt-gpu-server", 
             "--zone=us-central1-a", "--format=get(networkInterfaces[0].accessConfigs[0].natIP)"],
            capture_output=True, text=True, check=True
        )
        ip = result.stdout.strip()
        if ip:
            return ip
    except Exception as e:
        print(f"Could not automatically get VM IP: {e}")
    
    return None

def test_server_connection(server_ip):
    """Test connection to the server."""
    try:
        response = requests.get(f"http://{server_ip}", timeout=5)
        if response.status_code == 200:
            print(f"✅ Successfully connected to server at {server_ip}")
            return True
        else:
            print(f"❌ Server responded with status code: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Could not connect to server: {e}")
        return False

def update_app_config(server_ip):
    """Update the app.py file with the server IP."""
    try:
        with open('app.py', 'r', encoding='utf-8') as file:
            content = file.read()
        
        # Replace the server IP in the code
        if 'YOUR_VM_IP_ADDRESS' in content:
            content = content.replace('YOUR_VM_IP_ADDRESS', server_ip)
            
            with open('app.py', 'w', encoding='utf-8') as file:
                file.write(content)
            
            print(f"✅ Updated app.py with server IP: {server_ip}")
            return True
        else:
            print("⚠️ Could not find placeholder in app.py to update server IP")
            return False
    except Exception as e:
        print(f"❌ Error updating app.py: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Setup client for STT YouTube App")
    parser.add_argument('--ip', help='Server IP address')
    args = parser.parse_args()
    
    # Get server IP from arguments, auto-detect, or prompt user
    server_ip = args.ip
    
    if not server_ip:
        # Try to auto-detect from Google Cloud SDK
        server_ip = get_vm_ip()
    
    if not server_ip:
        # Prompt user for IP address
        server_ip = input("Enter your GCP VM's public IP address: ")
    
    if not server_ip:
        print("❌ No server IP provided. Exiting.")
        return
    
    # Test connection to server
    print(f"Testing connection to server at {server_ip}...")
    if test_server_connection(server_ip):
        # Update app.py with server IP
        update_app_config(server_ip)
        
        # Setup environment variable
        print("\nYou can also set the SERVER_IP environment variable:")
        if os.name == 'nt':  # Windows
            print(f"set SERVER_IP={server_ip}")
        else:  # Unix/Linux/Mac
            print(f"export SERVER_IP={server_ip}")
        
        print("\n📱 Client setup complete! You can now run the app:")
        print("python app.py")
    else:
        print("\n❌ Could not connect to server. Please check:")
        print("  1. Is your VM running? Check in GCP console")
        print("  2. Is the server application running on the VM?")
        print("  3. Did you allow HTTP traffic to the VM (port 80)?")
        print("  4. Is the IP address correct?")

if __name__ == "__main__":
    main()