#!/usr/bin/env python3
"""
Test SSH connection to VMs directly
"""
import paramiko
import sys

def test_ssh(host, user, password):
    """Test SSH connection"""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print(f"Connecting to {host} as {user}...")
        ssh.connect(host, username=user, password=password, timeout=10, look_for_keys=False, allow_agent=False)
        print(f"✓ Connected successfully to {host}")
        
        # Test command
        stdin, stdout, stderr = ssh.exec_command("echo 'Connection successful' && hostname")
        result = stdout.read().decode()
        print(f"✓ Command output: {result}")
        
        ssh.close()
        return True
    except Exception as e:
        print(f"✗ Failed to connect to {host}: {e}")
        return False

if __name__ == "__main__":
    # Test WAHA VM
    print("Testing WAHA VM:")
    test_ssh("34.133.143.67", "root", "$Oden3474")
    
    print("\nTesting User VM:")
    test_ssh("34.173.85.56", "root", "$Oden3474")