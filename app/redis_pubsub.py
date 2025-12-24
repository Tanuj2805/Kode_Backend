"""
Redis Pub/Sub Manager for Real-Time Communication
Provides true pub/sub functionality instead of polling
"""

import asyncio
import json
import logging
from typing import Callable, Dict, Optional
import redis.asyncio as redis
import os

logger = logging.getLogger(__name__)


class RedisPubSubManager:
    """Manages Redis Pub/Sub connections and subscriptions"""
    
    def __init__(self):
        self.redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        self.use_redis = self.redis_url.startswith('redis://')
        
        # Connection pools
        self.redis_client: Optional[redis.Redis] = None
        self.pubsub: Optional[redis.client.PubSub] = None
        
        # Handlers for different channels
        self.channel_handlers: Dict[str, Callable] = {}
        
        # Background tasks
        self.subscriber_task: Optional[asyncio.Task] = None
        
        logger.info(f"RedisPubSubManager initialized (use_redis={self.use_redis})")
    
    async def connect(self):
        """Connect to Redis and set up pub/sub"""
        if not self.use_redis:
            logger.info("Redis disabled - using in-memory mode")
            return
        
        try:
            # Create async Redis connection
            self.redis_client = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=10
            )
            
            # Test connection
            await self.redis_client.ping()
            
            # Create pub/sub
            self.pubsub = self.redis_client.pubsub()
            
            logger.info("✅ Connected to Redis Pub/Sub")
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to Redis: {e}")
            self.use_redis = False
    
    async def disconnect(self):
        """Disconnect from Redis"""
        if self.subscriber_task:
            self.subscriber_task.cancel()
            try:
                await self.subscriber_task
            except asyncio.CancelledError:
                pass
        
        if self.pubsub:
            await self.pubsub.close()
        
        if self.redis_client:
            await self.redis_client.close()
        
        logger.info("Disconnected from Redis Pub/Sub")
    
    async def publish(self, channel: str, message: dict):
        """
        Publish message to a channel
        
        Args:
            channel: Channel name (e.g., 'job_results', 'notifications')
            message: Dictionary to publish (will be JSON-encoded)
        """
        if not self.use_redis or not self.redis_client:
            logger.info(f"📢 [LOCAL] Would publish to {channel}: {message}")
            return
        
        try:
            message_json = json.dumps(message)
            await self.redis_client.publish(channel, message_json)
            logger.debug(f"Published to {channel}: {message.get('type', 'message')}")
        except Exception as e:
            logger.error(f"Error publishing to {channel}: {e}")
    
    async def subscribe(self, channel: str, handler: Callable):
        """
        Subscribe to a channel with a handler function
        
        Args:
            channel: Channel name to subscribe to
            handler: Async function to call when message received
                    Signature: async def handler(message: dict)
        """
        if not self.use_redis or not self.pubsub:
            logger.info(f"📡 [LOCAL] Would subscribe to {channel}")
            return
        
        try:
            # Store handler
            self.channel_handlers[channel] = handler
            
            # Subscribe to channel
            await self.pubsub.subscribe(channel)
            
            logger.info(f"✅ Subscribed to channel: {channel}")
            
            # Start subscriber task if not running
            if not self.subscriber_task or self.subscriber_task.done():
                self.subscriber_task = asyncio.create_task(self._subscriber_loop())
            
        except Exception as e:
            logger.error(f"Error subscribing to {channel}: {e}")
    
    async def unsubscribe(self, channel: str):
        """Unsubscribe from a channel"""
        if not self.use_redis or not self.pubsub:
            return
        
        try:
            await self.pubsub.unsubscribe(channel)
            if channel in self.channel_handlers:
                del self.channel_handlers[channel]
            logger.info(f"Unsubscribed from channel: {channel}")
        except Exception as e:
            logger.error(f"Error unsubscribing from {channel}: {e}")
    
    async def _subscriber_loop(self):
        """Background task that listens for messages"""
        logger.info("🎧 Started Redis Pub/Sub listener")
        
        try:
            async for message in self.pubsub.listen():
                if message['type'] == 'message':
                    channel = message['channel']
                    data = message['data']
                    
                    # Get handler for this channel
                    handler = self.channel_handlers.get(channel)
                    
                    if handler:
                        try:
                            # Parse JSON message
                            message_dict = json.loads(data)
                            
                            # Call handler
                            await handler(message_dict)
                            
                        except json.JSONDecodeError:
                            logger.error(f"Invalid JSON from {channel}: {data}")
                        except Exception as e:
                            logger.error(f"Error in handler for {channel}: {e}", exc_info=True)
                    else:
                        logger.warning(f"No handler for channel: {channel}")
                
        except asyncio.CancelledError:
            logger.info("Redis Pub/Sub listener stopped")
        except Exception as e:
            logger.error(f"Error in subscriber loop: {e}", exc_info=True)


# Global instance
redis_pubsub_manager = RedisPubSubManager()


# Convenience functions for common channels

async def publish_job_result(job_id: str, result: dict):
    """Publish job execution result"""
    await redis_pubsub_manager.publish('job_results', {
        'type': 'job_completed',
        'job_id': job_id,
        'result': result
    })


async def publish_job_started(job_id: str):
    """Publish job started notification"""
    await redis_pubsub_manager.publish('job_status', {
        'type': 'job_started',
        'job_id': job_id
    })


async def publish_job_failed(job_id: str, error: str):
    """Publish job failure notification"""
    await redis_pubsub_manager.publish('job_results', {
        'type': 'job_failed',
        'job_id': job_id,
        'error': error
    })


async def publish_notification(user_id: str, notification: dict):
    """Publish user notification"""
    await redis_pubsub_manager.publish(f'user:{user_id}', {
        'type': 'notification',
        'data': notification
    })


# Example handler function
async def example_job_result_handler(message: dict):
    """
    Example handler for job results
    
    Args:
        message: Dictionary with job result data
    """
    logger.info(f"Received job result: {message.get('job_id')}")
    
    # Your logic here
    # e.g., send to WebSocket, update database, etc.

