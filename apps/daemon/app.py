#!/usr/bin/env python3
"""
API Server - Sends commands to EC2 daemons
Manages multiple EC2 instances and provides a unified API
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from typing import Dict, List, Optional
import aiohttp
from aiohttp import web, ClientSession, ClientTimeout
import sqlite3
from contextlib import asynccontextmanager
import uuid

# Configuration
CONFIG = {
    'port': 8080,
    'host': '0.0.0.0',
    'admin_api_key': 'admin-secret-key-change-this',  # Change this!
    'daemon_api_key': 'your-secret-api-key-change-this',  # Must match daemon API key
    'db_path': 'ec2_instances.db',
    'request_timeout': 30,
    'command_timeout': 300,
    'log_file': './logs/ec2-api-server.log'
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

class DatabaseManager:
    """Manages EC2 instance database"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize database tables"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS ec2_instances (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    host TEXT NOT NULL,
                    port INTEGER NOT NULL,
                    status TEXT DEFAULT 'unknown',
                    last_seen TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS command_logs (
                    id TEXT PRIMARY KEY,
                    instance_id TEXT,
                    command TEXT NOT NULL,
                    result TEXT,
                    success BOOLEAN,
                    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (instance_id) REFERENCES ec2_instances (id)
                )
            ''')
            conn.commit()
    
    def add_instance(self, name: str, host: str, port: int, metadata: Dict = None):
        """Add new EC2 instance"""
        instance_id = str(uuid.uuid4())
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO ec2_instances (id, name, host, port, metadata)
                VALUES (?, ?, ?, ?, ?)
            ''', (instance_id, name, host, port, json.dumps(metadata or {})))
            conn.commit()
        return instance_id
    
    def get_instances(self) -> List[Dict]:
        """Get all instances"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('SELECT * FROM ec2_instances ORDER BY name')
            return [dict(row) for row in cursor.fetchall()]
    
    def get_instance(self, instance_id: str) -> Optional[Dict]:
        """Get specific instance"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('SELECT * FROM ec2_instances WHERE id = ?', (instance_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def update_instance_status(self, instance_id: str, status: str):
        """Update instance status"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                UPDATE ec2_instances 
                SET status = ?, last_seen = CURRENT_TIMESTAMP 
                WHERE id = ?
            ''', (status, instance_id))
            conn.commit()
    
    def delete_instance(self, instance_id: str):
        """Delete instance"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('DELETE FROM ec2_instances WHERE id = ?', (instance_id,))
            conn.commit()
    
    def log_command(self, instance_id: str, command: str, result: Dict, success: bool):
        """Log command execution"""
        log_id = str(uuid.uuid4())
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO command_logs (id, instance_id, command, result, success)
                VALUES (?, ?, ?, ?, ?)
            ''', (log_id, instance_id, command, json.dumps(result), success))
            conn.commit()
        return log_id

class EC2DaemonClient:
    """Client for communicating with EC2 daemons"""
    
    def __init__(self, daemon_api_key: str):
        self.daemon_api_key = daemon_api_key
        self.timeout = ClientTimeout(total=CONFIG['request_timeout'])
    
    async def health_check(self, host: str, port: int) -> Dict:
        """Check daemon health"""
        url = f"http://{host}:{port}/health"
        try:
            async with ClientSession(timeout=self.timeout) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        return {'error': f'HTTP {response.status}'}
        except Exception as e:
            return {'error': str(e)}
    
    async def execute_command(self, host: str, port: int, command: str, timeout: int = None) -> Dict:
        """Execute command on daemon"""
        url = f"http://{host}:{port}/execute"
        headers = {'X-API-Key': self.daemon_api_key, 'Content-Type': 'application/json'}
        payload = {
            'command': command,
            'timeout': timeout or CONFIG['command_timeout']
        }
        
        try:
            async with ClientSession(timeout=self.timeout) as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    result = await response.json()
                    result['http_status'] = response.status
                    return result
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    async def get_status(self, host: str, port: int) -> Dict:
        """Get daemon system status"""
        url = f"http://{host}:{port}/status"
        headers = {'X-API-Key': self.daemon_api_key}
        
        try:
            async with ClientSession(timeout=self.timeout) as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        return {'error': f'HTTP {response.status}'}
        except Exception as e:
            return {'error': str(e)}

# Global instances
db = DatabaseManager(CONFIG['db_path'])
daemon_client = EC2DaemonClient(CONFIG['daemon_api_key'])

def verify_admin_key(request):
    """Verify admin API key"""
    provided_key = request.headers.get('X-Admin-Key')
    if not provided_key:
        return False
    return provided_key == CONFIG['admin_api_key']

# API Routes
async def add_instance_endpoint(request):
    """Add new EC2 instance"""
    if not verify_admin_key(request):
        return web.json_response({'error': 'Unauthorized'}, status=401)
    
    try:
        data = await request.json()
        name = data.get('name')
        host = data.get('host')
        port = data.get('port', 8081)
        metadata = data.get('metadata', {})
        
        if not name or not host:
            return web.json_response({'error': 'Name and host are required'}, status=400)
        
        instance_id = db.add_instance(name, host, port, metadata)
        
        # Test connection
        health = await daemon_client.health_check(host, port)
        if 'error' not in health:
            db.update_instance_status(instance_id, 'healthy')
        else:
            db.update_instance_status(instance_id, 'unhealthy')
        
        return web.json_response({
            'instance_id': instance_id,
            'name': name,
            'host': host,
            'port': port,
            'health_check': health
        })
        
    except Exception as e:
        logger.error(f"Error adding instance: {e}")
        return web.json_response({'error': str(e)}, status=500)

async def list_instances_endpoint(request):
    """List all EC2 instances"""
    if not verify_admin_key(request):
        return web.json_response({'error': 'Unauthorized'}, status=401)
    
    instances = db.get_instances()
    for instance in instances:
        if instance['metadata']:
            instance['metadata'] = json.loads(instance['metadata'])
    
    return web.json_response({'instances': instances})

async def get_instance_endpoint(request):
    """Get specific instance details"""
    if not verify_admin_key(request):
        return web.json_response({'error': 'Unauthorized'}, status=401)
    
    instance_id = request.match_info['instance_id']
    instance = db.get_instance(instance_id)
    
    if not instance:
        return web.json_response({'error': 'Instance not found'}, status=404)
    
    if instance['metadata']:
        instance['metadata'] = json.loads(instance['metadata'])
    
    return web.json_response(instance)

async def delete_instance_endpoint(request):
    """Delete EC2 instance"""
    if not verify_admin_key(request):
        return web.json_response({'error': 'Unauthorized'}, status=401)
    
    instance_id = request.match_info['instance_id']
    instance = db.get_instance(instance_id)
    
    if not instance:
        return web.json_response({'error': 'Instance not found'}, status=404)
    
    db.delete_instance(instance_id)
    return web.json_response({'message': 'Instance deleted successfully'})

async def execute_command_endpoint(request):
    """Execute command on specific instance"""
    if not verify_admin_key(request):
        return web.json_response({'error': 'Unauthorized'}, status=401)
    
    instance_id = request.match_info['instance_id']
    instance = db.get_instance(instance_id)
    
    if not instance:
        return web.json_response({'error': 'Instance not found'}, status=404)
    
    try:
        data = await request.json()
        command = data.get('command')
        timeout = data.get('timeout')
        
        if not command:
            return web.json_response({'error': 'Command is required'}, status=400)
        
        # Execute command on daemon
        result = await daemon_client.execute_command(
            instance['host'], 
            instance['port'], 
            command, 
            timeout
        )
        
        # Update instance status based on result
        if result.get('success') is not None:
            status = 'healthy' if result.get('success') or result.get('http_status') == 200 else 'unhealthy'
            db.update_instance_status(instance_id, status)
        
        # Log command execution
        db.log_command(instance_id, command, result, result.get('success', False))
        
        return web.json_response({
            'instance_id': instance_id,
            'instance_name': instance['name'],
            'command': command,
            'result': result
        })
        
    except Exception as e:
        logger.error(f"Error executing command: {e}")
        return web.json_response({'error': str(e)}, status=500)

async def execute_command_all_endpoint(request):
    """Execute command on all instances"""
    if not verify_admin_key(request):
        return web.json_response({'error': 'Unauthorized'}, status=401)
    
    try:
        data = await request.json()
        command = data.get('command')
        timeout = data.get('timeout')
        
        if not command:
            return web.json_response({'error': 'Command is required'}, status=400)
        
        instances = db.get_instances()
        results = []
        
        # Execute command on all instances concurrently
        tasks = []
        for instance in instances:
            task = daemon_client.execute_command(
                instance['host'], 
                instance['port'], 
                command, 
                timeout
            )
            tasks.append((instance, task))
        
        # Wait for all tasks to complete
        for instance, task in tasks:
            try:
                result = await task
                
                # Update instance status
                if result.get('success') is not None:
                    status = 'healthy' if result.get('success') or result.get('http_status') == 200 else 'unhealthy'
                    db.update_instance_status(instance['id'], status)
                
                # Log command execution
                db.log_command(instance['id'], command, result, result.get('success', False))
                
                results.append({
                    'instance_id': instance['id'],
                    'instance_name': instance['name'],
                    'host': instance['host'],
                    'result': result
                })
                
            except Exception as e:
                logger.error(f"Error executing command on {instance['name']}: {e}")
                results.append({
                    'instance_id': instance['id'],
                    'instance_name': instance['name'],
                    'host': instance['host'],
                    'result': {'success': False, 'error': str(e)}
                })
        
        return web.json_response({
            'command': command,
            'total_instances': len(instances),
            'results': results
        })
        
    except Exception as e:
        logger.error(f"Error executing command on all instances: {e}")
        return web.json_response({'error': str(e)}, status=500)

async def health_check_endpoint(request):
    """Check health of specific instance"""
    if not verify_admin_key(request):
        return web.json_response({'error': 'Unauthorized'}, status=401)
    
    instance_id = request.match_info['instance_id']
    instance = db.get_instance(instance_id)
    
    if not instance:
        return web.json_response({'error': 'Instance not found'}, status=404)
    
    health = await daemon_client.health_check(instance['host'], instance['port'])
    
    # Update status based on health check
    status = 'healthy' if 'error' not in health else 'unhealthy'
    db.update_instance_status(instance_id, status)
    
    return web.json_response({
        'instance_id': instance_id,
        'instance_name': instance['name'],
        'health': health,
        'status': status
    })

async def health_check_all_endpoint(request):
    """Check health of all instances"""
    if not verify_admin_key(request):
        return web.json_response({'error': 'Unauthorized'}, status=401)
    
    instances = db.get_instances()
    results = []
    
    # Health check all instances concurrently
    tasks = []
    for instance in instances:
        task = daemon_client.health_check(instance['host'], instance['port'])
        tasks.append((instance, task))
    
    for instance, task in tasks:
        try:
            health = await task
            status = 'healthy' if 'error' not in health else 'unhealthy'
            db.update_instance_status(instance['id'], status)
            
            results.append({
                'instance_id': instance['id'],
                'instance_name': instance['name'],
                'host': instance['host'],
                'health': health,
                'status': status
            })
            
        except Exception as e:
            logger.error(f"Error checking health for {instance['name']}: {e}")
            results.append({
                'instance_id': instance['id'],
                'instance_name': instance['name'],
                'host': instance['host'],
                'health': {'error': str(e)},
                'status': 'unhealthy'
            })
    
    return web.json_response({
        'total_instances': len(instances),
        'results': results
    })

async def get_instance_status_endpoint(request):
    """Get system status of specific instance"""
    if not verify_admin_key(request):
        return web.json_response({'error': 'Unauthorized'}, status=401)
    
    instance_id = request.match_info['instance_id']
    instance = db.get_instance(instance_id)
    
    if not instance:
        return web.json_response({'error': 'Instance not found'}, status=404)
    
    status = await daemon_client.get_status(instance['host'], instance['port'])
    
    return web.json_response({
        'instance_id': instance_id,
        'instance_name': instance['name'],
        'system_status': status
    })

async def api_status_endpoint(request):
    """API server status endpoint"""
    return web.json_response({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0',
        'total_instances': len(db.get_instances())
    })

def create_app():
    """Create and configure the web application"""
    app = web.Application()
    
    # Instance management routes
    app.router.add_post('/instances', add_instance_endpoint)
    app.router.add_get('/instances', list_instances_endpoint)
    app.router.add_get('/instances/{instance_id}', get_instance_endpoint)
    app.router.add_delete('/instances/{instance_id}', delete_instance_endpoint)
    
    # Command execution routes
    app.router.add_post('/instances/{instance_id}/execute', execute_command_endpoint)
    app.router.add_post('/instances/execute-all', execute_command_all_endpoint)
    
    # Health and status routes
    app.router.add_get('/instances/{instance_id}/health', health_check_endpoint)
    app.router.add_get('/instances/health-all', health_check_all_endpoint)
    app.router.add_get('/instances/{instance_id}/status', get_instance_status_endpoint)
    app.router.add_get('/status', api_status_endpoint)
    
    return app

async def main():
    """Main function to start the API server"""
    logger.info("Starting EC2 API Server...")
    
    # Create application
    app = create_app()
    
    # Start server
    runner = web.AppRunner(app)
    await runner.setup()
    
    site = web.TCPSite(runner, CONFIG['host'], CONFIG['port'])
    await site.start()
    
    logger.info(f"EC2 API Server started on {CONFIG['host']}:{CONFIG['port']}")
    logger.info("Available endpoints:")
    logger.info("  POST /instances - Add new instance")
    logger.info("  GET  /instances - List all instances")
    logger.info("  GET  /instances/{id} - Get instance details")
    logger.info("  DELETE /instances/{id} - Delete instance")
    logger.info("  POST /instances/{id}/execute - Execute command on instance")
    logger.info("  POST /instances/execute-all - Execute command on all instances")
    logger.info("  GET  /instances/{id}/health - Health check instance")
    logger.info("  GET  /instances/health-all - Health check all instances")
    logger.info("  GET  /instances/{id}/status - Get instance system status")
    logger.info("  GET  /status - API server status")
    
    # Keep running
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await runner.cleanup()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("API Server stopped by user")
    except Exception as e:
        logger.error(f"API Server crashed: {e}")
        sys.exit(1)