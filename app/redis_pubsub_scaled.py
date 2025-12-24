"""
Scaled Redis Pub/Sub Manager for 3000+ connections
Optimized for high-throughput environments
"""

import asyncio
import json
import logging
from typing import Callable, Dict, Optional, Set
import redis.asyncio as redis
from redis.asyncio.connection import ConnectionPool
import os

logger = logging.getLogger(__name__)


class RedisPubSubManagerScaled:
    """
    Scaled Redis Pub/Sub manager for high-throughput environments
    Optimized for 3000-5000 concurrent connections
    """
    
    def __init__(self):
        self.redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        self.use_redis = self.redis_url.startswith('redis://')
        
        # Connection pool settings for high concurrency
        self.pool_size = int(os.getenv('REDIS_POOL_SIZE', '50'))
        self.max_connections = int(os.getenv('REDIS_MAX_CONNECTIONS', '100'))
        
        # Connection pools
        self.connection_pool: Optional[ConnectionPool] = None
        self.redis_client: Optional[redis.Redis] = None
        self.pubsub: Optional[redis.client.PubSub] = None
        
        # Handlers for different channels (supports multiple handlers per channel)
        self.channel_handlers: Dict[str, Set[Callable]] = {}
        
        # Background tasks
        self.subscriber_task: Optional[asyncio.Task] = None
        
        # Performance metrics
        self.messages_received = 0
        self.messages_published = 0
        self.errors = 0
        
        logger.info(f"RedisPubSubManagerScaled initialized (pool_size={self.pool_size}, max_conn={self.max_connections})")
    
    async def connect(self):
        """Connect to Redis with connection pooling for high concurrency"""
        if not self.use_redis:
            logger.info("Redis disabled - using in-memory mode")
            return
        
        try:
            # Parse Redis URL to extract password if present
            redis_password = os.getenv('REDIS_PASSWORD')
            
            # Create connection pool with optimized settings
            self.connection_pool = ConnectionPool.from_url(
                self.redis_url,
                password=redis_password,
                encoding="utf-8",
                decode_responses=True,
                max_connections=self.max_connections,
                socket_connect_timeout=5,
                socket_keepalive=True,
                socket_keepalive_options={},
                health_check_interval=30,
                retry_on_timeout=True
            )
            
            # Create Redis client with pool
            self.redis_client = redis.Redis(
                connection_pool=self.connection_pool
            )
            
            # Test connection
            await self.redis_client.ping()
            
            # Create pub/sub
            self.pubsub = self.redis_client.pubsub()
            
            logger.info("✅ Connected to Redis Pub/Sub with connection pooling")
            logger.info(f"   Pool size: {self.pool_size}, Max connections: {self.max_connections}")
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to Redis: {e}")
            self.use_redis = False
    
    async def disconnect(self):
        """Disconnect from Redis and clean up resources"""
        if self.subscriber_task:
            self.subscriber_task.cancel()
            try:
                await self.subscriber_task
            except asyncio.CancelledError:
                pass
        
        if self.pubsub:
            try:
                await self.pubsub.close()
            except:
                pass
        
        if self.redis_client:
            try:
                await self.redis_client.close()
            except:
                pass
        
        if self.connection_pool:
            try:
                await self.connection_pool.disconnect()
            except:
                pass
        
        logger.info(f"Disconnected from Redis (published: {self.messages_published}, received: {self.messages_received}, errors: {self.errors})")
    
    async def publish(self, channel: str, message: dict):
        """
        Publish message to a channel (high-performance, non-blocking)
        
        Args:
            channel: Channel name
            message: Dictionary to publish (will be JSON-encoded)
        """
        if not self.use_redis or not self.redis_client:
            logger.debug(f"[LOCAL] Would publish to {channel}: {message.get('type', 'message')}")
            return
        
        try:
            message_json = json.dumps(message)
            await self.redis_client.publish(channel, message_json)
            self.messages_published += 1
            
            # Log milestone
            if self.messages_published % 10000 == 0:
                logger.info(f"📊 Published {self.messages_published} messages")
                
        except Exception as e:
            self.errors += 1
            logger.error(f"Error publishing to {channel}: {e}")
    
    async def publish_batch(self, channel: str, messages: list):
        """
        Publish multiple messages efficiently using pipeline
        
        Args:
            channel: Channel name
            messages: List of dictionaries to publish
        """
        if not self.use_redis or not self.redis_client:
            return
        
        try:
            # Use pipeline for batch publishing (reduces round-trips)
            async with self.redis_client.pipeline(transaction=False) as pipe:
                for message in messages:
                    message_json = json.dumps(message)
                    pipe.publish(channel, message_json)
                
                await pipe.execute()
                self.messages_published += len(messages)
                logger.debug(f"📦 Batch published {len(messages)} messages to {channel}")
                
        except Exception as e:
            self.errors += 1
            logger.error(f"Error batch publishing to {channel}: {e}")
    
    async def subscribe(self, channel: str, handler: Callable):
        """
        Subscribe to a channel with a handler function
        Supports multiple handlers per channel
        
        Args:
            channel: Channel name to subscribe to
            handler: Async function to call when message received
        """
        if not self.use_redis or not self.pubsub:
            logger.info(f"📡 [LOCAL] Would subscribe to {channel}")
            return
        
        try:
            # Add handler to set (allows multiple handlers per channel)
            if channel not in self.channel_handlers:
                self.channel_handlers[channel] = set()
                # Subscribe to channel
                await self.pubsub.subscribe(channel)
                logger.info(f"✅ Subscribed to channel: {channel}")
            
            self.channel_handlers[channel].add(handler)
            logger.debug(f"   Added handler {handler.__name__} to {channel} ({len(self.channel_handlers[channel])} handlers)")
            
            # Start subscriber task if not running
            if not self.subscriber_task or self.subscriber_task.done():
                self.subscriber_task = asyncio.create_task(self._subscriber_loop())
            
        except Exception as e:
            self.errors += 1
            logger.error(f"Error subscribing to {channel}: {e}")
    
    async def unsubscribe(self, channel: str, handler: Callable = None):
        """
        Unsubscribe from a channel
        
        Args:
            channel: Channel name
            handler: Specific handler to remove (if None, removes all handlers)
        """
        if not self.use_redis or not self.pubsub:
            return
        
        try:
            if handler and channel in self.channel_handlers:
                # Remove specific handler
                self.channel_handlers[channel].discard(handler)
                
                # If no more handlers, unsubscribe from channel
                if not self.channel_handlers[channel]:
                    await self.pubsub.unsubscribe(channel)
                    del self.channel_handlers[channel]
                    logger.info(f"Unsubscribed from channel: {channel} (no more handlers)")
            else:
                # Remove all handlers and unsubscribe
                await self.pubsub.unsubscribe(channel)
                if channel in self.channel_handlers:
                    del self.channel_handlers[channel]
                logger.info(f"Unsubscribed from channel: {channel}")
                
        except Exception as e:
            self.errors += 1
            logger.error(f"Error unsubscribing from {channel}: {e}")
    
    async def _subscriber_loop(self):
        """
        Background task that listens for messages (optimized for high throughput)
        Uses fire-and-forget pattern for handlers to avoid blocking
        """
        logger.info("🎧 Started Redis Pub/Sub listener (high-performance mode)")
        
        try:
            async for message in self.pubsub.listen():
                if message['type'] == 'message':
                    channel = message['channel']
                    data = message['data']
                    
                    # Get handlers for this channel
                    handlers = self.channel_handlers.get(channel, set())
                    
                    if handlers:
                        try:
                            # Parse JSON once
                            message_dict = json.loads(data)
                            self.messages_received += 1
                            
                            # Call all handlers (fire-and-forget for performance)
                            # This prevents slow handlers from blocking others
                            for handler in handlers:
                                asyncio.create_task(self._safe_handler_call(handler, message_dict))
                            
                            # Log milestone
                            if self.messages_received % 10000 == 0:
                                logger.info(f"📊 Received {self.messages_received} messages")
                                
                        except json.JSONDecodeError:
                            self.errors += 1
                            logger.error(f"Invalid JSON from {channel}: {data[:100]}...")
                        except Exception as e:
                            self.errors += 1
                            logger.error(f"Error processing message from {channel}: {e}")
                
        except asyncio.CancelledError:
            logger.info("Redis Pub/Sub listener stopped")
        except Exception as e:
            self.errors += 1
            logger.error(f"Error in subscriber loop: {e}", exc_info=True)
    
    async def _safe_handler_call(self, handler: Callable, message: dict):
        """
        Safely call handler with error handling
        Prevents one failing handler from affecting others
        """
        try:
            await handler(message)
        except Exception as e:
            self.errors += 1
            logger.error(f"Error in handler {handler.__name__}: {e}", exc_info=True)
    
    async def get_stats(self) -> dict:
        """Get performance statistics"""
        return {
            'published': self.messages_published,
            'received': self.messages_received,
            'errors': self.errors,
            'channels': len(self.channel_handlers),
            'total_handlers': sum(len(handlers) for handlers in self.channel_handlers.values()),
            'pool_size': self.pool_size,
            'max_connections': self.max_connections,
            'subscriber_active': self.subscriber_task and not self.subscriber_task.done() if self.subscriber_task else False
        }
    
    async def health_check(self) -> bool:
        """
        Check if Redis connection is healthy
        
        Returns:
            True if healthy, False otherwise
        """
        if not self.use_redis or not self.redis_client:
            return False
        
        try:
            await self.redis_client.ping()
            return True
        except:
            return False


# Global instance
redis_pubsub_scaled = RedisPubSubManagerScaled()


# Convenience functions for common channels

async def publish_job_result(job_id: str, result: dict):
    """Publish job execution result"""
    await redis_pubsub_scaled.publish('job_results', {
        'type': 'job_completed',
        'job_id': job_id,
        'result': result
    })


async def publish_job_started(job_id: str):
    """Publish job started notification"""
    await redis_pubsub_scaled.publish('job_status', {
        'type': 'job_started',
        'job_id': job_id
    })


async def publish_job_failed(job_id: str, error: str):
    """Publish job failure notification"""
    await redis_pubsub_scaled.publish('job_results', {
        'type': 'job_failed',
        'job_id': job_id,
        'error': error
    })

