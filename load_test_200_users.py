#!/usr/bin/env python3
"""
Load Test: 200 Concurrent Users
Simulates 200 users submitting code simultaneously to test system capacity
"""
import asyncio
import aiohttp
import time
import json
from datetime import datetime
import statistics

# Configuration
API_BASE_URL = "http://localhost:8000"  # Change to your API URL
NUM_USERS = 200
WEBSOCKET_URL = "ws://localhost:8000/ws"


# Sample code to execute (small, fast code)
TEST_CODE = {
    "python": """
# Simple Python code
numbers = [1, 2, 3, 4, 5]
result = sum(numbers)
print(result)
""",
    "javascript": """
// Simple JavaScript code
const numbers = [1, 2, 3, 4, 5];
const result = numbers.reduce((a, b) => a + b, 0);
console.log(result);
""",
    "cpp": """
#include <iostream>
using namespace std;

int main() {
    int sum = 0;
    for(int i = 1; i <= 5; i++) {
        sum += i;
    }
    cout << sum << endl;
    return 0;
}
"""
}


class LoadTestResults:
    """Track and display load test results"""
    def __init__(self):
        self.results = []
        self.start_time = None
        self.end_time = None
        
    def add_result(self, user_id, success, response_time, error=None):
        self.results.append({
            'user_id': user_id,
            'success': success,
            'response_time': response_time,
            'error': error,
            'timestamp': time.time()
        })
    
    def print_summary(self):
        if not self.results:
            print("❌ No results to display")
            return
        
        total_users = len(self.results)
        successful = sum(1 for r in self.results if r['success'])
        failed = total_users - successful
        
        response_times = [r['response_time'] for r in self.results if r['success']]
        
        print("\n" + "="*70)
        print("📊 LOAD TEST RESULTS - 200 CONCURRENT USERS")
        print("="*70)
        print(f"\n⏱️  Test Duration: {self.end_time - self.start_time:.2f} seconds")
        print(f"\n👥 Users:")
        print(f"   Total:      {total_users}")
        print(f"   Successful: {successful} ✅")
        print(f"   Failed:     {failed} {'❌' if failed > 0 else '✅'}")
        print(f"   Success Rate: {(successful/total_users)*100:.1f}%")
        
        if response_times:
            print(f"\n⚡ Response Times:")
            print(f"   Fastest:  {min(response_times):.2f}s")
            print(f"   Slowest:  {max(response_times):.2f}s")
            print(f"   Average:  {statistics.mean(response_times):.2f}s")
            print(f"   Median:   {statistics.median(response_times):.2f}s")
            
            # Percentiles
            sorted_times = sorted(response_times)
            p50 = sorted_times[int(len(sorted_times) * 0.50)]
            p75 = sorted_times[int(len(sorted_times) * 0.75)]
            p90 = sorted_times[int(len(sorted_times) * 0.90)]
            p95 = sorted_times[int(len(sorted_times) * 0.95)]
            p99 = sorted_times[int(len(sorted_times) * 0.99)] if len(sorted_times) > 100 else sorted_times[-1]
            
            print(f"\n📈 Percentiles:")
            print(f"   P50 (median): {p50:.2f}s")
            print(f"   P75:          {p75:.2f}s")
            print(f"   P90:          {p90:.2f}s")
            print(f"   P95:          {p95:.2f}s")
            print(f"   P99:          {p99:.2f}s")
        
        # User experience breakdown
        if response_times:
            excellent = sum(1 for t in response_times if t < 5)
            good = sum(1 for t in response_times if 5 <= t < 15)
            acceptable = sum(1 for t in response_times if 15 <= t < 30)
            slow = sum(1 for t in response_times if 30 <= t < 60)
            very_slow = sum(1 for t in response_times if t >= 60)
            
            print(f"\n😊 User Experience:")
            print(f"   Excellent (< 5s):     {excellent:3d} ({excellent/successful*100:5.1f}%) ⭐⭐⭐⭐⭐")
            print(f"   Good (5-15s):         {good:3d} ({good/successful*100:5.1f}%) ⭐⭐⭐⭐")
            print(f"   Acceptable (15-30s):  {acceptable:3d} ({acceptable/successful*100:5.1f}%) ⭐⭐⭐")
            print(f"   Slow (30-60s):        {slow:3d} ({slow/successful*100:5.1f}%) ⭐⭐")
            print(f"   Very Slow (> 60s):    {very_slow:3d} ({very_slow/successful*100:5.1f}%) ⭐")
        
        # Errors
        if failed > 0:
            print(f"\n❌ Errors:")
            error_types = {}
            for r in self.results:
                if not r['success'] and r['error']:
                    error_types[r['error']] = error_types.get(r['error'], 0) + 1
            
            for error, count in error_types.items():
                print(f"   {error}: {count}")
        
        # Throughput
        if response_times:
            duration = self.end_time - self.start_time
            throughput = successful / duration
            print(f"\n🚀 Throughput:")
            print(f"   Jobs/second: {throughput:.2f}")
            print(f"   Jobs/minute: {throughput * 60:.2f}")
        
        print("\n" + "="*70)
        
        # Recommendations
        print("\n💡 Recommendations:")
        if successful < total_users * 0.95:
            print("   ⚠️  High failure rate! Check:")
            print("      - API server is running")
            print("      - Workers are running")
            print("      - Redis/SQS are accessible")
        
        avg_time = statistics.mean(response_times) if response_times else 0
        if avg_time > 30:
            print("   ⚠️  Slow response times! Consider:")
            print("      - Adding more workers")
            print("      - Using horizontal scaling (multiple t2.micro)")
            print("      - Check queue depth")
        elif avg_time < 10:
            print("   ✅ Excellent performance! Your system is handling load well!")
        
        print("\n" + "="*70 + "\n")


