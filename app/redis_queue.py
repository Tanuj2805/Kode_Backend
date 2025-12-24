"""
Redis Queue Service for Code Execution
Uses RQ (Redis Queue) for distributed task processing
"""

import os
from redis import Redis
from rq import Queue
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

# Redis connection
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

class RedisQueueService:
    """Manages Redis queue for code execution tasks"""
    
    def __init__(self):
        try:
            self.redis_conn = Redis.from_url(REDIS_URL, decode_responses=False)
            self.queue = Queue('code_execution', connection=self.redis_conn)
            # logger.info(f"✅ Connected to Redis: {REDIS_URL}")
        except Exception as e:
            logger.error(f"❌ Failed to connect to Redis: {e}")
            self.redis_conn = None
            self.queue = None
    
    def is_available(self) -> bool:
        """Check if Redis is available"""
        if not self.redis_conn:
            return False
        try:
            self.redis_conn.ping()
            return True
        except:
            return False
    
    def enqueue_job(self, job_data: Dict[str, Any], job_id: str, timeout: int = 30) -> Optional[str]:
        """
        Enqueue a code execution job
        
        Args:
            job_data: Dict with language, code, stdin
            job_id: Unique job identifier
            timeout: Job timeout in seconds
            
        Returns:
            Job ID if successful, None otherwise
        """
        if not self.is_available():
            logger.error("Redis not available")
            return None
        
        try:
            from worker_tasks import execute_code_task
            
            job = self.queue.enqueue(
                execute_code_task,
                job_data,
                job_id=job_id,
                job_timeout=timeout,
                result_ttl=300,  # Keep result for 5 minutes
                failure_ttl=300  # Keep failure info for 5 minutes
            )
            
            # logger.info(f"📋 Enqueued job: {job_id}")
            return job.id
            
        except Exception as e:
            logger.error(f"❌ Failed to enqueue job {job_id}: {e}")
            return None
    
    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """
        Get status of a job
        
        Returns:
            Dict with status, result, error
        """
        if not self.is_available():
            return {"status": "error", "error": "Redis not available"}
        
        try:
            from rq.job import Job
            
            job = Job.fetch(job_id, connection=self.redis_conn)
            
            if job.is_finished:
                return {
                    "status": "completed",
                    "result": job.result
                }
            elif job.is_failed:
                return {
                    "status": "failed",
                    "error": str(job.exc_info)
                }
            elif job.is_started:
                return {
                    "status": "processing"
                }
            else:
                return {
                    "status": "queued"
                }
                
        except Exception as e:
            logger.error(f"❌ Failed to get job status {job_id}: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    def get_queue_size(self) -> int:
        """Get number of jobs in queue"""
        if not self.is_available():
            return 0
        try:
            return len(self.queue)
        except:
            return 0
    
    def get_worker_count(self) -> int:
        """Get number of active workers"""
        if not self.is_available():
            return 0
        try:
            from rq import Worker
            return len(Worker.all(connection=self.redis_conn))
        except:
            return 0

# Global instance
redis_queue_service = RedisQueueService()










