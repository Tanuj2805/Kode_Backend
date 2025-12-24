"""
WebSocket connection manager for real-time code execution
"""

from fastapi import WebSocket
from typing import Dict
import json
import logging
import asyncio

logger = logging.getLogger(__name__)

class ConnectionManager:
    """Manages WebSocket connections"""
    
    def __init__(self):
        # Store active connections: {connection_id: WebSocket}
        self.active_connections: Dict[str, WebSocket] = {}
        # Map job_id to connection_id: {job_id: connection_id}
        self.job_connections: Dict[str, str] = {}
    
    async def connect(self, connection_id: str, websocket: WebSocket):
        """Accept new WebSocket connection"""
        await websocket.accept()
        self.active_connections[connection_id] = websocket
        # logger.info(f"✅ WebSocket connected: {connection_id} (Total: {len(self.active_connections)})")
        
        # Send acknowledgment
        await self.send_to_connection(connection_id, {
            "type": "connection_ack",
            "connection_id": connection_id,
            "message": "Connected successfully"
        })
    
    def disconnect(self, connection_id: str):
        """Remove WebSocket connection"""
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]
            # logger.info(f"❌ WebSocket disconnected: {connection_id} (Remaining: {len(self.active_connections)})")
        
        # Clean up job mappings
        jobs_to_remove = [job_id for job_id, conn_id in self.job_connections.items() 
                          if conn_id == connection_id]
        for job_id in jobs_to_remove:
            del self.job_connections[job_id]
    
    async def send_to_connection(self, connection_id: str, message: dict):
        """Send message to specific connection"""
        if connection_id in self.active_connections:
            websocket = self.active_connections[connection_id]
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error sending to {connection_id}: {e}")
                self.disconnect(connection_id)
    
    async def send_to_job(self, job_id: str, message: dict):
        """Send message to connection associated with a job"""
        if job_id in self.job_connections:
            connection_id = self.job_connections[job_id]
            await self.send_to_connection(connection_id, message)
        else:
            logger.warning(f"No connection found for job {job_id}")
    
    def register_job(self, job_id: str, connection_id: str):
        """Register job to connection mapping"""
        self.job_connections[job_id] = connection_id

# Global connection manager
connection_manager = ConnectionManager()











