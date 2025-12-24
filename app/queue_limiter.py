"""
Queue Depth Limiter - Protects system from overload
Maintains queue depth at safe levels
"""

import os
import logging
from typing import Optional
import boto3
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class QueueLimiter:
    """
    Enforces queue depth limits to prevent system overload
    """
    
    def __init__(self, max_queue_depth: int = 1000):
        """
        Initialize queue limiter
        
        Args:
            max_queue_depth: Maximum allowed queue depth (default: 1000)
        """
        self.max_queue_depth = max_queue_depth
        self.use_sqs = os.getenv('USE_QUEUE', 'false').lower() == 'true'
        
        if self.use_sqs:
            self.sqs = boto3.client('sqs', region_name=os.getenv('AWS_REGION', 'us-east-1'))
            self.queue_url = os.getenv('SQS_QUEUE_URL')
            # logger.info(f"Queue limiter initialized (max depth: {max_queue_depth})")
        else:
            # Development mode - in-memory queue
            from app.queue_service import _memory_queue
            self._memory_queue = _memory_queue
            # logger.info("Queue limiter in development mode")
    
    def get_queue_depth(self) -> Optional[int]:
        """
        Get current queue depth
        
        Returns:
            Number of jobs in queue, or None if unable to check
        """
        try:
            if self.use_sqs:
                # Production: Get from SQS
                response = self.sqs.get_queue_attributes(
                    QueueUrl=self.queue_url,
                    AttributeNames=[
                        'ApproximateNumberOfMessages',
                        'ApproximateNumberOfMessagesNotVisible'
                    ]
                )
                
                waiting = int(response['Attributes'].get('ApproximateNumberOfMessages', 0))
                processing = int(response['Attributes'].get('ApproximateNumberOfMessagesNotVisible', 0))
                
                total = waiting + processing
                # logger.debug(f"Queue depth: {total} (waiting: {waiting}, processing: {processing})")
                return total
            else:
                # Development: Get from in-memory queue
                depth = len(self._memory_queue)
                # logger.debug(f"Queue depth (dev): {depth}")
                return depth
                
        except Exception as e:
            logger.error(f"Error getting queue depth: {e}")
            return None
    
    def can_accept_job(self) -> tuple[bool, Optional[int], Optional[str]]:
        """
        Check if system can accept new job
        
        Returns:
            Tuple of (can_accept, queue_depth, reason)
            - can_accept: True if job can be accepted
            - queue_depth: Current queue depth
            - reason: Rejection reason if can't accept
        """
        queue_depth = self.get_queue_depth()
        
        # If can't check queue depth, fail open (accept job)
        if queue_depth is None:
            logger.warning("Could not check queue depth, accepting job anyway")
            return True, None, None
        
        # Check against limit
        if queue_depth >= self.max_queue_depth:
            # Calculate estimated wait time
            estimated_wait_minutes = queue_depth // 100  # Assuming 100 jobs/minute processing
            
            reason = (
                f"System is experiencing high load. "
                f"Queue has {queue_depth} jobs (max: {self.max_queue_depth}). "
                f"Estimated wait would be {estimated_wait_minutes}+ minutes. "
                f"Please try again in {max(5, estimated_wait_minutes // 2)} minutes."
            )
            
            logger.warning(f"Job rejected - queue full: {queue_depth}/{self.max_queue_depth}")
            return False, queue_depth, reason
        
        # Queue has space
        # logger.debug(f"Job accepted - queue depth: {queue_depth}/{self.max_queue_depth}")
        return True, queue_depth, None
    
    def get_queue_status(self) -> dict:
        """
        Get detailed queue status
        
        Returns:
            Dictionary with queue statistics
        """
        queue_depth = self.get_queue_depth()
        
        if queue_depth is None:
            return {
                "status": "unknown",
                "message": "Unable to check queue status"
            }
        
        utilization = (queue_depth / self.max_queue_depth) * 100
        
        if queue_depth >= self.max_queue_depth:
            status = "full"
            message = f"Queue full ({queue_depth} jobs)"
        elif utilization >= 80:
            status = "high"
            message = f"Queue nearly full ({queue_depth}/{self.max_queue_depth})"
        elif utilization >= 50:
            status = "medium"
            message = f"Queue moderately loaded ({queue_depth}/{self.max_queue_depth})"
        else:
            status = "healthy"
            message = f"Queue healthy ({queue_depth}/{self.max_queue_depth})"
        
        return {
            "status": status,
            "queue_depth": queue_depth,
            "max_depth": self.max_queue_depth,
            "utilization_percent": round(utilization, 1),
            "message": message,
            "estimated_wait_minutes": queue_depth // 100 if queue_depth > 0 else 0
        }

# Global queue limiter instance
queue_limiter = QueueLimiter(max_queue_depth=1000)











