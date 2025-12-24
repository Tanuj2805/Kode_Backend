"""
Background worker that processes code execution jobs
Run this separately: python worker.py
"""

import asyncio
import json
import logging
from datetime import datetime
from app.queue_service import queue_service
from app.redis_service import redis_service
from app.executors import execute_code

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
from dotenv import load_dotenv
load_dotenv(override=True)
async def process_job(job_data: dict):
    """Process a single job"""
    job_id = job_data['job_id']
    language = job_data['language']
    code = job_data['code']
    input_data = job_data.get('input', '')
    
    # logger.info(f"PROCESSING: Processing job {job_id}")
    
    try:
        # Execute code
        start_time = datetime.now()
        result = await execute_code(language, code, input_data)
        end_time = datetime.now()
        
        execution_time = (end_time - start_time).total_seconds()
        
        # Add job_id and execution time to result
        result['job_id'] = job_id
        result['status'] = 'completed'
        result['execution_time'] = execution_time
        
        # Store result in Redis (5 minute expiry)
        redis_service.set(
            f"result:{job_id}",
            json.dumps(result),
            expiry=300
        )
        
        # logger.info(f"SUCCESS: Job {job_id} completed in {execution_time:.2f}s")
        
    except Exception as e:
        logger.error(f"ERROR: Job {job_id} failed: {e}", exc_info=True)
        
        # Store error result
        error_result = {
            "job_id": job_id,
            "status": "failed",
            "success": False,
            "output": "",
            "error": str(e)
        }
        
        redis_service.set(
            f"result:{job_id}",
            json.dumps(error_result),
            expiry=300
        )

async def worker_loop():
    """Main worker loop"""
    # logger.info("STARTING: Worker started, waiting for jobs...")
    
    while True:
        try:
            # Receive job from queue
            job_data = await queue_service.receive_job()
            
            if job_data:
                # Process job
                await process_job(job_data)
            else:
                # No jobs, wait a bit
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Worker error: {e}", exc_info=True)
            await asyncio.sleep(5)

if __name__ == '__main__':
    asyncio.run(worker_loop())


