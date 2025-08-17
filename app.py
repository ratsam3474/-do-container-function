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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)