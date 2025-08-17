"""
DigitalOcean Function for Docker Container Management
Manages Docker containers on separate VMs via SSH
- WAHA containers on WAHA VM
- User containers on User VM
"""

import os
import json
import random
import time
import paramiko
from typing import Dict, Optional
from datetime import datetime

def main(args):
    """
    Main function entry point for DO Function
    
    Actions:
    - create: Create user container (uses USER_VM)
    - create_waha: Create WAHA instance (uses WAHA_VM)
    - list_waha: List WAHA instances and their sessions (uses WAHA_VM)
    - stop/restart/delete: Works on both VMs based on container type
    """
    
    action = args.get('action', 'create')
    
    try:
        # Route to correct VM based on action
        if action == 'create':
            # Create user container on USER VM
            user_id = args.get('user_id')
            plan_type = args.get('plan_type', 'free')
            if not user_id:
                return {"statusCode": 400, "body": {"error": "user_id is required"}}
            
            result = create_user_container(user_id, plan_type, args)
            
        elif action == 'create_waha':
            # Create WAHA instance on WAHA VM
            result = create_waha_instance(args)
            
        elif action == 'list_waha':
            # List WAHA instances and available capacity
            result = list_waha_instances()
            
        elif action == 'find_available_waha':
            # Find WAHA instance with available capacity
            sessions_needed = args.get('sessions_needed', 1)
            result = find_available_waha_instance(sessions_needed)
            
        elif action in ['stop', 'restart', 'delete']:
            # These work on both VMs - determine by container name
            container_name = args.get('container_name')
            if not container_name:
                return {"statusCode": 400, "body": {"error": "container_name is required"}}
            
            if 'waha' in container_name:
                result = manage_waha_container(action, container_name)
            else:
                result = manage_user_container(action, container_name)
        else:
            return {
                "statusCode": 400,
                "body": {"error": f"Unknown action: {action}"}
            }
        
        return {
            "statusCode": 200,
            "body": result
        }
        
    except Exception as e:
        return {
            "statusCode": 500,
            "body": {"error": str(e), "type": "function_error"}
        }

def get_ssh_client(vm_type: str):
    """
    Create SSH client for specific VM
    vm_type: 'waha' or 'user'
    """
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    if vm_type == 'waha':
        # WAHA VM credentials
        host = os.environ.get('WAHA_VM_IP')
        ssh_user = os.environ.get('WAHA_SSH_USER', 'root')
        ssh_password = os.environ.get('WAHA_SSH_PASSWORD')
        ssh_key_path = os.environ.get('WAHA_SSH_KEY_PATH')
    else:
        # User containers VM credentials
        host = os.environ.get('USER_VM_IP')
        ssh_user = os.environ.get('USER_SSH_USER', 'root')
        ssh_password = os.environ.get('USER_SSH_PASSWORD')
        ssh_key_path = os.environ.get('USER_SSH_KEY_PATH')
    
    if not host:
        raise Exception(f"{vm_type.upper()}_VM_IP not configured")
    
    # Connect with key or password
    try:
        if ssh_key_path and os.path.exists(ssh_key_path):
            ssh.connect(host, username=ssh_user, key_filename=ssh_key_path, timeout=10)
        elif ssh_password:
            ssh.connect(host, username=ssh_user, password=ssh_password, timeout=10, look_for_keys=False, allow_agent=False)
        else:
            raise Exception(f"No SSH credentials for {vm_type} VM")
    except Exception as e:
        raise Exception(f"SSH connection failed to {vm_type} VM ({host}): {str(e)}")
    
    return ssh

def find_available_port(ssh, start_port: int, end_port: int) -> int:
    """Find an available port in the given range"""
    for _ in range(100):
        port = random.randint(start_port, end_port)
        
        # Check if port is in use
        stdin, stdout, stderr = ssh.exec_command(f"ss -tuln | grep :{port}")
        if not stdout.read():
            return port
    
    raise Exception(f"No available ports in range {start_port}-{end_port}")

# ============= USER CONTAINER FUNCTIONS (User VM) =============