async def simulate_user_websocket(user_id, language, code, results):
    """Simulate a single user submitting code via WebSocket"""
    start_time = time.time()
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(WEBSOCKET_URL) as ws:
                # Send code execution request
                await ws.send_json({
                    "type": "execute",
                    "language": language,
                    "code": code
                })
                
                # Wait for response (with timeout)
                result_received = False
                timeout = 120  # 2 minutes max
                
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        
                        if data.get('type') == 'result':
                            result_received = True
                            response_time = time.time() - start_time
                            results.add_result(user_id, True, response_time)
                            print(f"✅ User {user_id:3d}: {response_time:6.2f}s")
                            break
                        elif data.get('type') == 'error':
                            response_time = time.time() - start_time
                            results.add_result(user_id, False, response_time, data.get('message', 'Unknown error'))
                            print(f"❌ User {user_id:3d}: ERROR - {data.get('message')}")
                            break
                        elif data.get('type') == 'queue_full':
                            response_time = time.time() - start_time
                            results.add_result(user_id, False, response_time, 'Queue full')
                            print(f"⚠️  User {user_id:3d}: Queue full")
                            break
                    
                    # Timeout check
                    if time.time() - start_time > timeout:
                        results.add_result(user_id, False, timeout, 'Timeout')
                        print(f"⏱️  User {user_id:3d}: TIMEOUT")
                        break
                
                if not result_received and (time.time() - start_time < timeout):
                    results.add_result(user_id, False, time.time() - start_time, 'No response')
                    print(f"❌ User {user_id:3d}: No response")
    
    except Exception as e:
        response_time = time.time() - start_time
        results.add_result(user_id, False, response_time, str(e))
        print(f"❌ User {user_id:3d}: Exception - {str(e)[:50]}")


async def simulate_user_rest(user_id, language, code, results):
    """Simulate a single user submitting code via REST API"""
    start_time = time.time()
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{API_BASE_URL}/execute",
                json={
                    "language": language,
                    "code": code
                },
                timeout=aiohttp.ClientTimeout(total=120)
            ) as response:
                response_time = time.time() - start_time
                
                if response.status == 200:
                    data = await response.json()
                    results.add_result(user_id, True, response_time)
                    print(f"✅ User {user_id:3d}: {response_time:6.2f}s")
                else:
                    error_msg = f"HTTP {response.status}"
                    results.add_result(user_id, False, response_time, error_msg)
                    print(f"❌ User {user_id:3d}: {error_msg}")
    
    except asyncio.TimeoutError:
        response_time = time.time() - start_time
        results.add_result(user_id, False, response_time, 'Timeout')
        print(f"⏱️  User {user_id:3d}: TIMEOUT")
    
    except Exception as e:
        response_time = time.time() - start_time
        results.add_result(user_id, False, response_time, str(e))
        print(f"❌ User {user_id:3d}: Exception - {str(e)[:50]}")


async def run_load_test(use_websocket=True):
    """Run the load test"""
    print("\n" + "="*70)
    print("🚀 STARTING LOAD TEST")
    print("="*70)
    print(f"\nConfiguration:")
    print(f"  Users:      {NUM_USERS}")
    print(f"  Method:     {'WebSocket' if use_websocket else 'REST API'}")
    print(f"  API URL:    {API_BASE_URL}")
    print(f"  Languages:  Python, JavaScript, C++")
    print("\n" + "="*70)
    print("\n🔄 Launching users...\n")
    
    results = LoadTestResults()
    results.start_time = time.time()
    
    # Create tasks for all users
    tasks = []
    languages = list(TEST_CODE.keys())
    
    for user_id in range(1, NUM_USERS + 1):
        # Distribute languages evenly
        language = languages[user_id % len(languages)]
        code = TEST_CODE[language]
        
        if use_websocket:
            task = simulate_user_websocket(user_id, language, code, results)
        else:
            task = simulate_user_rest(user_id, language, code, results)
        
        tasks.append(task)
    
    # Run all users concurrently
    await asyncio.gather(*tasks)
    
    results.end_time = time.time()
    
    # Print summary
    results.print_summary()


async def check_server():
    """Check if server is running"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{API_BASE_URL}/health", timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    print("✅ Server is running!")
                    return True
    except:
        pass
    
    print("❌ Server not running!")
    print(f"\nPlease ensure your API server is running at {API_BASE_URL}")
    print("\nTo start the server:")
    print("  cd backend")
    print("  uvicorn main:app --reload")
    return False


if __name__ == '__main__':
    print("\n" + "="*70)
    print("  LOAD TEST - 200 CONCURRENT USERS")
    print("="*70)
    print("\nThis script simulates 200 users submitting code simultaneously")
    print("to test your system's capacity and performance.")
    print("\n" + "="*70)
    
    # Check if server is running
    if asyncio.run(check_server()):
        print("\nStarting test in 3 seconds...")
        time.sleep(3)
        
        # Run the load test
        asyncio.run(run_load_test(use_websocket=True))
    else:
        print("\nTest aborted. Please start the server first.")










