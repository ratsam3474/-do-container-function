"""
Web service wrapper for container management function
"""
from flask import Flask, request, jsonify
import os
from main import main as function_main

app = Flask(__name__)

@app.route('/', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy", 
        "service": "container-manager",
        "endpoints": {
            "POST /": "Execute function",
            "GET /": "Health check"
        }
    })

@app.route('/', methods=['POST'])
def execute_function():
    """Execute the container management function"""
    try:
        args = request.get_json() or {}
        result = function_main(args)
        return jsonify(result)
    except Exception as e:
        return jsonify({
            "statusCode": 500,
            "body": {"error": str(e)}
        }), 500

@app.route('/test-connection', methods=['GET'])
def test_connection():
    """Test connectivity to VMs"""
    import socket
    results = {}
    
    # Test WAHA VM
    waha_ip = os.environ.get('WAHA_VM_IP', 'not set')
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((waha_ip, 22))
        sock.close()
        results['waha_vm'] = {
            'ip': waha_ip,
            'port_22_reachable': result == 0,
            'status': 'reachable' if result == 0 else f'unreachable (error {result})'
        }
    except Exception as e:
        results['waha_vm'] = {'ip': waha_ip, 'error': str(e)}
    
    # Test User VM
    user_ip = os.environ.get('USER_VM_IP', 'not set')
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((user_ip, 22))
        sock.close()
        results['user_vm'] = {
            'ip': user_ip,
            'port_22_reachable': result == 0,
            'status': 'reachable' if result == 0 else f'unreachable (error {result})'
        }
    except Exception as e:
        results['user_vm'] = {'ip': user_ip, 'error': str(e)}
    
    return jsonify(results)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)