"""
Hybrid Worker: Multiprocessing + Asyncio
Combines the benefits of both for optimal performance

Each worker process runs its own asyncio event loop with multiple tasks.
This gives you:
- True parallelism (multiprocessing bypasses GIL)
- Concurrent execution within each process (asyncio)

Configuration via environment variables:
    USE_QUEUE=false (default) - In-memory queue (development)
    USE_QUEUE=true            - AWS SQS queue (production)
    
    REDIS_URL=redis://...     - Real Redis (production)
    (empty)                   - In-memory Redis (development)

Usage:
    # Development mode (in-memory)
    python worker_hybrid.py --processes 2 --tasks-per-process 3
    
    # Production mode (AWS SQS + Redis)
    export USE_QUEUE=true
    export REDIS_URL=redis://localhost:6379
    export SQS_QUEUE_URL=https://sqs...
    python worker_hybrid.py --processes 4 --tasks-per-process 5
"""

import asyncio
import multiprocessing
import logging
import signal
import sys
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)

from app.queue_service import queue_service
from app.redis_service import redis_service
from app.executors import execute_code

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [PID:%(process)d] - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class HybridWorker:
    """
    A single worker process that runs multiple asyncio tasks
    """
    
    def __init__(self, process_id: int, tasks_per_process: int = 5):
        self.process_id = process_id
        self.tasks_per_process = tasks_per_process
        self.running = True
        
    async def worker_task(self, task_id: int):
        """
        Single asyncio task that processes jobs from queue
        """
        worker_name = f"Process-{self.process_id}-Task-{task_id}"
        # logger.info(f"SUCCESS: {worker_name} started")
        
        while self.running:
            try:
                # Get job from queue (non-blocking with timeout)
                job_data = await asyncio.wait_for(
                    asyncio.to_thread(queue_service.dequeue),
                    timeout=1.0
                )
                
                if not job_data:
                    await asyncio.sleep(0.1)
                    continue
                
                job_id = job_data.get('job_id')
                code = job_data.get('code')
                language = job_data.get('language')
                input_data = job_data.get('input', '')
                
                # logger.info(f"PROCESSING: {worker_name} processing {job_id}")
                
                # Execute code (this is CPU-intensive, runs in thread pool)
                from datetime import datetime
                start_time = datetime.now()
                result = await asyncio.to_thread(
                    execute_code,
                    code,
                    language,
                    input_data
                )
                end_time = datetime.now()
                
                execution_time = (end_time - start_time).total_seconds()
                
                # Add metadata to result
                result['job_id'] = job_id
                result['status'] = 'completed'
                result['execution_time'] = execution_time
                
                # Store result in Redis (5 minute expiry)
                import json
                await asyncio.to_thread(
                    redis_service.set,
                    f"result:{job_id}",
                    json.dumps(result),
                    300  # 5 minutes expiry
                )
                
                # logger.info(f"SUCCESS: {worker_name} completed {job_id} in {execution_time:.2f}s")
                
            except asyncio.TimeoutError:
                # No job available, continue
                continue
            except Exception as e:
                logger.error(f"ERROR: {worker_name} error: {e}", exc_info=True)
                
                # Store error result if we have a job_id
                if 'job_id' in locals() and job_id:
                    error_result = {
                        "job_id": job_id,
                        "status": "failed",
                        "success": False,
                        "output": "",
                        "error": str(e)
                    }
                    try:
                        import json
                        await asyncio.to_thread(
                            redis_service.set,
                            f"result:{job_id}",
                            json.dumps(error_result),
                            300  # 5 minutes expiry
                        )
                    except Exception as store_error:
                        logger.error(f"Failed to store error result: {store_error}")
                
                await asyncio.sleep(1)
    
    async def run(self):
        """
        Start multiple asyncio tasks in this process
        """
        # logger.info(f"STARTING: Process-{self.process_id} starting with {self.tasks_per_process} tasks")
        
        # Create multiple concurrent tasks
        tasks = [
            asyncio.create_task(self.worker_task(task_id))
            for task_id in range(self.tasks_per_process)
        ]
        
        # Wait for all tasks (runs forever until interrupted)
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            # logger.info(f"Process-{self.process_id} shutting down...")
            self.running = False


