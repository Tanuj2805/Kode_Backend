"""
Load test for 3000 simultaneous WebSocket connections
Tests scalability and performance under load
"""

import asyncio
import websockets
import json
import time
from datetime import datetime
import statistics
import argparse

# Results tracking
results = {
    'completed': 0,
    'failed': 0,
    'timeouts': 0,
    'connection_errors': 0,
    'latencies': [],
    'start_time': 0,
    'end_time': 0
}

lock = asyncio.Lock()


async def simulate_client(client_id: int, uri: str, timeout: int = 30):
    """
    Simulate a single WebSocket client
    
    Args:
        client_id: Unique client identifier
        uri: WebSocket URI to connect to
        timeout: Timeout in seconds
    """
    try:
        async with asyncio.timeout(timeout):
            async with websockets.connect(uri, ping_interval=None) as websocket:
                # Receive connection ack
                ack = await websocket.recv()
                ack_data = json.loads(ack)
                
                if ack_data.get('type') != 'connection_ack':
                    async with lock:
                        results['failed'] += 1
                    return
                
                # Send code execution request
                start_time = time.time()
                
                await websocket.send(json.dumps({
                    "action": "execute",
                    "language": "python",
                    "code": f"print('Client {client_id}')",
                    "input": ""
                }))
                
                # Wait for result
                result_received = False
                async for message in websocket:
                    data = json.loads(message)
                    
                    if data['type'] in ['job_completed', 'job_failed']:
                        end_time = time.time()
                        latency = end_time - start_time
                        
                        async with lock:
                            results['completed'] += 1
                            results['latencies'].append(latency)
                            
                            # Progress indicator
                            if results['completed'] % 100 == 0:
                                total_attempted = results['completed'] + results['failed'] + results['timeouts']
                                print(f"✅ Progress: {results['completed']}/{client_id + 1} "
                                      f"(Failed: {results['failed']}, Timeouts: {results['timeouts']})")
                        
                        result_received = True
                        break
                
                if not result_received:
                    async with lock:
                        results['failed'] += 1
    
    except asyncio.TimeoutError:
        async with lock:
            results['timeouts'] += 1
        print(f"⏱️  Client {client_id}: Timeout")
    
    except websockets.exceptions.WebSocketException as e:
        async with lock:
            results['connection_errors'] += 1
        print(f"🔌 Client {client_id}: Connection error - {e}")
    
    except Exception as e:
        async with lock:
            results['failed'] += 1
        print(f"❌ Client {client_id}: {type(e).__name__} - {e}")


async def run_load_test(num_clients: int, uri: str, ramp_up_delay: float = 0.01):
    """
    Run load test with specified number of concurrent connections
    
    Args:
        num_clients: Number of concurrent clients to simulate
        uri: WebSocket URI
        ramp_up_delay: Delay between starting clients (seconds)
    """
    print("=" * 80)
    print(f"🚀 LOAD TEST: {num_clients} Simultaneous WebSocket Connections")
    print("=" * 80)
    print(f"Target: {uri}")
    print(f"Ramp-up delay: {ramp_up_delay}s per 100 clients")
    print()
    
    results['start_time'] = time.time()
    
    # Create tasks for all clients
    tasks = []
    for i in range(num_clients):
        task = asyncio.create_task(simulate_client(i, uri))
        tasks.append(task)
        
        # Add small delay every 100 connections to avoid overwhelming the server
        if (i + 1) % 100 == 0:
            await asyncio.sleep(ramp_up_delay)
            print(f"📊 Started {i + 1}/{num_clients} clients...")
    
    print(f"📊 All {num_clients} client tasks created, waiting for completion...")
    print()
    
    # Wait for all clients to complete
    await asyncio.gather(*tasks, return_exceptions=True)
    
    results['end_time'] = time.time()
    
    # Print results
    print_results(num_clients)


