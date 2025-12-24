"""
Redis service abstraction - uses dict locally, Redis in production
"""

import os
import json
import redis
from typing import Optional, Dict
import logging
import time
import asyncio
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# In-memory cache for development with expiry support
_memory_cache: Dict[str, tuple] = {}  # {key: (value, expiry_timestamp)}
_cache_lock = asyncio.Lock()

class RedisService:
    """Redis service that works locally and in production"""
    
    def __init__(self):
        redis_url = os.getenv('REDIS_URL', '')
        self.use_redis = redis_url.startswith('redis://')
        
        if self.use_redis:
            try:
                # Production: Use real Redis
                self.client = redis.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_connect_timeout=5
                )
                # Test connection
                self.client.ping()
                # logger.info("SUCCESS: Connected to Redis")
            except Exception as e:
                logger.warning(f"WARNING: Could not connect to Redis: {e}. Using in-memory cache.")
                self.use_redis = False
                self.client = None
        else:
            # Development: Use in-memory dict
            self.client = None
            # logger.info("INFO: Using in-memory cache for development")
    
    def _clean_expired(self):
        """Remove expired keys from memory cache"""
        now = time.time()
        expired_keys = [k for k, (v, exp) in _memory_cache.items() if exp and exp < now]
        for key in expired_keys:
            _memory_cache.pop(key, None)
    
    def set(self, key: str, value: str, expiry: int = 300):
        """Set value with expiry (default 5 minutes)"""
        try:
            if self.use_redis and self.client:
                self.client.setex(key, expiry, value)
            else:
                # In-memory with expiry support
                self._clean_expired()
                expiry_time = time.time() + expiry if expiry > 0 else None
                _memory_cache[key] = (value, expiry_time)
            return True
        except Exception as e:
            logger.error(f"Error setting cache: {e}")
            return False
    
    def get(self, key: str) -> Optional[str]:
        """Get value"""
        try:
            if self.use_redis and self.client:
                return self.client.get(key)
            else:
                # In-memory with expiry check
                self._clean_expired()
                if key in _memory_cache:
                    value, expiry_time = _memory_cache[key]
                    if expiry_time is None or expiry_time > time.time():
                        return value
                    else:
                        # Expired
                        _memory_cache.pop(key, None)
                return None
        except Exception as e:
            logger.error(f"Error getting cache: {e}")
            return None
    
    def delete(self, key: str):
        """Delete key"""
        try:
            if self.use_redis and self.client:
                self.client.delete(key)
            else:
                _memory_cache.pop(key, None)
            return True
        except Exception as e:
            logger.error(f"Error deleting cache: {e}")
            return False
    
    def incr(self, key: str) -> int:
        """Increment counter (for rate limiting)"""
        try:
            if self.use_redis and self.client:
                return self.client.incr(key)
            else:
                self._clean_expired()
                if key in _memory_cache:
                    value, expiry_time = _memory_cache[key]
                    current = int(value) if value else 0
                else:
                    current = 0
                
                new_value = current + 1
                # Keep existing expiry
                expiry_time = _memory_cache.get(key, (None, None))[1]
                _memory_cache[key] = (str(new_value), expiry_time)
                return new_value
        except Exception as e:
            logger.error(f"Error incrementing: {e}")
            return 0
    
    def expire(self, key: str, seconds: int):
        """Set expiry on key"""
        try:
            if self.use_redis and self.client:
                self.client.expire(key, seconds)
            else:
                # Update expiry for existing key
                if key in _memory_cache:
                    value, _ = _memory_cache[key]
                    expiry_time = time.time() + seconds
                    _memory_cache[key] = (value, expiry_time)
            return True
        except Exception as e:
            logger.error(f"Error setting expiry: {e}")
            return False
    
    async def publish(self, channel: str, message: str):
        """Publish message to channel (for Pub/Sub)"""
        try:
            if self.use_redis and self.client:
                self.client.publish(channel, message)
            else:
                # In-memory: Just log (no real pub/sub locally)
                pass
                # logger.info(f"INFO: [LOCAL] Publish to {channel}: {message[:100]}...")
            return True
        except Exception as e:
            logger.error(f"Error publishing: {e}")
            return False

# Global Redis service instance
redis_service = RedisService()


