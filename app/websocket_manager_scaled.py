"""
Scaled WebSocket connection manager for 3000+ concurrent connections
Optimized for high-throughput real-time communication
"""

from fastapi import WebSocket
from typing import Dict, Set, Optional
import json
import logging
import asyncio
from collections import defaultdict
import time

logger = logging.getLogger(__name__)


class ConnectionManagerScaled:
    """
    Manages WebSocket connections at scale
    Optimized for 3000-5000 concurrent connections per server instance
    """
    
    def __init__(self):
        # Store active connections: {connection_id: WebSocket}
        self.active_connections: Dict[str, WebSocket] = {}
        
        # Map job_id to connection_id: {job_id: connection_id}
        self.job_connections: Dict[str, str] = {}
        
        # User to connections mapping (for multi-device support)
        # {user_id: set of connection_ids}
        self.user_connections: Dict[str, Set[str]] = defaultdict(set)
        
        # Connection metadata
        self.connection_metadata: Dict[str, dict] = {}
        
        # Performance metrics
        self.messages_sent = 0
        self.connections_total = 0
        self.peak_connections = 0
        self.disconnections_total = 0
        self.send_errors = 0
        
        # Rate limiting per connection (prevent spam)
        self.connection_message_count: Dict[str, int] = defaultdict(int)
        self.connection_last_reset: Dict[str, float] = defaultdict(float)
        self.rate_limit_window = 60  # seconds
        self.rate_limit_max = 100    # messages per window
        
        logger.info("ConnectionManagerScaled initialized")
    
    async def connect(self, connection_id: str, websocket: WebSocket, user_id: str = None):
        """
        Accept new WebSocket connection
        
        Args:
            connection_id: Unique connection identifier
            websocket: WebSocket instance
            user_id: Optional user identifier
        """
        try:
            await websocket.accept()
            
            self.active_connections[connection_id] = websocket
            self.connections_total += 1
            
            # Track user connections
            if user_id:
                self.user_connections[user_id].add(connection_id)
            
            # Store metadata
            self.connection_metadata[connection_id] = {
                'user_id': user_id,
                'connected_at': time.time(),
                'messages_sent': 0,
                'last_activity': time.time()
            }
            
            # Initialize rate limiting
            self.connection_message_count[connection_id] = 0
            self.connection_last_reset[connection_id] = time.time()
            
            # Update peak
            current = len(self.active_connections)
            if current > self.peak_connections:
                self.peak_connections = current
                if current % 100 == 0:  # Log every 100 connections
                    logger.info(f"📈 New peak connections: {self.peak_connections}")
            
            logger.debug(f"✅ WebSocket connected: {connection_id} (Total: {current})")
            
            # Send acknowledgment
            await self.send_to_connection(connection_id, {
                "type": "connection_ack",
                "connection_id": connection_id,
                "message": "Connected successfully",
                "server_time": time.time()
            })
            
        except Exception as e:
            logger.error(f"Error accepting connection {connection_id}: {e}")
            raise
    
    def disconnect(self, connection_id: str):
        """
        Remove WebSocket connection and clean up resources
        
        Args:
            connection_id: Connection to disconnect
        """
        if connection_id in self.active_connections:
            # Remove connection
            del self.active_connections[connection_id]
            self.disconnections_total += 1
            
            # Remove from user mapping
            metadata = self.connection_metadata.get(connection_id, {})
            user_id = metadata.get('user_id')
            if user_id and connection_id in self.user_connections.get(user_id, set()):
                self.user_connections[user_id].discard(connection_id)
                # Clean up empty user sets
                if not self.user_connections[user_id]:
                    del self.user_connections[user_id]
            
            # Remove metadata
            if connection_id in self.connection_metadata:
                del self.connection_metadata[connection_id]
            
            # Clean up rate limiting
            self.connection_message_count.pop(connection_id, None)
            self.connection_last_reset.pop(connection_id, None)
            
            current = len(self.active_connections)
            logger.debug(f"❌ WebSocket disconnected: {connection_id} (Remaining: {current})")
        
        # Clean up job mappings
        jobs_to_remove = [job_id for job_id, conn_id in self.job_connections.items() 
                          if conn_id == connection_id]
        for job_id in jobs_to_remove:
            del self.job_connections[job_id]
    
    def _check_rate_limit(self, connection_id: str) -> bool:
        """
        Check if connection is within rate limit
        
        Args:
            connection_id: Connection to check
            
        Returns:
            True if within limit, False if rate limited
        """
        now = time.time()
        last_reset = self.connection_last_reset[connection_id]
        
        # Reset counter if window expired
        if now - last_reset > self.rate_limit_window:
            self.connection_message_count[connection_id] = 0
            self.connection_last_reset[connection_id] = now
        
        # Check limit
        if self.connection_message_count[connection_id] >= self.rate_limit_max:
            return False
        
        self.connection_message_count[connection_id] += 1
        return True
    
    async def send_to_connection(self, connection_id: str, message: dict, bypass_rate_limit: bool = False):
        """
        Send message to specific connection (non-blocking)
        
        Args:
            connection_id: Target connection
            message: Message to send
            bypass_rate_limit: Skip rate limiting (for system messages)
        """
        if connection_id not in self.active_connections:
            return
        
        # Check rate limit (unless bypassed)
        if not bypass_rate_limit and not self._check_rate_limit(connection_id):
            logger.warning(f"Rate limit exceeded for {connection_id}")
            return
        
        websocket = self.active_connections[connection_id]
        try:
            await websocket.send_json(message)
            self.messages_sent += 1
            
            # Update metadata
            if connection_id in self.connection_metadata:
                self.connection_metadata[connection_id]['messages_sent'] += 1
                self.connection_metadata[connection_id]['last_activity'] = time.time()
            
            # Log milestone
            if self.messages_sent % 10000 == 0:
                logger.info(f"📊 Sent {self.messages_sent} messages total")
                
        except Exception as e:
            self.send_errors += 1
            logger.error(f"Error sending to {connection_id}: {e}")
            # Disconnect on error
            self.disconnect(connection_id)
    
    async def send_to_user(self, user_id: str, message: dict):
        """
        Send message to all connections of a user
        
        Args:
            user_id: Target user
            message: Message to send
        """
        connection_ids = self.user_connections.get(user_id, set()).copy()
        
        if not connection_ids:
            logger.debug(f"No connections found for user {user_id}")
            return
        
        # Send to all user's connections in parallel
        tasks = [
            self.send_to_connection(conn_id, message, bypass_rate_limit=True)
            for conn_id in connection_ids
        ]
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def send_to_job(self, job_id: str, message: dict):
        """
        Send message to connection associated with a job
        
        Args:
            job_id: Job identifier
            message: Message to send
        """
        if job_id in self.job_connections:
            connection_id = self.job_connections[job_id]
            await self.send_to_connection(connection_id, message, bypass_rate_limit=True)
        else:
            logger.warning(f"No connection found for job {job_id}")
    
    async def broadcast(self, message: dict, exclude: Set[str] = None):
        """
        Broadcast message to all connections (efficient batched processing)
        
        Args:
            message: Message to broadcast
            exclude: Set of connection_ids to exclude
        """
        exclude = exclude or set()
        
        # Get all connection IDs to send to
        connection_ids = [
            conn_id for conn_id in self.active_connections.keys()
            if conn_id not in exclude
        ]
        
        if not connection_ids:
            return
        
        logger.info(f"📡 Broadcasting to {len(connection_ids)} connections")
        
        # Process in batches to avoid overwhelming the event loop
        batch_size = 100
        for i in range(0, len(connection_ids), batch_size):
            batch = connection_ids[i:i+batch_size]
            tasks = [
                self.send_to_connection(conn_id, message, bypass_rate_limit=True)
                for conn_id in batch
            ]
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # Small delay between batches to prevent event loop blocking
            if i + batch_size < len(connection_ids):
                await asyncio.sleep(0.01)
    
    def register_job(self, job_id: str, connection_id: str):
        """
        Register job to connection mapping
        
        Args:
            job_id: Job identifier
            connection_id: Connection identifier
        """
        self.job_connections[job_id] = connection_id
        logger.debug(f"Registered job {job_id} to connection {connection_id}")
    
    def get_connection_info(self, connection_id: str) -> Optional[dict]:
        """
        Get information about a connection
        
        Args:
            connection_id: Connection to query
            
        Returns:
            Connection metadata or None
        """
        return self.connection_metadata.get(connection_id)
    
    def get_user_connections(self, user_id: str) -> Set[str]:
        """
        Get all connection IDs for a user
        
        Args:
            user_id: User identifier
            
        Returns:
            Set of connection IDs
        """
        return self.user_connections.get(user_id, set()).copy()
    
    async def cleanup_stale_connections(self, timeout_seconds: int = 3600):
        """
        Remove connections that have been inactive for too long
        
        Args:
            timeout_seconds: Inactivity timeout
        """
        now = time.time()
        stale_connections = []
        
        for conn_id, metadata in self.connection_metadata.items():
            last_activity = metadata.get('last_activity', metadata.get('connected_at', now))
            if now - last_activity > timeout_seconds:
                stale_connections.append(conn_id)
        
        if stale_connections:
            logger.info(f"🧹 Cleaning up {len(stale_connections)} stale connections")
            for conn_id in stale_connections:
                self.disconnect(conn_id)
    
    def get_stats(self) -> dict:
        """
        Get connection statistics
        
        Returns:
            Dictionary with current statistics
        """
        return {
            'active_connections': len(self.active_connections),
            'peak_connections': self.peak_connections,
            'total_connections': self.connections_total,
            'total_disconnections': self.disconnections_total,
            'messages_sent': self.messages_sent,
            'send_errors': self.send_errors,
            'unique_users': len(self.user_connections),
            'active_jobs': len(self.job_connections),
            'avg_messages_per_connection': self.messages_sent / max(self.connections_total, 1)
        }
    
    async def periodic_cleanup(self):
        """Background task to periodically clean up stale connections"""
        while True:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes
                await self.cleanup_stale_connections()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic cleanup: {e}")


# Global connection manager
connection_manager_scaled = ConnectionManagerScaled()

