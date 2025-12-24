"""
Queue service abstraction - uses in-memory queue locally, SQS in production
"""

import os
import json
import asyncio
from typing import Optional, Dict
from collections import deque
import logging

logger = logging.getLogger(__name__)

# In-memory queue for development
_memory_queue = deque()

class QueueService:
    """Queue service that works locally and in production"""
    
    def __init__(self):
        self.use_sqs = os.getenv('USE_QUEUE', 'false').lower() == 'true'
        
        if self.use_sqs:
            # Production: Use AWS SQS
            import boto3
            self.sqs = boto3.client('sqs', region_name=os.getenv('AWS_REGION', 'us-east-1'))
            self.queue_url = os.getenv('SQS_QUEUE_URL')
            # logger.info("Using AWS SQS for queue")
        else:
            # Development: Use in-memory queue
            self.sqs = None
            self.queue_url = None
            # logger.info("Using in-memory queue for development")
    
    async def send_job(self, job_data: Dict) -> bool:
        """Send job to queue"""
        try:
            if self.use_sqs:
                # Production: Send to SQS
                self.sqs.send_message(
                    QueueUrl=self.queue_url,
                    MessageBody=json.dumps(job_data)
                )
            else:
                # Development: Add to in-memory queue
                _memory_queue.append(job_data)
            
            # logger.info(f"Job queued: {job_data.get('job_id')}")
            return True
            
        except Exception as e:
            logger.error(f"Error queuing job: {e}")
            return False
    
    async def receive_job(self) -> Optional[Dict]:
        """Receive job from queue (for workers)"""
        try:
            if self.use_sqs:
                # Production: Receive from SQS
                response = self.sqs.receive_message(
                    QueueUrl=self.queue_url,
                    MaxNumberOfMessages=1,
                    WaitTimeSeconds=10
                )
                
                if 'Messages' in response:
                    message = response['Messages'][0]
                    job_data = json.loads(message['Body'])
                    
                    # Delete message from queue
                    self.sqs.delete_message(
                        QueueUrl=self.queue_url,
                        ReceiptHandle=message['ReceiptHandle']
                    )
                    
                    return job_data
                return None
                
            else:
                # Development: Get from in-memory queue
                if _memory_queue:
                    return _memory_queue.popleft()
                return None
                
        except Exception as e:
            logger.error(f"Error receiving job: {e}")
            return None

# Global queue service instance
queue_service = QueueService()











