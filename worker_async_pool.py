"""
Enhanced Background Worker with AsyncIO Pool
Processes multiple jobs concurrently for better performance
Run this separately: python worker_async_pool.py
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

class AsyncWorkerPool:
    """
    Async worker pool that processes multiple jobs concurrently
    Similar to thread pool but using asyncio (better for async code)
    """
    
    def __init__(self, max_workers=5):
        """
        Initialize worker pool
        
        Args:
            max_workers: Number of concurrent jobs to process (default: 5)
        """
        self.max_workers = max_workers
        self.running = False
        self.jobs_processed = 0
        self.jobs_failed = 0
    
    async def process_job(self, job_data: dict):
        """
        Process a single job
        
        Args:
            job_data: Dictionary containing job information
        """
        job_id = job_data['job_id']
        language = job_data['language']
        code = job_data['code']
        input_data = job_data.get('input', '')
        
        # logger.info(f"⚙️  Processing job {job_id} (language: {language})")
        
        try:
            # Execute code
            start_time = datetime.now()
            result = await execute_code(language, code, input_data)
            end_time = datetime.now()
            
            execution_time = (end_time - start_time).total_seconds()
            
            # Add job metadata
            result['job_id'] = job_id
            result['status'] = 'completed'
            result['execution_time'] = execution_time
            
            # Store result in Redis (5 minute expiry)
            redis_service.set(
                f"result:{job_id}",
                json.dumps(result),
                expiry=300
            )
            
            self.jobs_processed += 1
            # logger.info(f"✅ Job {job_id} completed in {execution_time:.2f}s (Total: {self.jobs_processed})")
            
        except Exception as e:
            self.jobs_failed += 1
            logger.error(f"❌ Job {job_id} failed: {e}", exc_info=True)
            
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
    
    async def worker(self, worker_id: int):
        """
        Single worker coroutine that continuously processes jobs
        
        Args:
            worker_id: Unique identifier for this worker
        """
        # logger.info(f"🔧 Worker-{worker_id} started and ready")
        
        while self.running:
            try:
                # Fetch job from queue
                job_data = await queue_service.receive_job()
                
                if job_data:
                    # logger.info(f"📋 Worker-{worker_id} picked up job {job_data['job_id']}")
                    await self.process_job(job_data)
                else:
                    # No jobs available, wait briefly before trying again
                    await asyncio.sleep(1)
                    
            except Exception as e:
                logger.error(f"❌ Worker-{worker_id} error: {e}", exc_info=True)
                await asyncio.sleep(5)
        
        # logger.info(f"🛑 Worker-{worker_id} stopped")
    
    async def start(self):
        """
        Start all workers in the pool
        Workers will run concurrently and process jobs independently
        """
        # logger.info("=" * 60)
        # logger.info(f"🚀 Starting AsyncIO Worker Pool")
        # logger.info(f"   Workers: {self.max_workers}")
        # logger.info(f"   Mode: Concurrent processing")
        # logger.info("=" * 60)
        
        self.running = True
        
        # Create multiple worker coroutines
        workers = [
            asyncio.create_task(self.worker(i), name=f"Worker-{i}")
            for i in range(self.max_workers)
        ]
        
        # logger.info(f"✅ {self.max_workers} workers started successfully")
        
        # Wait for all workers (runs forever until stopped)
        try:
            await asyncio.gather(*workers, return_exceptions=True)
        except Exception as e:
            logger.error(f"Worker pool error: {e}", exc_info=True)
    
    async def stop(self):
        """
        Gracefully stop all workers
        """
        # logger.info("🛑 Stopping worker pool...")
        self.running = False
        
        # Give workers time to finish current jobs
        await asyncio.sleep(2)
        
        # logger.info("=" * 60)
        # logger.info("📊 Worker Pool Statistics:")
        # logger.info(f"   Jobs Processed: {self.jobs_processed}")
        # logger.info(f"   Jobs Failed: {self.jobs_failed}")
        # logger.info(f"   Success Rate: {(self.jobs_processed / max(1, self.jobs_processed + self.jobs_failed)) * 100:.1f}%")
        # logger.info("=" * 60)
        # logger.info("✅ Worker pool stopped gracefully")


async def main():
    """
    Main entry point for the worker pool
    """
    # Auto-detect optimal worker count based on instance type
    # Or set via MAX_WORKERS environment variable
    try:
        from worker_config import get_optimal_worker_count
        max_workers = get_optimal_worker_count()
    except ImportError:
        max_workers = 5
        logger.warning("⚠️  worker_config.py not found, using default: 5 workers")
    
    pool = AsyncWorkerPool(max_workers=max_workers)
    
    try:
        await pool.start()
    except KeyboardInterrupt:
        # logger.info("\n⚠️  Received shutdown signal...")
        await pool.stop()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutdown complete")

