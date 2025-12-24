"""
WebSocket routes for real-time code execution
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.websocket_manager import connection_manager
from app.queue_service import queue_service
from app.redis_service import redis_service
from app.queue_limiter import queue_limiter
import uuid
import json
import logging
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Main WebSocket endpoint"""
    connection_id = str(uuid.uuid4())
    
    try:
        # Accept connection
        await connection_manager.connect(connection_id, websocket)
        
        # Start listening for results
        result_listener = asyncio.create_task(listen_for_results(connection_id))
        
        # Keep connection alive and handle messages
        while True:
            try:
                # Wait for message from client
                data = await websocket.receive_json()
                # logger.info(f"📨 Received from {connection_id}: {data.get('action')}")
                
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
                # logger.info(f"Client {connection_id} disconnected")
                break
            except Exception as e:
                logger.error(f"Error in WebSocket loop: {e}", exc_info=True)
                break
    
    finally:
        # Clean up
        result_listener.cancel()
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
        
        # Send to queue
        success = await queue_service.send_job(job_data)
        
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

async def listen_for_results(connection_id: str):
    """Listen for results from Redis and push to WebSocket"""
    # logger.info(f"🎧 Started result listener for {connection_id}")
    
    try:
        while True:
            # Check for results for jobs associated with this connection
            jobs = [job_id for job_id, conn_id in connection_manager.job_connections.items() 
                    if conn_id == connection_id]
            
            for job_id in jobs:
                # Check Redis for result
                result_data = redis_service.get(f"result:{job_id}")
                
                if result_data:
                    try:
                        result = json.loads(result_data)
                        
                        # Send result to client
                        if result.get('success'):
                            await connection_manager.send_to_job(job_id, {
                                "type": "job_completed",
                                "job_id": job_id,
                                "result": {
                                    "success": True,
                                    "output": result.get('output', ''),
                                    "execution_time": result.get('execution_time')
                                }
                            })
                        else:
                            await connection_manager.send_to_job(job_id, {
                                "type": "job_failed",
                                "job_id": job_id,
                                "error": result.get('error', 'Unknown error')
                            })
                        
                        # Clean up
                        redis_service.delete(f"result:{job_id}")
                        if job_id in connection_manager.job_connections:
                            del connection_manager.job_connections[job_id]
                        
                    except Exception as e:
                        logger.error(f"Error processing result for {job_id}: {e}")
            
            # Sleep briefly
            await asyncio.sleep(0.5)
            
    except asyncio.CancelledError:
        logger.info(f"Result listener cancelled for {connection_id}")
    except Exception as e:
        logger.error(f"Error in result listener: {e}", exc_info=True)

