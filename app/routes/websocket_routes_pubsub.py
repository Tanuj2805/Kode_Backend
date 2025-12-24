"""
WebSocket routes for real-time code execution with Redis Pub/Sub
Enhanced version that uses true pub/sub instead of polling
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.websocket_manager import connection_manager
from app.redis_queue_service import redis_queue_service
from app.redis_pubsub import redis_pubsub_manager, publish_job_result
from app.queue_limiter import queue_limiter
import uuid
import json
import logging
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter()


# Handler for job results from Redis Pub/Sub
async def handle_job_result(message: dict):
    """
    Handler for job results from Redis Pub/Sub
    Called whenever a job completes
    """
    try:
        job_id = message.get('job_id')
        message_type = message.get('type')
        
        logger.info(f"📨 Pub/Sub received {message_type} for job {job_id}")
        logger.info(f"   Full message: {message}")
        
        if message_type == 'job_completed':
            result = message.get('result', {})
            
            # Check if we have a WebSocket connection for this job
            if job_id not in connection_manager.job_connections:
                logger.debug(f"No WebSocket connection for job {job_id} (job_completed) - likely HTTP-based execution")
                return
            
            logger.info(f"✅ Sending result to WebSocket for job {job_id}")
            await connection_manager.send_to_job(job_id, {
                "type": "job_completed",
                "job_id": job_id,
                "result": {
                    "success": result.get('success', True),
                    "output": result.get('output', ''),
                    "error": result.get('error', ''),
                    "execution_time": result.get('execution_time')
                }
            })
            logger.info(f"✅ Result sent to WebSocket for job {job_id}")
            
            # Clean up job mapping
            if job_id in connection_manager.job_connections:
                del connection_manager.job_connections[job_id]
        
        elif message_type == 'job_failed':
            # Check if we have a WebSocket connection for this job
            if job_id not in connection_manager.job_connections:
                logger.debug(f"No WebSocket connection for job {job_id} (job_failed) - likely HTTP-based execution")
                return
            
            error = message.get('error', 'Unknown error')
            await connection_manager.send_to_job(job_id, {
                "type": "job_failed",
                "job_id": job_id,
                "error": error
            })
            
            # Clean up job mapping
            if job_id in connection_manager.job_connections:
                del connection_manager.job_connections[job_id]
        
        elif message_type == 'job_started':
            # Check if we have a WebSocket connection for this job
            if job_id not in connection_manager.job_connections:
                logger.debug(f"No WebSocket connection for job {job_id} (job_started) - likely HTTP-based execution")
                return
            
            await connection_manager.send_to_job(job_id, {
                "type": "job_started",
                "job_id": job_id,
                "message": "Your code is being executed"
            })
    
    except Exception as e:
        logger.error(f"Error handling job result: {e}", exc_info=True)


@router.websocket("/ws/pubsub")
async def websocket_pubsub_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint with Redis Pub/Sub
    No polling - uses true pub/sub for real-time updates
    """
    connection_id = str(uuid.uuid4())
    
    try:
        # Accept connection
        await connection_manager.connect(connection_id, websocket)
        
        # Keep connection alive and handle messages
        while True:
            try:
                # Wait for message from client
                data = await websocket.receive_json()
                logger.info(f"📨 Received from {connection_id}: {data.get('action')}")
                
                action = data.get('action')
                
                if action == 'execute':
                    await handle_execute(connection_id, data)
                
                elif action == 'ping':
                    await connection_manager.send_to_connection(connection_id, {
                        "type": "pong",
                        "timestamp": datetime.now().isoformat()
                    })
                
                else:
                    await connection_manager.send_to_connection(connection_id, {
                        "type": "error",
                        "message": f"Unknown action: {action}"
                    })
                    
            except WebSocketDisconnect:
                logger.info(f"Client {connection_id} disconnected")
                break
            except Exception as e:
                logger.error(f"Error in WebSocket loop: {e}", exc_info=True)
                break
    
    finally:
        # Clean up
        connection_manager.disconnect(connection_id)


async def handle_execute(connection_id: str, data: dict):
    """Handle code execution request"""
    try:
        # Check queue depth BEFORE accepting job
        can_accept, queue_depth, rejection_reason = queue_limiter.can_accept_job()
        
        if not can_accept:
            logger.warning(f"Job rejected for {connection_id} - queue full ({queue_depth} jobs)")
            await connection_manager.send_to_connection(connection_id, {
                "type": "queue_full",
                "message": rejection_reason,
                "queue_depth": queue_depth,
                "retry_after_seconds": 300  # Suggest retry after 5 minutes
            })
            return
        
        # Generate job ID
        job_id = str(uuid.uuid4())
        
        # Extract data
        language = data.get('language')
        code = data.get('code')
        input_data = data.get('input', '')
        
        if not language or not code:
            await connection_manager.send_to_connection(connection_id, {
                "type": "error",
                "message": "Missing language or code"
            })
            return
        
        # Register job to connection
        connection_manager.register_job(job_id, connection_id)
        
        # Create job data
        job_data = {
            "job_id": job_id,
            "connection_id": connection_id,
            "language": language,
            "code": code,
            "input": input_data,
            "timestamp": datetime.now().isoformat()
        }
        
        # Send to Redis queue (works across processes!)
        success = await redis_queue_service.send_job(job_data)
        
        if success:
            # Notify client job was queued
            await connection_manager.send_to_connection(connection_id, {
                "type": "job_created",
                "job_id": job_id,
                "status": "queued",
                "message": "Your code is in the queue",
                "queue_depth": queue_depth,
                "estimated_wait_seconds": (queue_depth // 100) * 60 if queue_depth else 10
            })
        else:
            await connection_manager.send_to_connection(connection_id, {
                "type": "error",
                "message": "Failed to queue job"
            })
            
    except Exception as e:
        logger.error(f"Error handling execute: {e}", exc_info=True)
        await connection_manager.send_to_connection(connection_id, {
            "type": "error",
            "message": f"Failed to queue job: {str(e)}"
        })


# Initialize pub/sub subscription on module load
async def setup_pubsub():
    """Set up Redis Pub/Sub subscriptions"""
    await redis_pubsub_manager.connect()
    
    # Subscribe to job results channel
    await redis_pubsub_manager.subscribe('job_results', handle_job_result)
    
    # Subscribe to job status channel (optional)
    await redis_pubsub_manager.subscribe('job_status', handle_job_result)
    
    logger.info("✅ Redis Pub/Sub subscriptions ready")


async def cleanup_pubsub():
    """Clean up Redis Pub/Sub connections"""
    await redis_pubsub_manager.disconnect()
    logger.info("Redis Pub/Sub cleaned up")

