#!/usr/bin/env python3
"""
Simple Load Test: 200 Concurrent Jobs
Tests the worker queue system by directly submitting jobs
"""
import asyncio
import time
import statistics
from datetime import datetime
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.queue_service import queue_service
from app.redis_service import redis_service
import uuid


class SimpleLoadTest:
    """Simple load test that submits jobs to queue"""
    
    def __init__(self, num_jobs=200):
        self.num_jobs = num_jobs
        self.results = []
        self.start_time = None
        self.end_time = None
    
    async def submit_job(self, job_id, language, code):
        """Submit a job to the queue"""
        start_time = time.time()
        
        try:
            # Submit job to queue
            await queue_service.send_job({
                "job_id": job_id,
                "language": language,
                "code": code,
                "input": ""
            })
            
            # Wait for result in Redis (with timeout)
            timeout = 120  # 2 minutes
            poll_interval = 0.5
            elapsed = 0
            
            while elapsed < timeout:
                result = redis_service.get(f"result:{job_id}")
                
                if result:
                    response_time = time.time() - start_time
                    self.results.append({
                        'job_id': job_id,
                        'success': True,
                        'response_time': response_time
                    })
                    return True, response_time
                
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval
            
            # Timeout
            response_time = time.time() - start_time
            self.results.append({
                'job_id': job_id,
                'success': False,
                'response_time': response_time,
                'error': 'Timeout'
            })
            return False, response_time
        
        except Exception as e:
            response_time = time.time() - start_time
            self.results.append({
                'job_id': job_id,
                'success': False,
                'response_time': response_time,
                'error': str(e)
            })
            return False, response_time
    
    async def run(self):
        """Run the load test"""
        print("\n" + "="*70)
        print("🚀 SIMPLE LOAD TEST - 200 CONCURRENT JOBS")
        print("="*70)
        print(f"\nConfiguration:")
        print(f"  Total Jobs: {self.num_jobs}")
        print(f"  Queue Type: {'SQS' if queue_service.use_sqs else 'In-Memory'}")
        print(f"  Redis Type: {'Redis' if redis_service.use_redis else 'In-Memory'}")
        print("\n" + "="*70)
        print("\n🔄 Submitting jobs...\n")
        
        self.start_time = time.time()
        
        # Sample codes
        codes = {
            'python': 'numbers = [1, 2, 3, 4, 5]\nresult = sum(numbers)\nprint(result)',
            'javascript': 'const numbers = [1, 2, 3, 4, 5];\nconst result = numbers.reduce((a, b) => a + b, 0);\nconsole.log(result);',
            'cpp': '#include <iostream>\nusing namespace std;\n\nint main() {\n    int sum = 0;\n    for(int i = 1; i <= 5; i++) {\n        sum += i;\n    }\n    cout << sum << endl;\n    return 0;\n}'
        }
        
        languages = list(codes.keys())
        
        # Create tasks
        tasks = []
        for i in range(self.num_jobs):
            job_id = f"load_test_{uuid.uuid4().hex[:8]}"
            language = languages[i % len(languages)]
            code = codes[language]
            
            task = self.submit_job(job_id, language, code)
            tasks.append(task)
        
        # Run all jobs concurrently
        results = await asyncio.gather(*tasks)
        
        self.end_time = time.time()
        
        # Print results as they come
        for i, (success, response_time) in enumerate(results, 1):
            status = "✅" if success else "❌"
            print(f"{status} Job {i:3d}: {response_time:6.2f}s")
        
        # Print summary
        self.print_summary()
    
    def print_summary(self):
        """Print test summary"""
        if not self.results:
            print("❌ No results to display")
            return
        
        total = len(self.results)
        successful = sum(1 for r in self.results if r['success'])
        failed = total - successful
        
        response_times = [r['response_time'] for r in self.results if r['success']]
        
        print("\n" + "="*70)
        print("📊 LOAD TEST SUMMARY")
        print("="*70)
        print(f"\n⏱️  Test Duration: {self.end_time - self.start_time:.2f} seconds")
        print(f"\n📦 Jobs:")
        print(f"   Total:      {total}")
        print(f"   Successful: {successful} ✅")
        print(f"   Failed:     {failed} {'❌' if failed > 0 else '✅'}")
        print(f"   Success Rate: {(successful/total)*100:.1f}%")
        
        if response_times:
            print(f"\n⚡ Response Times:")
            print(f"   Fastest:  {min(response_times):.2f}s")
            print(f"   Slowest:  {max(response_times):.2f}s")
            print(f"   Average:  {statistics.mean(response_times):.2f}s")
            print(f"   Median:   {statistics.median(response_times):.2f}s")
            
            # Percentiles
            sorted_times = sorted(response_times)
            p50 = sorted_times[int(len(sorted_times) * 0.50)]
            p90 = sorted_times[int(len(sorted_times) * 0.90)]
            p95 = sorted_times[int(len(sorted_times) * 0.95)]
            
            print(f"\n📈 Percentiles:")
            print(f"   P50: {p50:.2f}s")
            print(f"   P90: {p90:.2f}s")
            print(f"   P95: {p95:.2f}s")
            
            # User experience
            excellent = sum(1 for t in response_times if t < 5)
            good = sum(1 for t in response_times if 5 <= t < 15)
            acceptable = sum(1 for t in response_times if 15 <= t < 30)
            slow = sum(1 for t in response_times if t >= 30)
            
            print(f"\n😊 User Experience:")
            print(f"   Excellent (< 5s):    {excellent:3d} ({excellent/successful*100:5.1f}%) ⭐⭐⭐⭐⭐")
            print(f"   Good (5-15s):        {good:3d} ({good/successful*100:5.1f}%) ⭐⭐⭐⭐")
            print(f"   Acceptable (15-30s): {acceptable:3d} ({acceptable/successful*100:5.1f}%) ⭐⭐⭐")
            print(f"   Slow (> 30s):        {slow:3d} ({slow/successful*100:5.1f}%) ⭐⭐")
            
            # Throughput
            duration = self.end_time - self.start_time
            throughput = successful / duration
            print(f"\n🚀 Throughput:")
            print(f"   Jobs/second: {throughput:.2f}")
            print(f"   Jobs/minute: {throughput * 60:.2f}")
        
        # Recommendations
        print("\n💡 Analysis:")
        avg_time = statistics.mean(response_times) if response_times else 0
        
        if avg_time < 10:
            print("   ✅ Excellent performance!")
            print("   Your system is handling the load very well.")
        elif avg_time < 30:
            print("   ⚠️  Acceptable performance.")
            print("   Consider adding more workers for better response times.")
        else:
            print("   ❌ Slow performance!")
            print("   Recommendations:")
            print("      - Add more workers (./start_workers.sh 10)")
            print("      - Use horizontal scaling (17× t2.micro)")
            print("      - Check if workers are running properly")
        
        print("\n" + "="*70 + "\n")


if __name__ == '__main__':
    print("\n" + "="*70)
    print("  SIMPLE LOAD TEST - 200 CONCURRENT JOBS")
    print("="*70)
    print("\nThis test submits 200 jobs directly to the queue system")
    print("and measures how long it takes for workers to process them.")
    print("\n" + "="*70)
    
    # Get number of jobs from command line
    num_jobs = 200
    if len(sys.argv) > 1:
        try:
            num_jobs = int(sys.argv[1])
        except ValueError:
            print(f"Invalid number: {sys.argv[1]}, using default: 200")
    
    print(f"\nStarting test with {num_jobs} jobs in 2 seconds...")
    time.sleep(2)
    
    # Run test
    test = SimpleLoadTest(num_jobs=num_jobs)
    asyncio.run(test.run())










