"""
Execute routes using Redis Queue + Pub/Sub
Frontend sends HTTP POST, backend handles everything
"""

from fastapi import APIRouter, HTTPException
from app.models import ExecuteRequest, ExecuteResponse
from app.redis_queue_service import redis_queue_service
from app.redis_pubsub import redis_pubsub_manager
from app.queue_limiter import queue_limiter
import uuid
import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter()

# Store for pending jobs (in-memory for now, could use Redis)
pending_jobs = {}


@router.post("/execute")
async def execute_code(request: ExecuteRequest):
    """
    Execute code via Redis Queue + wait for result
    
    Flow:
    1. Frontend sends POST request
    2. Backend creates job, sends to Redis Queue
    3. Worker processes and publishes result via Pub/Sub
    4. Backend receives result and returns to frontend
    """
    try:
        # Check queue depth
        can_accept, queue_depth, rejection_reason = queue_limiter.can_accept_job()
        
        if not can_accept:
            logger.warning(f"Job rejected - queue full ({queue_depth} jobs)")
            return {
                "status": "rejected",
                "message": rejection_reason,
                "queue_depth": queue_depth,
                "retry_after_seconds": 30
            }
        
        # Generate job ID
        job_id = str(uuid.uuid4())
        
        # Create job data
        job_data = {
            "job_id": job_id,
            "language": request.language,
            "code": request.code,
            "input": request.input or "",
            "timestamp": datetime.now().isoformat()
        }
        
        # Create future to wait for result
        result_future = asyncio.Future()
        pending_jobs[job_id] = result_future
        
        # Send to Redis Queue
        success = await redis_queue_service.send_job(job_data)
        
        if not success:
            del pending_jobs[job_id]
            logger.error(f"Failed to queue job {job_id}")
            raise HTTPException(status_code=500, detail="Failed to queue job")
        
        logger.info(f"✅ Job {job_id} queued, waiting for result...")
        
        # Wait for result (with timeout)
        try:
            result = await asyncio.wait_for(result_future, timeout=120.0)
            logger.info(f"✅ Job {job_id} completed")
            return result
        except asyncio.TimeoutError:
            logger.error(f"⏱️ Job {job_id} timed out")
            del pending_jobs[job_id]
            return {
                "success": False,
                "output": "",
                "error": "Execution timeout (120s limit)"
            }
        finally:
            # Clean up
            if job_id in pending_jobs:
                del pending_jobs[job_id]
        
    except Exception as e:
        logger.error(f"Error executing job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute/async")
async def execute_code_async(request: ExecuteRequest):
    """
    Execute code asynchronously - returns job_id immediately
    Client polls /execute/{job_id}/status for result
    """
    try:
        # Check queue depth
        can_accept, queue_depth, rejection_reason = queue_limiter.can_accept_job()
        
        if not can_accept:
            return {
                "status": "rejected",
                "message": rejection_reason,
                "queue_depth": queue_depth
            }
        
        # Generate job ID
        job_id = str(uuid.uuid4())
        
        # Create job data
        job_data = {
            "job_id": job_id,
            "language": request.language,
            "code": request.code,
            "input": request.input or "",
            "timestamp": datetime.now().isoformat()
        }
        
        # Send to Redis Queue
        success = await redis_queue_service.send_job(job_data)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to queue job")
        
        logger.info(f"Job {job_id} queued")
        
        # Return job_id
        return {
            "status": "queued",
            "job_id": job_id,
            "poll_url": f"/api/execute/{job_id}/status"
        }
        
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/execute/{job_id}/status")
async def get_execution_status(job_id: str):
    """
    Get execution status for async jobs
    Result stored in Redis by worker via Pub/Sub
    """
    try:
        # Check if result is in pending_jobs (real-time)
        if job_id in pending_jobs:
            future = pending_jobs[job_id]
            if future.done():
                return future.result()
            else:
                return {
                    "status": "processing",
                    "job_id": job_id,
                    "message": "Job is being executed"
                }
        
        # Otherwise still processing or not found
        return {
            "status": "processing",
            "job_id": job_id,
            "message": "Job is being executed"
        }
        
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Pub/Sub handler to receive results from workers
async def handle_job_result_http(message: dict):
    """
    Handler for job results from Redis Pub/Sub
    Called when worker publishes result
    """
    try:
        job_id = message.get('job_id')
        message_type = message.get('type')
        
        logger.info(f"📨 Received {message_type} for job {job_id}")
        
        if message_type == 'job_completed':
            result = message.get('result', {})
            
            # Check if this job has a pending future
            if job_id in pending_jobs:
                future = pending_jobs[job_id]
                if not future.done():
                    # Resolve the future with result
                    future.set_result(result)
                    logger.info(f"✅ Resolved future for job {job_id}")
        
        elif message_type == 'job_failed':
            error = message.get('error', 'Unknown error')
            
            if job_id in pending_jobs:
                future = pending_jobs[job_id]
                if not future.done():
                    future.set_result({
                        "success": False,
                        "output": "",
                        "error": error
                    })
    
    except Exception as e:
        logger.error(f"Error handling job result: {e}", exc_info=True)


# Setup function to subscribe to Pub/Sub
async def setup_http_pubsub():
    """Subscribe to job results for HTTP endpoint"""
    await redis_pubsub_manager.connect()
    await redis_pubsub_manager.subscribe('job_results', handle_job_result_http)
    logger.info("✅ HTTP execute route subscribed to job results")


async def cleanup_http_pubsub():
    """Cleanup Pub/Sub connection"""
    await redis_pubsub_manager.disconnect()
