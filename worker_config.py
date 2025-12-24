"""
Worker Configuration
Detects instance type and sets optimal worker count automatically
"""
import os
import requests
import logging

logger = logging.getLogger(__name__)


def get_instance_type():
    """
    Detect AWS EC2 instance type from metadata service
    Returns instance type or None if not on EC2
    """
    try:
        # Try to get instance type from AWS metadata
        response = requests.get(
            'http://169.254.169.254/latest/meta-data/instance-type',
            timeout=2
        )
        if response.status_code == 200:
            return response.text
    except:
        pass
    
    # Check environment variable
    return os.getenv('INSTANCE_TYPE', None)


def get_optimal_worker_count():
    """
    Returns optimal worker count based on instance type
    """
    instance_type = get_instance_type()
    
    # Manual override from environment
    env_workers = os.getenv('MAX_WORKERS')
    if env_workers:
        try:
            return int(env_workers)
        except ValueError:
            pass
    
    # Auto-detect based on instance type
    worker_map = {
        't2.micro': 3,
        't2.small': 5,
        't2.medium': 10,
        't2.large': 15,
        't3.micro': 3,
        't3.small': 5,
        't3.medium': 10,
        't3.large': 20,
        't3.xlarge': 50,
        't3.2xlarge': 100,
        'c6i.large': 20,
        'c6i.xlarge': 40,
        'c6i.2xlarge': 100,
    }
    
    if instance_type:
        workers = worker_map.get(instance_type, 5)
        # logger.info(f"🔍 Detected instance: {instance_type}")
        # logger.info(f"⚙️  Setting {workers} workers (optimal for this instance)")
        return workers
    
    # Default
    # logger.info("⚙️  Using default: 5 workers")
    return 5


if __name__ == '__main__':
    # Test
    print(f"Instance Type: {get_instance_type()}")
    print(f"Optimal Workers: {get_optimal_worker_count()}")











