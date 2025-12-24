#!/usr/bin/env python3
"""
Redis Queue Worker
Runs independently to process code execution jobs from Redis queue

Usage:
    python3 run_worker.py                    # Single worker
    python3 run_worker.py --workers 4        # Multiple workers
    python3 run_worker.py --burst            # Process existing jobs and exit
"""

import os
import sys
import argparse
from redis import Redis
from rq import Worker, Queue, Connection
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Redis connection
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

def main():
    parser = argparse.ArgumentParser(description='Run RQ worker for code execution')
    parser.add_argument('--workers', type=int, default=1, help='Number of worker processes')
    parser.add_argument('--burst', action='store_true', help='Run in burst mode (process existing jobs and exit)')
    parser.add_argument('--queue', type=str, default='code_execution', help='Queue name')
    args = parser.parse_args()
    
    print("=" * 60)
    print("🚀 Starting Redis Queue Workers")
    print("=" * 60)
    print(f"Redis URL: {REDIS_URL}")
    print(f"Queue: {args.queue}")
    print(f"Workers: {args.workers}")
    print(f"Burst mode: {args.burst}")
    print("=" * 60)
    print("")
    
    try:
        # Connect to Redis
        redis_conn = Redis.from_url(REDIS_URL)
        
        # Test connection
        redis_conn.ping()
        print("✅ Connected to Redis")
        
        # Create queue
        queue = Queue(args.queue, connection=redis_conn)
        print(f"✅ Queue '{args.queue}' ready")
        print(f"📊 Current queue size: {len(queue)}")
        print("")
        
        if args.workers == 1:
            # Single worker
            print("🔄 Starting worker...")
            with Connection(redis_conn):
                worker = Worker([queue])
                worker.work(burst=args.burst)
        else:
            # Multiple workers (fork)
            print(f"🔄 Starting {args.workers} workers...")
            from multiprocessing import Process
            
            def run_worker(worker_num):
                print(f"  Worker {worker_num} started (PID: {os.getpid()})")
                with Connection(redis_conn):
                    worker = Worker([queue], name=f'worker-{worker_num}')
                    worker.work(burst=args.burst)
            
            processes = []
            for i in range(args.workers):
                p = Process(target=run_worker, args=(i+1,))
                p.start()
                processes.append(p)
            
            # Wait for all workers
            for p in processes:
                p.join()
                
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user. Shutting down...")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()