def create_user_container(user_id: str, plan_type: str, args: Dict) -> Dict:
    """Create user container with 3 services on USER VM"""
    
    ssh = get_ssh_client('user')
    
    try:
        # Allocate ports from different ranges
        app_port = find_available_port(ssh, 40000, 50000)      # API: 40k-50k
        warmer_port = find_available_port(ssh, 20000, 30000)   # Warmer: 20k-30k
        campaign_port = find_available_port(ssh, 30000, 40000) # Campaign: 30k-40k
        
        container_name = f"cuwhapp-user-{user_id[:8]}-{app_port}"
        
        # Environment variables
        env_vars = args.get('environment', {})
        env_string = ' '.join([f'-e {k}={v}' for k, v in env_vars.items() if v])
        
        # Restart policy based on plan
        restart_policy = 'unless-stopped' if plan_type != 'free' else 'no'
        
        # Create network if doesn't exist
        ssh.exec_command("docker network create cuwhapp-network 2>/dev/null")
        
        # Build Docker command
        docker_cmd = f"""
        docker run -d \
            --name {container_name} \
            -p {app_port}:8000 \
            -p {warmer_port}:20000 \
            -p {campaign_port}:30000 \
            -e USER_ID={user_id} \
            -e PLAN_TYPE={plan_type} \
            -e API_PORT=8000 \
            -e WARMER_PORT=20000 \
            -e CAMPAIGN_PORT=30000 \
            {env_string} \
            --network cuwhapp-network \
            --restart {restart_policy} \
            cuwhapp/multi-service:latest
        """
        
        # Execute Docker command
        stdin, stdout, stderr = ssh.exec_command(docker_cmd)
        container_id = stdout.read().decode().strip()
        error = stderr.read().decode()
        
        if error and "Error" in error:
            raise Exception(f"Docker error: {error}")
        
        # Wait and verify
        time.sleep(3)
        stdin, stdout, stderr = ssh.exec_command(f"docker ps --filter name={container_name} --format '{{{{.Status}}}}'")
        status = stdout.read().decode().strip()
        
        if "Up" not in status:
            raise Exception(f"Container failed to start: {status}")
        
        # Get VM IP for URLs
        user_vm_ip = os.environ.get('USER_VM_IP')
        
        return {
            'success': True,
            'container': {
                'id': container_id[:12],
                'name': container_name,
                'vm': 'user',
                'urls': {
                    'api': f"http://{user_vm_ip}:{app_port}",
                    'warmer': f"http://{user_vm_ip}:{warmer_port}",
                    'campaign': f"http://{user_vm_ip}:{campaign_port}"
                }
            },
            'message': f"User container created for {user_id}"
        }
        
    finally:
        ssh.close()

def manage_user_container(action: str, container_name: str) -> Dict:
    """Manage user container (stop/restart/delete) on USER VM"""
    
    ssh = get_ssh_client('user')
    
    try:
        if action == 'stop':
            ssh.exec_command(f"docker stop {container_name}")
            message = f"Container {container_name} stopped"
        elif action == 'restart':
            ssh.exec_command(f"docker restart {container_name}")
            message = f"Container {container_name} restarted"
        elif action == 'delete':
            ssh.exec_command(f"docker stop {container_name}")
            time.sleep(2)
            ssh.exec_command(f"docker rm {container_name}")
            message = f"Container {container_name} deleted"
        
        return {'success': True, 'message': message}
        
    finally:
        ssh.close()

# ============= WAHA CONTAINER FUNCTIONS (WAHA VM) =============

def create_waha_instance(args: Dict) -> Dict:
    """Create new WAHA instance on WAHA VM"""
    
    ssh = get_ssh_client('waha')
    
    try:
        # Find next available port
        port = find_available_port(ssh, 4500, 5500)
        instance_id = port - 4500 + 1
        container_name = f"cuwhapp-waha-{instance_id}"
        
        max_sessions = args.get('max_sessions', 100)
        
        # Create network if doesn't exist
        ssh.exec_command("docker network create cuwhapp-network 2>/dev/null")
        
        # Build Docker command for WAHA
        docker_cmd = f"""
        docker run -d \
            --name {container_name} \
            -p {port}:3000 \
            -e WAHA_PRINT_QR=true \
            -e WAHA_LOG_LEVEL=info \
            -e WAHA_SESSION_STORE_ENABLED=true \
            -e WAHA_SESSION_STORE_PATH=/app/sessions \
            -e WAHA_FILES_MIMETYPES=audio,image,video,document \
            -e WAHA_FILES_LIFETIME=180 \
            -e WAHA_MAX_SESSIONS={max_sessions} \
            -v waha_sessions_{instance_id}:/app/sessions \
            -v waha_files_{instance_id}:/app/files \
            --network cuwhapp-network \
            --restart unless-stopped \
            devlikeapro/waha-plus:latest
        """
        
        # Execute Docker command
        stdin, stdout, stderr = ssh.exec_command(docker_cmd)
        container_id = stdout.read().decode().strip()
        error = stderr.read().decode()
        
        if error and "Error" in error:
            raise Exception(f"Docker error: {error}")
        
        # Wait for WAHA to be ready
        time.sleep(5)
        
        # Test health endpoint
        stdin, stdout, stderr = ssh.exec_command(f"curl -s http://localhost:{port}/api/health")
        health = stdout.read().decode()
        
        # Get VM IP
        waha_vm_ip = os.environ.get('WAHA_VM_IP')
        
        return {
            'success': True,
            'instance': {
                'id': instance_id,
                'container_id': container_id[:12],
                'container_name': container_name,
                'port': port,
                'endpoint': f"http://{waha_vm_ip}:{port}",
                'max_sessions': max_sessions,
                'current_sessions': 0,
                'vm': 'waha'
            },
            'message': f"WAHA instance {instance_id} created on port {port}"
        }
        
    finally:
        ssh.close()

