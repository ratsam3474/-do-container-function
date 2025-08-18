"""
Container management using Docker TCP API
External port = Internal port for all services
"""

import os
import json
import requests
import random
from typing import Dict, Optional
from datetime import datetime

def main(args):
    """
    Main function entry point
    Actions:
    - create: Create user container
    - create_waha: Create WAHA instance
    - list_waha: List WAHA instances
    - find_available_waha: Find WAHA with capacity
    """
    
    action = args.get('action', 'create')
    
    try:
        if action == 'create':
            user_id = args.get('user_id')
            plan_type = args.get('plan_type', 'free')
            if not user_id:
                return {"statusCode": 400, "body": {"error": "user_id is required"}}
            result = create_user_container(user_id, plan_type)
            
        elif action == 'create_waha':
            result = create_waha_instance(args)
            
        elif action == 'list_waha':
            result = list_waha_instances()
            
        elif action == 'find_available_waha':
            sessions_needed = args.get('sessions_needed', 1)
            result = find_available_waha_instance(sessions_needed)
            
        else:
            return {"statusCode": 400, "body": {"error": f"Unknown action: {action}"}}
        
        return {"statusCode": 200, "body": result}
        
    except Exception as e:
        return {"statusCode": 500, "body": {"error": str(e), "type": "docker_error"}}

def docker_request(vm_type: str, endpoint: str, method='GET', json_data=None):
    """Make request to Docker API on VM"""
    if vm_type == 'waha':
        base_url = f"http://{os.environ.get('WAHA_VM_IP', '10.128.0.3')}:2375"
    else:
        base_url = f"http://{os.environ.get('USER_VM_IP', '10.128.0.4')}:2375"
    
    url = f"{base_url}{endpoint}"
    
    if method == 'GET':
        response = requests.get(url, timeout=10)
    elif method == 'POST':
        response = requests.post(url, json=json_data, timeout=30)
    
    return response.json() if response.text else {}

def find_available_port(vm_type: str, start_port: int, end_port: int) -> int:
    """Find an available port by checking running containers"""
    containers = docker_request(vm_type, '/containers/json?all=true')
    
    used_ports = set()
    
    # Check container names for ports (since we include port in the name)
    for container in containers:
        names = container.get('Names', [])
        for name in names:
            if 'cuwhapp-user-' in name:
                # Extract port from container name (e.g., cuwhapp-user-xxx-40000)
                parts = name.split('-')
                if len(parts) > 0 and parts[-1].isdigit():
                    port = int(parts[-1])
                    # Add this port and neighboring ports (for warmer/campaign)
                    used_ports.add(port)
                    used_ports.add(port - 20000)  # warmer port
                    used_ports.add(port - 10000)  # campaign port
        
        # Also check actual port bindings
        for port_info in container.get('Ports', []):
            if 'PublicPort' in port_info:
                used_ports.add(port_info['PublicPort'])
    
    # Find first available port
    for port in range(start_port, end_port + 1):
        if port not in used_ports:
            return port
    
    # If all sequential ports used, try random
    for _ in range(100):
        port = random.randint(start_port, end_port)
        if port not in used_ports:
            return port
    
    raise Exception(f"No available ports in range {start_port}-{end_port}")

def create_user_container(user_id: str, plan_type: str) -> Dict:
    """Create user container via Docker API"""
    
    # Allocate ports from correct ranges
    app_port = find_available_port('user', 40000, 50000)
    warmer_port = find_available_port('user', 20000, 30000)
    campaign_port = find_available_port('user', 30000, 40000)
    
    container_name = f"cuwhapp-user-{user_id[:20]}-{app_port}"
    
    # Create container config - ports must match inside and outside
    config = {
        "Image": "cuwhapp-multi-service:latest",
        "Hostname": container_name,
        "Env": [
            f"USER_ID={user_id}",
            f"PLAN_TYPE={plan_type}",
            f"API_PORT={app_port}",
            f"WARMER_PORT={warmer_port}",
            f"CAMPAIGN_PORT={campaign_port}"
        ],
        "ExposedPorts": {
            f"{app_port}/tcp": {},
            f"{warmer_port}/tcp": {},
            f"{campaign_port}/tcp": {}
        },
        "HostConfig": {
            "PortBindings": {
                f"{app_port}/tcp": [{"HostPort": str(app_port)}],
                f"{warmer_port}/tcp": [{"HostPort": str(warmer_port)}],
                f"{campaign_port}/tcp": [{"HostPort": str(campaign_port)}]
            },
            "NetworkMode": "host",  # Use host network for same port inside/outside
            "RestartPolicy": {"Name": "unless-stopped" if plan_type != 'free' else "no"}
        }
    }
    
    # Create container
    result = docker_request('user', f'/containers/create?name={container_name}', 'POST', config)
    
    if 'Id' in result:
        # Start container
        docker_request('user', f'/containers/{result["Id"]}/start', 'POST')
        
        user_vm_ip = os.environ.get('USER_VM_IP', '10.128.0.4')
        
        return {
            'success': True,
            'container': {
                'id': result['Id'][:12],
                'name': container_name,
                'urls': {
                    'api': f"http://{user_vm_ip}:{app_port}",
                    'warmer': f"http://{user_vm_ip}:{warmer_port}",
                    'campaign': f"http://{user_vm_ip}:{campaign_port}"
                }
            },
            'message': f"Container created with ports {app_port}, {warmer_port}, {campaign_port}"
        }
    else:
        return {'success': False, 'error': result.get('message', 'Failed to create container')}