def worker_process_entry(process_id: int, tasks_per_process: int):
    """
    Entry point for each worker process
    Creates its own asyncio event loop
    """
    # Handle graceful shutdown
    def signal_handler(sig, frame):
        # logger.info(f"Process-{process_id} received shutdown signal")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create new event loop for this process
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Create and run worker
    worker = HybridWorker(process_id, tasks_per_process)
    
    try:
        loop.run_until_complete(worker.run())
    except KeyboardInterrupt:
        # logger.info(f"Process-{process_id} interrupted")
    finally:
        loop.close()


class WorkerPool:
    """
    Manages multiple worker processes
    """
    
    def __init__(self, num_processes: int = 4, tasks_per_process: int = 5):
        self.num_processes = num_processes
        self.tasks_per_process = tasks_per_process
        self.processes = []
        
        # Get configuration from environment
        self.use_queue = os.getenv('USE_QUEUE', 'false').lower() == 'true'
        self.redis_url = os.getenv('REDIS_URL', '')
        self.sqs_queue_url = os.getenv('SQS_QUEUE_URL', '')
        
        # Calculate total worker capacity
        total_workers = num_processes * tasks_per_process
        
        # Display configuration
        # logger.info("=" * 70)
        # logger.info("HYBRID WORKER POOL CONFIGURATION")
        # logger.info("=" * 70)
        # logger.info(f"CONFIG: Worker Processes: {num_processes}")
        # logger.info(f"CONFIG: Tasks per Process: {tasks_per_process}")
        # logger.info(f"CONFIG: Total Concurrent Workers: {total_workers}")
        # logger.info(f"INFO: CPU Cores Available: {multiprocessing.cpu_count()}")
        # logger.info("─" * 70)
        
        # Queue configuration
        if self.use_queue:
            # logger.info("CONFIG: Queue Mode: AWS SQS (Production)")
            # logger.info(f"   SQS URL: {self.sqs_queue_url[:50]}..." if self.sqs_queue_url else "   WARNING: SQS_QUEUE_URL not set!")
        else:
            # logger.info("CONFIG: Queue Mode: In-Memory (Development)")
        
        # Redis configuration  
        if self.redis_url:
            # logger.info("CONFIG: Redis Mode: Real Redis (Production)")
            # logger.info(f"   Redis URL: {self.redis_url.split('@')[0]}@***")
        else:
            # logger.info("CONFIG: Redis Mode: In-Memory (Development)")
        
        # logger.info("=" * 70)
        
        # Validate production configuration
        if self.use_queue and not self.sqs_queue_url:
            logger.warning("WARNING: USE_QUEUE=true but SQS_QUEUE_URL is not set!")
            logger.warning("WARNING: Workers will try to use SQS but may fail!")
        
        if self.redis_url and not self.use_queue:
            # logger.info("INFO: Redis URL set but USE_QUEUE=false (Redis will be used)")
        
        if self.use_queue and not self.redis_url:
            logger.warning("WARNING: USE_QUEUE=true but REDIS_URL is not set!")
            logger.warning("WARNING: Using in-memory Redis (results may be lost!)")
    
    def start(self):
        """
        Start all worker processes
        """
        # logger.info(f"STARTING: Starting {self.num_processes} worker processes...")
        
        for i in range(self.num_processes):
            process = multiprocessing.Process(
                target=worker_process_entry,
                args=(i, self.tasks_per_process),
                name=f"Worker-{i}"
            )
            process.start()
            self.processes.append(process)
            # logger.info(f"SUCCESS: Started Worker-{i} (PID: {process.pid})")
        
        # logger.info(f"SUCCESS: All {self.num_processes} worker processes are running!")
    
    def wait(self):
        """
        Wait for all processes to complete
        """
        try:
            for process in self.processes:
                process.join()
        except KeyboardInterrupt:
            # logger.info("🛑 Shutting down worker pool...")
            self.stop()
    
    def stop(self):
        """
        Gracefully stop all worker processes
        """
        # logger.info("🛑 Stopping all worker processes...")
        
        for process in self.processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
                
                if process.is_alive():
                    logger.warning(f"Force killing {process.name}")
                    process.kill()
        
        # logger.info("SUCCESS: All workers stopped")