def print_results(num_clients: int):
    """Print test results and statistics"""
    duration = results['end_time'] - results['start_time']
    
    print()
    print("=" * 80)
    print("📊 LOAD TEST RESULTS")
    print("=" * 80)
    
    # Connection Statistics
    print()
    print("🔌 Connection Statistics:")
    print(f"   Target Clients:        {num_clients}")
    print(f"   Successful:            {results['completed']} ({results['completed']/num_clients*100:.1f}%)")
    print(f"   Failed:                {results['failed']}")
    print(f"   Timeouts:              {results['timeouts']}")
    print(f"   Connection Errors:     {results['connection_errors']}")
    print(f"   Total Duration:        {duration:.2f}s")
    
    # Throughput
    if duration > 0:
        throughput = results['completed'] / duration
        print()
        print("⚡ Throughput:")
        print(f"   Requests/second:       {throughput:.2f}")
        print(f"   Avg time/request:      {duration/num_clients:.3f}s")
    
    # Latency Statistics
    if results['latencies']:
        latencies = sorted(results['latencies'])
        print()
        print("⏱️  Latency Statistics:")
        print(f"   Min:                   {min(latencies):.3f}s")
        print(f"   Max:                   {max(latencies):.3f}s")
        print(f"   Mean:                  {statistics.mean(latencies):.3f}s")
        print(f"   Median:                {statistics.median(latencies):.3f}s")
        
        # Percentiles
        p50_idx = int(len(latencies) * 0.50)
        p75_idx = int(len(latencies) * 0.75)
        p95_idx = int(len(latencies) * 0.95)
        p99_idx = int(len(latencies) * 0.99)
        
        print(f"   P50 (median):          {latencies[p50_idx]:.3f}s")
        print(f"   P75:                   {latencies[p75_idx]:.3f}s")
        print(f"   P95:                   {latencies[p95_idx]:.3f}s")
        print(f"   P99:                   {latencies[p99_idx]:.3f}s")
    
    # Success Rate
    print()
    success_rate = (results['completed'] / num_clients * 100) if num_clients > 0 else 0
    
    if success_rate >= 99:
        status = "✅ EXCELLENT"
    elif success_rate >= 95:
        status = "✓ GOOD"
    elif success_rate >= 90:
        status = "⚠️  ACCEPTABLE"
    else:
        status = "❌ POOR"
    
    print(f"📈 Overall Result: {status}")
    print(f"   Success Rate:          {success_rate:.2f}%")
    
    # Recommendations
    print()
    print("💡 Recommendations:")
    if success_rate < 95:
        print("   • Success rate is below 95% - consider scaling up")
        print("   • Add more backend servers or increase resources")
    if results['latencies'] and statistics.mean(results['latencies']) > 5:
        print("   • High average latency - check worker capacity")
        print("   • Consider adding more workers or optimizing code execution")
    if results['timeouts'] > num_clients * 0.05:
        print("   • High timeout rate - increase timeout or check network")
    if success_rate >= 99 and results['latencies'] and statistics.mean(results['latencies']) < 3:
        print("   • ✅ System performing well! Ready for this load.")
    
    print("=" * 80)


async def test_single_connection(uri: str):
    """Quick test with a single connection"""
    print("🧪 Testing single connection...")
    
    try:
        async with websockets.connect(uri) as websocket:
            # Receive ack
            ack = await websocket.recv()
            print(f"✅ Connected: {ack[:100]}")
            
            # Send test request
            await websocket.send(json.dumps({
                "action": "execute",
                "language": "python",
                "code": "print('Test')",
                "input": ""
            }))
            
            # Wait for response
            async for message in websocket:
                data = json.loads(message)
                print(f"📨 Received: {data.get('type')}")
                if data.get('type') in ['job_completed', 'job_failed']:
                    print("✅ Single connection test passed!")
                    return True
        
        return False
    
    except Exception as e:
        print(f"❌ Single connection test failed: {e}")
        return False


async def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='WebSocket Load Testing Tool')
    parser.add_argument('--clients', type=int, default=3000, 
                        help='Number of concurrent clients (default: 3000)')
    parser.add_argument('--uri', type=str, default='ws://localhost:5000/ws/pubsub',
                        help='WebSocket URI (default: ws://localhost:5000/ws/pubsub)')
    parser.add_argument('--ramp-up', type=float, default=0.01,
                        help='Ramp-up delay per 100 clients in seconds (default: 0.01)')
    parser.add_argument('--test-connection', action='store_true',
                        help='Test single connection first')
    
    args = parser.parse_args()
    
    # Test single connection first if requested
    if args.test_connection:
        if not await test_single_connection(args.uri):
            print("❌ Single connection test failed. Fix connection issues before load testing.")
            return
        print()
    
    # Run load test
    await run_load_test(args.clients, args.uri, args.ramp_up)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
        if results['completed'] > 0:
            print("\nPartial results:")
            print_results(results['completed'] + results['failed'] + results['timeouts'])