def create_waha_instance(args: Dict) -> Dict:
    """Create WAHA instance via Docker API"""
    
    # Find available port starting from 4500
    port = find_available_port('waha', 4500, 5500)
    instance_id = port - 4500 + 1
    container_name = f"cuwhapp-waha-{instance_id}"
    max_sessions = args.get('max_sessions', 100)
    
    # Pull image first if needed
    docker_request('waha', '/images/create?fromImage=devlikeapro/waha-plus:latest', 'POST')
    
    # Create container config - port 4500+ outside, 3000 inside
    config = {
        "Image": "devlikeapro/waha-plus:latest",
        "Hostname": container_name,
        "Env": [
            "WAHA_PRINT_QR=true",
            "WAHA_LOG_LEVEL=info",
            "WAHA_SESSION_STORE_ENABLED=true",
            "WAHA_SESSION_STORE_PATH=/app/sessions",
            "WAHA_FILES_MIMETYPES=audio,image,video,document",
            "WAHA_FILES_LIFETIME=180",
            f"WAHA_MAX_SESSIONS={max_sessions}"
        ],
        "ExposedPorts": {"3000/tcp": {}},
        "HostConfig": {
            "PortBindings": {"3000/tcp": [{"HostPort": str(port)}]},
            "RestartPolicy": {"Name": "unless-stopped"},
            "Binds": [
                f"waha_sessions_{instance_id}:/app/sessions",
                f"waha_files_{instance_id}:/app/files"
            ]
        }
    }
    
    # Create container
    result = docker_request('waha', f'/containers/create?name={container_name}', 'POST', config)
    
    if 'Id' in result:
        # Start container
        docker_request('waha', f'/containers/{result["Id"]}/start', 'POST')
        
        waha_vm_ip = os.environ.get('WAHA_VM_IP', '10.128.0.3')
        
        return {
            'success': True,
            'instance': {
                'id': instance_id,
                'container_id': result['Id'][:12],
                'container_name': container_name,
                'port': port,
                'endpoint': f"http://{waha_vm_ip}:{port}",
                'max_sessions': max_sessions
            },
            'message': f"WAHA instance created on port {port}"
        }
    else:
        return {'success': False, 'error': result.get('message', 'Failed to create WAHA')}

def list_waha_instances() -> Dict:
    """List all WAHA instances"""
    
    # Get containers from Docker API
    containers = docker_request('waha', '/containers/json?all=true')
    
    instances = []
    for container in containers:
        name = container.get('Names', [''])[0].strip('/')
        if 'cuwhapp-waha' in name:
            # Extract port from container info
            ports = container.get('Ports', [])
            port = None
            for p in ports:
                if p.get('PrivatePort') == 3000:
                    port = p.get('PublicPort')
                    break
            
            instances.append({
                'name': name,
                'id': container['Id'][:12],
                'status': container['State'],
                'port': port
            })
    
    waha_vm_ip = os.environ.get('WAHA_VM_IP', '10.128.0.3')
    
    return {
        'success': True,
        'instances': instances,
        'vm_ip': waha_vm_ip,
        'total': len(instances)
    }

def find_available_waha_instance(sessions_needed: int = 1) -> Dict:
    """Find WAHA instance with capacity"""
    
    result = list_waha_instances()
    
    if result['instances']:
        # Return first running instance with a port
        for instance in result['instances']:
            if instance['status'] == 'running' and instance.get('port'):
                waha_vm_ip = os.environ.get('WAHA_VM_IP', '10.128.0.3')
                return {
                    'success': True,
                    'instance': {
                        'name': instance['name'],
                        'port': instance['port'],
                        'endpoint': f"http://{waha_vm_ip}:{instance['port']}"
                    }
                }
    
    # No instance available, need to create one
    return {
        'success': False,
        'message': 'No WAHA instances available',
        'action_needed': 'create_waha'
    }