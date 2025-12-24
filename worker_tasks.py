"""
Worker Tasks for Redis Queue
This file contains the actual task functions that workers execute
"""

import asyncio
import sys
from typing import Dict, Any

def execute_code_task(job_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute code task (runs in worker process)
    
    Args:
        job_data: Dict with language, code, stdin
        
    Returns:
        Dict with output, error, exit_code
    """
    # Import executors
    from app.executors import (
        execute_python,
        execute_javascript,
        execute_cpp,
        execute_java,
        execute_c,
        execute_go,
        execute_rust
    )
    
    language = job_data.get('language', '').lower()
    code = job_data.get('code', '')
    stdin = job_data.get('stdin', '')
    
    # Language executor mapping
    executors = {
        'python': execute_python,
        'javascript': execute_javascript,
        'cpp': execute_cpp,
        'c++': execute_cpp,
        'java': execute_java,
        'c': execute_c,
        'go': execute_go,
        'rust': execute_rust
    }
    
    executor = executors.get(language)
    
    if not executor:
        return {
            "output": "",
            "error": f"Unsupported language: {language}",
            "exit_code": 1
        }
    
    try:
        # Run the executor (async function)
        if asyncio.iscoroutinefunction(executor):
            # Create new event loop for this worker
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(executor(code, stdin))
            finally:
                loop.close()
        else:
            # Sync executor
            result = executor(code, stdin)
        
        return result
        
    except Exception as e:
        return {
            "output": "",
            "error": f"Execution error: {str(e)}",
            "exit_code": 1
        }










