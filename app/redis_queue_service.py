"""
Redis-based Queue Service for cross-process communication
Works with separate worker processes
"""

import os
import json
import asyncio
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("redis module not available")


class RedisQueueService:
    """Queue service using Redis lists (works across processes)"""
    
    def __init__(self):
        self.redis_url = os.getenv('REDIS_URL', 'redis://:password123@52.66.244.81:6379/0')
        self.use_redis = os.getenv('USE_REDIS', 'false').lower() == 'true'
        self.redis_client = None
        self.queue_name = 'code_execution_queue'
        
        if self.use_redis and REDIS_AVAILABLE:
            logger.info(f"Using Redis queue: {self.redis_url}")
        else:
            logger.warning("Redis queue disabled - jobs will not be processed by separate workers!")
    
    async def connect(self):
        """Connect to Redis"""
        if not self.use_redis or not REDIS_AVAILABLE:
            return
        
        try:
            self.redis_client = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            await self.redis_client.ping()
            logger.info("✅ Connected to Redis for queue")
        except Exception as e:
            logger.error(f"❌ Failed to connect to Redis: {e}")
            self.redis_client = None
    
    async def send_job(self, job_data: Dict) -> bool:
        """Send job to Redis queue"""
        if not self.redis_client:
            await self.connect()
        
        if not self.redis_client:
            logger.error("Redis not available - cannot queue job")
            return False
        
        try:
            # Convert to JSON and push to Redis list
            job_json = json.dumps(job_data)
            await self.redis_client.rpush(self.queue_name, job_json)
            
            logger.info(f"📋 Job queued in Redis: {job_data.get('job_id')}")
            return True
            
        except Exception as e:
            logger.error(f"Error queuing job: {e}")
            return False
    
    async def receive_job(self) -> Optional[Dict]:
        """Receive job from Redis queue (blocking)"""
        if not self.redis_client:
            await self.connect()
        
        if not self.redis_client:
            return None
        
        try:
            # BLPOP: blocking left pop (waits up to 1 second)
            result = await self.redis_client.blpop(self.queue_name, timeout=1)
            
            if result:
                # result is a tuple: (queue_name, job_json)
                _, job_json = result
                job_data = json.loads(job_json)
                logger.info(f"📥 Job received from Redis: {job_data.get('job_id')}")
                return job_data
            
            return None
            
        except Exception as e:
            logger.error(f"Error receiving job: {e}")
            return None
    
    async def get_queue_size(self) -> int:
        """Get number of jobs in queue"""
        if not self.redis_client:
            await self.connect()
        
        if not self.redis_client:
            return 0
        
        try:
            size = await self.redis_client.llen(self.queue_name)
            return size
        except:
            return 0


# Global instance
redis_queue_service = RedisQueueService()