def list_waha_instances() -> Dict:
    """List all WAHA instances and their session counts"""
    
    ssh = get_ssh_client('waha')
    
    try:
        # Get all WAHA containers
        stdin, stdout, stderr = ssh.exec_command(
            "docker ps --filter 'name=cuwhapp-waha' --format '{{.Names}}:{{.Ports}}'"
        )
        containers = stdout.read().decode().strip().split('\n')
        
        instances = []
        total_capacity = 0
        total_used = 0
        
        for container in containers:
            if not container:
                continue
                
            parts = container.split(':')
            name = parts[0]
            # Extract port from format "0.0.0.0:4500->3000/tcp"
            port_info = parts[1] if len(parts) > 1 else ""
            port = port_info.split('->')[0].split(':')[-1] if '->' in port_info else None
            
            if port:
                # Get session count from WAHA API
                stdin, stdout, stderr = ssh.exec_command(
                    f"curl -s http://localhost:{port}/api/sessions | python3 -c 'import sys, json; data=json.load(sys.stdin); print(len(data) if isinstance(data, list) else 0)'"
                )
                session_count = int(stdout.read().decode().strip() or 0)
                
                instances.append({
                    'name': name,
                    'port': int(port),
                    'sessions': session_count,
                    'capacity': 100,  # Default max
                    'available': 100 - session_count
                })
                
                total_capacity += 100
                total_used += session_count
        
        waha_vm_ip = os.environ.get('WAHA_VM_IP')
        
        return {
            'success': True,
            'instances': instances,
            'summary': {
                'total_instances': len(instances),
                'total_capacity': total_capacity,
                'total_used': total_used,
                'total_available': total_capacity - total_used,
                'vm_ip': waha_vm_ip
            }
        }
        
    finally:
        ssh.close()

def find_available_waha_instance(sessions_needed: int = 1) -> Dict:
    """Find WAHA instance with enough available capacity"""
    
    # Get all instances
    result = list_waha_instances()
    
    if not result['success']:
        return result
    
    # Find instance with enough space (leaving 5 session buffer)
    for instance in result['instances']:
        if instance['available'] >= sessions_needed + 5:
            waha_vm_ip = os.environ.get('WAHA_VM_IP')
            return {
                'success': True,
                'instance': {
                    'name': instance['name'],
                    'port': instance['port'],
                    'endpoint': f"http://{waha_vm_ip}:{instance['port']}",
                    'available_sessions': instance['available'],
                    'current_sessions': instance['sessions']
                }
            }
    
    # No available instance, trigger creation
    return {
        'success': False,
        'message': 'No available WAHA instance with enough capacity',
        'action_needed': 'create_waha',
        'reason': f'Need {sessions_needed} sessions but no instance has enough space'
    }

def manage_waha_container(action: str, container_name: str) -> Dict:
    """Manage WAHA container (stop/restart/delete) on WAHA VM"""
    
    ssh = get_ssh_client('waha')
    
    try:
        if action == 'stop':
            ssh.exec_command(f"docker stop {container_name}")
            message = f"WAHA container {container_name} stopped"
        elif action == 'restart':
            ssh.exec_command(f"docker restart {container_name}")
            message = f"WAHA container {container_name} restarted"
        elif action == 'delete':
            ssh.exec_command(f"docker stop {container_name}")
            time.sleep(2)
            ssh.exec_command(f"docker rm {container_name}")
            message = f"WAHA container {container_name} deleted"
        
        return {'success': True, 'message': message}
        
    finally:
        ssh.close()

# For local testing
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        test_args = {
            'action': sys.argv[1],
            'user_id': sys.argv[2] if len(sys.argv) > 2 else 'test-user',
            'plan_type': sys.argv[3] if len(sys.argv) > 3 else 'free'
        }
        result = main(test_args)
        print(json.dumps(result, indent=2))