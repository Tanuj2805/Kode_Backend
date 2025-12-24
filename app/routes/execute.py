from fastapi import APIRouter, HTTPException, status
from app.models import ExecuteRequest, ExecuteResponse
from app.executors import execute_code as run_code
from app.queue_service import queue_service
from app.redis_service import redis_service
from app.queue_limiter import queue_limiter
import uuid
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/execute")
async def execute_code(request: ExecuteRequest):
    """
    Execute code via queue system (scalable approach)
    Returns job_id immediately, workers process asynchronously
    """
    try:
        # Check queue depth BEFORE accepting job
        can_accept, queue_depth, rejection_reason = queue_limiter.can_accept_job()
        
        if not can_accept:
            logger.warning(f"Job rejected - queue full ({queue_depth} jobs)")
            return {
                "status": "rejected",
                "message": rejection_reason,
                "queue_depth": queue_depth,
                "retry_after_seconds": 300
            }
        
        # Generate unique job ID
        job_id = str(uuid.uuid4())
        
        # Create job data
        job_data = {
            "job_id": job_id,
            "language": request.language,
            "code": request.code,
            "input": request.input or "",
            "timestamp": datetime.now().isoformat()
        }
        
        # Send to queue
        success = await queue_service.send_job(job_data)
        
        if not success:
            logger.error(f"Failed to queue job {job_id}")
            raise HTTPException(status_code=500, detail="Failed to queue job")
        
        # logger.info(f"SUCCESS: Job {job_id} queued for {request.language}")
        
        # Return job_id immediately (client will poll for results)
        return {
            "status": "queued",
            "job_id": job_id,
            "message": "Code submitted for execution",
            "poll_url": f"/api/execute/{job_id}/status"
        }
        
    except Exception as e:
        logger.error(f"Error submitting job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/execute/{job_id}/status")
async def get_execution_status(job_id: str):
    """
    Get execution status/result for a job
    Poll this endpoint until status is 'completed' or 'failed'
    """
    try:
        # Try to get result from Redis
        result_key = f"result:{job_id}"
        result_data = redis_service.get(result_key)
        
        if result_data:
            # Result found - parse and return
            result = json.loads(result_data)
            # logger.info(f"SUCCESS: Result retrieved for job {job_id}")
            return result
        else:
            # Result not ready yet
            # logger.debug(f"Job {job_id} still processing")
            return {
                "status": "processing",
                "job_id": job_id,
                "message": "Code is being executed, please poll again"
            }
            
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing result for {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving result")
    except Exception as e:
        logger.error(f"Error getting status for {job_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/execute/direct", response_model=ExecuteResponse)
async def execute_code_direct(request: ExecuteRequest):
    """
    Execute code directly (synchronous) - for testing/development only
    Use /execute (queue-based) for production
    """
    try:
        # logger.info(f"Direct execution requested for {request.language}")
        result = await run_code(request.language, request.code, request.input or "")
        return result
    except Exception as e:
        import traceback
        error_msg = f"{type(e).__name__}: {str(e)}"
        logger.error(f"Direct execution error: {error_msg}")
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "output": "",
            "error": error_msg
        }

