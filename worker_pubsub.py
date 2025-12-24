"""
Worker for processing code execution jobs with Redis Pub/Sub
Publishes results to Redis channels AND stores in Redis keys
- Pub/Sub: For real-time updates (execute_redis / run button)
- Redis keys: For HTTP polling (weekly_challenges / submit button)
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from typing import Dict, Any

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables FIRST!
from dotenv import load_dotenv
load_dotenv(override=True)

from app.redis_queue_service import redis_queue_service
from app.redis_pubsub import redis_pubsub_manager, publish_job_result, publish_job_started, publish_job_failed
from app.redis_service import redis_service
from app.executors import execute_code

logging.basicConfig(
    level=logging.DEBUG,  # Changed to DEBUG to see all messages
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Also set Redis logger to INFO to avoid spam
logging.getLogger('app.redis_queue_service').setLevel(logging.INFO)
logging.getLogger('app.redis_pubsub').setLevel(logging.INFO)


async def process_job(job_data: Dict[str, Any]):
    """
    Process a code execution job and publish result via Pub/Sub
    
    Args:
        job_data: Dictionary containing job information
    """
    job_id = job_data.get('job_id')
    connection_id = job_data.get('connection_id')
    language = job_data.get('language')
    code = job_data.get('code')
    input_data = job_data.get('input', '')
    
    # logger.info(f"🔨 Processing job {job_id} (language: {language})")
    
    try:
        # Publish job started
        await publish_job_started(job_id)
        
        # Execute code
        start_time = datetime.now()
        result = await execute_code(language, code, input_data)
        end_time = datetime.now()
        
        execution_time = (end_time - start_time).total_seconds()
        
        # Add execution time to result
        result['execution_time'] = execution_time
        
        # logger.info(f"✅ Job {job_id} completed in {execution_time:.2f}s")
        
        # Publish result via Pub/Sub (for execute_redis / run button)
        await publish_job_result(job_id, result)
        
        # ALSO store result in Redis key (for weekly_challenges / submit button)
        result_key = f"result:{job_id}"
        redis_service.set(result_key, json.dumps(result), expiry=300)
        logger.info(f"📝 Stored result key: {result_key}")
        
    except Exception as e:
        logger.error(f"❌ Job {job_id} failed: {e}", exc_info=True)
        
        # Publish failure via Pub/Sub (for execute_redis / run button)
        await publish_job_failed(job_id, str(e))
        
        # ALSO store error in Redis key (for weekly_challenges / submit button)
        result_key = f"result:{job_id}"
        error_result = {
            "success": False,
            "output": "",
            "error": str(e),
            "execution_time": 0
        }
        redis_service.set(result_key, json.dumps(error_result), expiry=300)
        logger.info(f"📝 Stored error result key: {result_key}")


async def worker_loop(worker_id: int = 0):
    """
    Main worker loop
    Continuously receives jobs from queue and processes them
    """
    # logger.info(f"🚀 Worker {worker_id} started")
    
    # Connect to Redis Pub/Sub
    await redis_pubsub_manager.connect()
    
    # Connect to Redis Queue
    await redis_queue_service.connect()
    
    consecutive_errors = 0
    max_consecutive_errors = 5
    
    while True:
        try:
            # Receive job from Redis queue (works across processes!)
            #logger.debug(f"Worker {worker_id} waiting for job...")
            job_data = await redis_queue_service.receive_job()
            
            if job_data:
                consecutive_errors = 0  # Reset error counter
                # logger.info(f"Worker {worker_id} got job: {job_data.get('job_id')}")
                
                # Process the job
                await process_job(job_data)
                
                # logger.info(f"Worker {worker_id} finished job, looping back...")
            else:
                # No job available, wait a bit
                #logger.debug(f"Worker {worker_id} no job, waiting...")
                await asyncio.sleep(1)
        
        except asyncio.CancelledError:
            # logger.info(f"Worker {worker_id} cancelled")
            break
        
        except Exception as e:
            consecutive_errors += 1
            logger.error(f"Error in worker {worker_id}: {e}", exc_info=True)
            
            # If too many consecutive errors, stop worker
            if consecutive_errors >= max_consecutive_errors:
                logger.error(f"Worker {worker_id} stopping due to too many errors")
                break
            
            # Wait before retrying
            await asyncio.sleep(5)
    
    # Clean up
    await redis_pubsub_manager.disconnect()
    # logger.info(f"Worker {worker_id} stopped")


async def start_workers(num_workers: int = 4):
    """
    Start multiple worker processes
    
    Args:
        num_workers: Number of workers to start
    """
    # logger.info(f"=" * 60)
    # logger.info(f"Starting {num_workers} workers with Redis Pub/Sub")
    # logger.info(f"=" * 60)
    
    # Create worker tasks
    tasks = []
    for i in range(num_workers):
        task = asyncio.create_task(worker_loop(i))
        tasks.append(task)
    
    # Wait for all workers
    try:
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        # logger.info("Shutting down workers...")
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Code execution worker with Redis Pub/Sub')
    parser.add_argument('--workers', type=int, default=4, help='Number of workers (default: 4)')
    args = parser.parse_args()
    
    try:
        asyncio.run(start_workers(args.workers))
    except KeyboardInterrupt:
        logger.info("Worker stopped by user")

