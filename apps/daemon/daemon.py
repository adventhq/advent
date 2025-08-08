#!/usr/bin/env python3
"""
EC2 Daemon - Python Implementation
Listens for commands from API server and executes them safely
"""

import asyncio
import json
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path
import aiohttp
from aiohttp import web
import socket
import psutil
import hashlib
import hmac

# Configuration
CONFIG = {
    'port': 8081,
    'host': '0.0.0.0',
    'api_key': 'your-secret-api-key-change-this',  # Change this!
    'max_execution_time': 300,  # 5 minutes max execution time
    'allowed_commands': [
        'ls', 'ps', 'df', 'free', 'uptime', 'whoami', 'pwd',
        'systemctl', 'service', 'docker', 'git', 'curl', 'wget'
    ],  # Whitelist of allowed commands
    'log_file': './logs/ec2-daemon.log'
}

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(CONFIG['log_file']),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class CommandExecutor:
    """Handles safe command execution with timeouts and logging"""
    
    @staticmethod
    def validate_command(command):
        """Validate command against whitelist"""
        if not command or not isinstance(command, str):
            return False
        
        cmd_parts = command.strip().split()
        if not cmd_parts:
            return False
            
        base_command = cmd_parts[0]
        return base_command in CONFIG['allowed_commands']
    
    @staticmethod
    async def execute_command(command, timeout=None):
        """Execute command with timeout and return result"""
        if timeout is None:
            timeout = CONFIG['max_execution_time']
            
        try:
            logger.info(f"Executing command: {command}")
            
            # Create subprocess
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=1024*1024  # 1MB limit for output
            )
            
            # Wait for completion with timeout
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), 
                timeout=timeout
            )
            
            result = {
                'success': True,
                'return_code': process.returncode,
                'stdout': stdout.decode('utf-8', errors='replace'),
                'stderr': stderr.decode('utf-8', errors='replace'),
                'executed_at': datetime.now().isoformat()
            }
            
            logger.info(f"Command completed with return code: {process.returncode}")
            return result
            
        except asyncio.TimeoutError:
            logger.error(f"Command timed out: {command}")
            return {
                'success': False,
                'error': 'Command execution timed out',
                'executed_at': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Command execution failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'executed_at': datetime.now().isoformat()
            }

def verify_api_key(request):
    """Verify API key from request headers"""
    provided_key = request.headers.get('X-API-Key')
    if not provided_key:
        return False
    
    expected_key = CONFIG['api_key']
    # Use constant-time comparison to prevent timing attacks
    return hmac.compare_digest(provided_key, expected_key)

def get_system_info():
    """Get basic system information"""
    try:
        return {
            'hostname': socket.gethostname(),
            'cpu_count': psutil.cpu_count(),
            'memory_total': psutil.virtual_memory().total,
            'disk_usage': {
                'total': psutil.disk_usage('/').total,
                'used': psutil.disk_usage('/').used,
                'free': psutil.disk_usage('/').free
            },
            'uptime': datetime.now().isoformat(),
            'load_average': psutil.getloadavg() if hasattr(psutil, 'getloadavg') else None
        }
    except Exception as e:
        logger.error(f"Error getting system info: {e}")
        return {'error': str(e)}

# API Routes
async def health_check(request):
    """Health check endpoint"""
    return web.json_response({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'system_info': get_system_info()
    })

async def execute_command_endpoint(request):
    """Execute command endpoint"""
    # Verify API key
    if not verify_api_key(request):
        logger.warning("Unauthorized access attempt")
        return web.json_response(
            {'error': 'Unauthorized'}, 
            status=401
        )
    
    try:
        # Parse request
        data = await request.json()
        command = data.get('command')
        timeout = data.get('timeout', CONFIG['max_execution_time'])
        
        if not command:
            return web.json_response(
                {'error': 'Command is required'}, 
                status=400
            )
        
        # Validate command
        if not CommandExecutor.validate_command(command):
            logger.warning(f"Invalid command attempted: {command}")
            return web.json_response(
                {'error': 'Command not allowed'}, 
                status=403
            )
        
        # Execute command
        result = await CommandExecutor.execute_command(command, timeout)
        
        return web.json_response(result)
        
    except json.JSONDecodeError:
        return web.json_response(
            {'error': 'Invalid JSON'}, 
            status=400
        )
    except Exception as e:
        logger.error(f"Error in execute_command_endpoint: {e}")
        return web.json_response(
            {'error': 'Internal server error'}, 
            status=500
        )

async def get_system_status(request):
    """Get system status endpoint"""
    if not verify_api_key(request):
        return web.json_response({'error': 'Unauthorized'}, status=401)
    
    return web.json_response(get_system_info())

def create_app():
    """Create and configure the web application"""
    app = web.Application()
    
    # Add routes
    app.router.add_get('/health', health_check)
    app.router.add_post('/execute', execute_command_endpoint)
    app.router.add_get('/status', get_system_status)
    
    return app

async def main():
    """Main function to start the daemon"""
    logger.info("Starting EC2 Daemon...")
    
    # Create application
    app = create_app()
    
    # Start server
    runner = web.AppRunner(app)
    await runner.setup()
    
    site = web.TCPSite(
        runner, 
        CONFIG['host'], 
        CONFIG['port']
    )
    
    await site.start()
    
    logger.info(f"EC2 Daemon started on {CONFIG['host']}:{CONFIG['port']}")
    logger.info("Available endpoints:")
    logger.info("  GET  /health - Health check")
    logger.info("  POST /execute - Execute command")
    logger.info("  GET  /status - System status")
    
    # Keep running
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await runner.cleanup()

if __name__ == '__main__':
    # Ensure log directory exists
    Path(CONFIG['log_file']).parent.mkdir(parents=True, exist_ok=True)
    
    # Run the daemon
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Daemon stopped by user")
    except Exception as e:
        logger.error(f"Daemon crashed: {e}")
        sys.exit(1)