def validate_environment():
    """
    Validate environment configuration and provide helpful warnings
    """
    use_queue = os.getenv('USE_QUEUE', 'false').lower() == 'true'
    redis_url = os.getenv('REDIS_URL', '')
    sqs_queue_url = os.getenv('SQS_QUEUE_URL', '')
    
    # logger.info("")
    # logger.info("🔍 Environment Configuration Check:")
    # logger.info("─" * 70)
    
    # Check USE_QUEUE
    # logger.info(f"   USE_QUEUE: {os.getenv('USE_QUEUE', 'false')} {'(Production Mode)' if use_queue else '(Development Mode)'}")
    
    # Check Redis
    if redis_url:
        # logger.info(f"   REDIS_URL: Configured")
    else:
        if use_queue:
            logger.warning(f"   REDIS_URL: WARNING - Not set (using in-memory)")
        else:
            # logger.info(f"   REDIS_URL: Not set (in-memory mode)")
    
    # Check SQS
    if use_queue:
        if sqs_queue_url:
            # logger.info(f"   SQS_QUEUE_URL: Configured")
        else:
            logger.error(f"   SQS_QUEUE_URL: ERROR - REQUIRED when USE_QUEUE=true!")
            logger.error(f"   Set SQS_QUEUE_URL environment variable!")
            return False
    else:
        # logger.info(f"   SQS_QUEUE_URL: Not required (in-memory queue)")
    
    # logger.info("─" * 70)
    # logger.info("")
    
    return True


def print_usage_examples():
    """
    Print helpful usage examples
    """
    # logger.info("")
    # logger.info("USAGE EXAMPLES:")
    # logger.info("=" * 70)
    # logger.info("")
    # logger.info("Development Mode (In-Memory Queue + Redis):")
    # logger.info("   python worker_hybrid.py --processes 2 --tasks-per-process 3")
    # logger.info("")
    # logger.info("Production Mode (AWS SQS + Real Redis):")
    # logger.info("   export USE_QUEUE=true")
    # logger.info("   export REDIS_URL=redis://localhost:6379")
    # logger.info("   export SQS_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/...")
    # logger.info("   python worker_hybrid.py --processes 4 --tasks-per-process 5")
    # logger.info("")
    # logger.info("Maximum Throughput (Use all CPU cores):")
    # logger.info(f"   python worker_hybrid.py --processes {multiprocessing.cpu_count()} --tasks-per-process 5")
    # logger.info("")
    # logger.info("=" * 70)
    # logger.info("")


def main():
    """
    Main entry point
    """
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Hybrid Worker Pool - Multiprocessing + Asyncio',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment Variables:
  USE_QUEUE        Set to 'true' for AWS SQS (production), 'false' for in-memory (dev)
  REDIS_URL        Redis connection URL (e.g., redis://localhost:6379)
  SQS_QUEUE_URL    AWS SQS queue URL (required when USE_QUEUE=true)
  
Examples:
  # Development (in-memory)
  python worker_hybrid.py --processes 2 --tasks-per-process 3
  
  # Production (AWS)
  export USE_QUEUE=true
  export REDIS_URL=redis://localhost:6379
  export SQS_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/...
  python worker_hybrid.py --processes 4 --tasks-per-process 5
        """
    )
    
    parser.add_argument(
        '--processes',
        type=int,
        default=multiprocessing.cpu_count(),
        help='Number of worker processes (default: CPU count)'
    )
    parser.add_argument(
        '--tasks-per-process',
        type=int,
        default=5,
        help='Number of asyncio tasks per process (default: 5)'
    )
    parser.add_argument(
        '--show-examples',
        action='store_true',
        help='Show usage examples and exit'
    )
    
    args = parser.parse_args()
    
    # Show examples if requested
    if args.show_examples:
        print_usage_examples()
        return
    
    # Validate environment
    if not validate_environment():
        logger.error("ERROR: Environment validation failed!")
        logger.error("ERROR: Fix the configuration and try again.")
        sys.exit(1)
    
    # Create and start worker pool
    pool = WorkerPool(
        num_processes=args.processes,
        tasks_per_process=args.tasks_per_process
    )
    
    try:
        pool.start()
        pool.wait()
    except KeyboardInterrupt:
        # logger.info("Received interrupt signal")
    finally:
        pool.stop()


if __name__ == "__main__":
    # Required for Windows
    multiprocessing.freeze_support()
    main()

