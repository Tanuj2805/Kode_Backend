import asyncio
import tempfile
import os
import sys
import shutil
import uuid
import logging
from datetime import datetime
from pathlib import Path

# Configure logging
log_dir = Path("/var/log/kodecompiler")
log_dir.mkdir(exist_ok=True, parents=True)

# Create logger
executor_logger = logging.getLogger('executor')
executor_logger.setLevel(logging.DEBUG)

# File handler - detailed logs
log_file = log_dir / "executor.log"
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter(
    '%(asctime)s | %(levelname)-8s | %(funcName)-20s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
file_handler.setFormatter(file_formatter)

# Error file handler - errors only
error_log_file = log_dir / "executor_errors.log"
error_handler = logging.FileHandler(error_log_file)
error_handler.setLevel(logging.ERROR)
error_formatter = logging.Formatter(
    '%(asctime)s | %(levelname)s | %(funcName)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
error_handler.setFormatter(error_formatter)

# Add handlers if not already added
if not executor_logger.handlers:
    executor_logger.addHandler(file_handler)
    executor_logger.addHandler(error_handler)

# Windows-specific fix for subprocess execution
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

def limit_output(output: str, max_lines: int = 300) -> str:
    """Limit output to specified number of lines for performance"""
    if not output:
        return output
    
    lines = output.split('\n')
    if len(lines) > max_lines:
        truncated_output = '\n'.join(lines[:max_lines])
        truncated_output += f"\n\n{'='*60}\n"
        truncated_output += f"⚠️  OUTPUT TRUNCATED\n"
        truncated_output += f"{'='*60}\n"
        truncated_output += f"Showing first {max_lines} lines out of {len(lines)} total lines.\n"
        truncated_output += f"Output truncated for performance reasons.\n"
        truncated_output += f"{'='*60}"
        return truncated_output
    
    return output

async def execute_code_generic(code: str, input_data: str, command: list, filename: str, prefix: str) -> dict:
    """Generic executor for running code with logging and race condition prevention"""
    
    execution_id = str(uuid.uuid4())[:8]
    # executor_logger.info(f"[{execution_id}] Starting execution: {command[0]} | file={filename}")
    
    # Windows-specific: Ensure we have the correct event loop
    if sys.platform == 'win32':
        try:
            loop = asyncio.get_running_loop()
            # executor_logger.debug(f"[{execution_id}] Windows loop: {loop.__class__.__name__}")
        except RuntimeError:
            pass
    
    # Use unique temp directory to prevent race conditions
    temp_dir = tempfile.mkdtemp(prefix=f"{prefix}{execution_id}_")
    code_file = os.path.join(temp_dir, filename)
    # executor_logger.debug(f"[{execution_id}] Created temp dir: {temp_dir}")
    
    try:
        # Write code to file
        with open(code_file, 'w', encoding='utf-8') as f:
            f.write(code)
        # executor_logger.debug(f"[{execution_id}] Code written to: {code_file}")
        
        # Windows fix: Verify event loop before subprocess
        if sys.platform == 'win32':
            loop = asyncio.get_running_loop()
            if loop.__class__.__name__ != 'ProactorEventLoop':
                error_msg = f"Wrong loop type: {loop.__class__.__name__}"
                executor_logger.error(f"[{execution_id}] {error_msg}")
                return {
                    "success": False,
                    "output": "",
                    "error": f"Windows subprocess error: {error_msg}"
                }
        
        # Create process
        process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=temp_dir
        )
        
        # executor_logger.debug(f"[{execution_id}] Process started: PID={process.pid}")
        
        # Send input and get output with timeout
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(input=input_data.encode('utf-8')),
                timeout=10.0
            )
            # executor_logger.debug(f"[{execution_id}] Process completed: returncode={process.returncode}")
        except asyncio.TimeoutError:
            executor_logger.warning(f"[{execution_id}] Execution timeout")
            process.kill()
            await process.wait()
            return {
                "success": False,
                "output": "",
                "error": "Execution timeout (10 seconds)"
            }
        except (RuntimeError, BrokenPipeError) as e:
            # Handle cases where stdin is closed before input is written
            executor_logger.error(f"[{execution_id}] Process stdin closed: {type(e).__name__}")
            # Try to get any output that was produced
            try:
                await process.wait()
                # Read any available output
                if process.stdout:
                    stdout = await process.stdout.read()
                else:
                    stdout = b""
                if process.stderr:
                    stderr = await process.stderr.read()
                else:
                    stderr = b""
            except Exception:
                stdout, stderr = b"", b""
            
            stdout_text = stdout.decode('utf-8', errors='replace').strip()
            stderr_text = stderr.decode('utf-8', errors='replace').strip()
            
            return {
                "success": False,
                "output": stdout_text,
                "error": stderr_text or "Process terminated unexpectedly (stdin closed)"
            }
        
        # Process results
        stdout_text = stdout.decode('utf-8', errors='replace').strip()
        stderr_text = stderr.decode('utf-8', errors='replace').strip()
        
        if process.returncode == 0:
            # executor_logger.info(f"[{execution_id}] [OK] Execution successful | output_len={len(stdout_text)}")
            return {
                "success": True,
                "output": limit_output(stdout_text) or "Code executed successfully",
                "error": None
            }
        else:
            executor_logger.warning(f"[{execution_id}] Execution failed: returncode={process.returncode}")
            return {
                "success": False,
                "output": limit_output(stdout_text),
                "error": stderr_text or "Execution failed"
            }
            
    except FileNotFoundError as e:
        compiler_name = command[0] if command else "compiler"
        error_msg = f"{compiler_name} not installed"
        executor_logger.error(f"[{execution_id}] {error_msg}")
        return {
            "success": False,
            "output": "",
            "error": f"ERROR: {compiler_name} is not installed on this system.\n\nTo use this language, please install {compiler_name} first.\nSee LANGUAGE_REQUIREMENTS.md for installation instructions."
        }
    except Exception as e:
        import traceback
        error_detail = f"{type(e).__name__}: {str(e) or 'No message'}"
        error_trace = traceback.format_exc()
        executor_logger.error(f"[{execution_id}] Exception: {error_detail}\n{error_trace}")
        return {
            "success": False,
            "output": "",
            "error": error_detail
        }
    finally:
        # Small delay to ensure file handles are released
        await asyncio.sleep(0.05)
        
        # Cleanup with retry
        for attempt in range(3):
            try:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    # executor_logger.debug(f"[{execution_id}] Cleaned up: {temp_dir}")
                break
            except Exception as e:
                if attempt < 2:
                    await asyncio.sleep(0.1)
                else:
                    executor_logger.warning(f"[{execution_id}] Cleanup failed: {temp_dir} - {e}")

async def execute_python(code: str, input_data: str = "") -> dict:
    """Execute Python code"""
    import sys
    python_exe = sys.executable
    return await execute_code_generic(
        code, input_data,
        [python_exe, 'code.py'],
        'code.py',
        'pycode_'
    )

async def execute_javascript(code: str, input_data: str = "") -> dict:
    """Execute JavaScript/Node.js code"""
    return await execute_code_generic(
        code, input_data,
        ['node', 'code.js'],
        'code.js',
        'jscode_'
    )

async def execute_java(code: str, input_data: str = "") -> dict:
    """Execute Java code with improved error handling"""
    execution_id = str(uuid.uuid4())[:8]
    # executor_logger.info(f"[{execution_id}] Starting Java execution")
    
    temp_dir = tempfile.mkdtemp(prefix=f"javacode_{execution_id}_")
    
    # Extract class name from code
    class_name = "Main"
    for line in code.split('\n'):
        if 'public class' in line:
            parts = line.split('public class')[1].strip().split()
            if parts:
                class_name = parts[0].replace('{', '').strip()
            break
    
    # executor_logger.debug(f"[{execution_id}] Java class: {class_name}")
    code_file = os.path.join(temp_dir, f"{class_name}.java")
    
    try:
        # Write code to file
        with open(code_file, 'w', encoding='utf-8') as f:
            f.write(code)
        
        # Compile
        compile_process = await asyncio.create_subprocess_exec(
            'javac', f"{class_name}.java",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=temp_dir
        )
    except FileNotFoundError:
        executor_logger.error(f"[{execution_id}] javac not found")
        return {
            "success": False,
            "output": "",
            "error": "ERROR: Java compiler (javac) is not installed.\n\nInstall Java Development Kit (JDK) to use Java.\nSee LANGUAGE_REQUIREMENTS.md for instructions."
        }
    
    try:
        stdout, stderr = await asyncio.wait_for(
            compile_process.communicate(),
            timeout=10.0
        )
        
        if compile_process.returncode != 0:
            executor_logger.warning(f"[{execution_id}] Java compilation failed")
            return {
                "success": False,
                "output": "",
                "error": f"Compilation error:\n{stderr.decode('utf-8', errors='replace')}"
            }
        
        # Run
        run_process = await asyncio.create_subprocess_exec(
            'java', class_name,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=temp_dir
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(
                run_process.communicate(input=input_data.encode('utf-8')),
                timeout=10.0
            )
        except asyncio.TimeoutError:
            run_process.kill()
            await run_process.wait()
            executor_logger.warning(f"[{execution_id}] Java execution timeout")
            return {
                "success": False,
                "output": "",
                "error": "Execution timeout (10 seconds)"
            }
        except (RuntimeError, BrokenPipeError) as e:
            executor_logger.error(f"[{execution_id}] Java process stdin closed: {type(e).__name__}")
            try:
                await run_process.wait()
                stdout = await run_process.stdout.read() if run_process.stdout else b""
                stderr = await run_process.stderr.read() if run_process.stderr else b""
            except Exception:
                stdout, stderr = b"", b""
            
            stdout_text = stdout.decode('utf-8', errors='replace').strip()
            stderr_text = stderr.decode('utf-8', errors='replace').strip()
            return {
                "success": False,
                "output": stdout_text,
                "error": stderr_text or "Process terminated unexpectedly (stdin closed)"
            }
        
        stdout_text = stdout.decode('utf-8', errors='replace').strip()
        stderr_text = stderr.decode('utf-8', errors='replace').strip()
        
        if run_process.returncode == 0:
            # executor_logger.info(f"[{execution_id}] [OK] Java execution successful")
            return {
                "success": True,
                "output": limit_output(stdout_text) or "Code executed successfully",
                "error": None
            }
        else:
            executor_logger.warning(f"[{execution_id}] Java execution failed: {run_process.returncode}")
            return {
                "success": False,
                "output": limit_output(stdout_text),
                "error": stderr_text or "Execution failed"
            }
            
    except Exception as e:
        import traceback
        executor_logger.error(f"[{execution_id}] Java exception: {e}\n{traceback.format_exc()}")
        return {
            "success": False,
            "output": "",
            "error": f"{type(e).__name__}: {str(e) or 'Unknown error'}"
        }
    finally:
        await asyncio.sleep(0.05)
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except:
            pass

async def execute_cpp(code: str, input_data: str = "") -> dict:
    """Execute C++ code with improved error handling"""
    execution_id = str(uuid.uuid4())[:8]
    # executor_logger.info(f"[{execution_id}] Starting C++ execution")
    
    temp_dir = tempfile.mkdtemp(prefix=f"cppcode_{execution_id}_")
    code_file = os.path.join(temp_dir, "code.cpp")
    exe_file = os.path.join(temp_dir, "code.exe" if os.name == 'nt' else "code")
    
    compile_process = None
    run_process = None
    
    try:
        # Write code to file
        with open(code_file, 'w', encoding='utf-8') as f:
            f.write(code)
        
        # Compile
        compile_cmd = ['g++', 'code.cpp', '-o', 'code.exe' if os.name == 'nt' else 'code']
        try:
            compile_process = await asyncio.create_subprocess_exec(
                *compile_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=temp_dir
            )
        except FileNotFoundError:
            executor_logger.error(f"[{execution_id}] g++ not found")
            return {
                "success": False,
                "output": "",
                "error": "ERROR: C++ compiler (g++) is not installed.\n\nInstall MinGW-w64 or Visual Studio to use C++.\nSee LANGUAGE_REQUIREMENTS.md for instructions."
            }
        
        try:
            stdout, stderr = await asyncio.wait_for(
                compile_process.communicate(),
                timeout=10.0
            )
        except asyncio.TimeoutError:
            if compile_process:
                compile_process.kill()
                await compile_process.wait()
            executor_logger.warning(f"[{execution_id}] C++ compilation timeout")
            return {
                "success": False,
                "output": "",
                "error": "Compilation timeout (10 seconds)"
            }
        
        if compile_process.returncode != 0:
            executor_logger.warning(f"[{execution_id}] C++ compilation failed")
            return {
                "success": False,
                "output": "",
                "error": f"Compilation error:\n{stderr.decode('utf-8', errors='replace')}"
            }
        
        # Verify executable exists
        if not os.path.exists(exe_file):
            executor_logger.error(f"[{execution_id}] C++ executable not found")
            return {
                "success": False,
                "output": "",
                "error": "Compilation succeeded but executable not found"
            }
        
        # Make executable (Linux)
        if os.name != 'nt':
            os.chmod(exe_file, 0o755)
        
        # Run
        try:
            run_process = await asyncio.create_subprocess_exec(
                exe_file,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=temp_dir
            )
        except Exception as e:
            executor_logger.error(f"[{execution_id}] Failed to start C++ executable: {e}")
            return {
                "success": False,
                "output": "",
                "error": f"Failed to start: {type(e).__name__}: {str(e) or 'Unknown'}"
            }
        
        try:
            stdout, stderr = await asyncio.wait_for(
                run_process.communicate(input=input_data.encode('utf-8')),
                timeout=10.0
            )
        except asyncio.TimeoutError:
            if run_process:
                run_process.kill()
                await run_process.wait()
            executor_logger.warning(f"[{execution_id}] C++ execution timeout")
            return {
                "success": False,
                "output": "",
                "error": "Execution timeout (10 seconds)"
            }
        except (RuntimeError, BrokenPipeError) as e:
            executor_logger.error(f"[{execution_id}] C++ process stdin closed: {type(e).__name__}")
            try:
                await run_process.wait()
                stdout = await run_process.stdout.read() if run_process.stdout else b""
                stderr = await run_process.stderr.read() if run_process.stderr else b""
            except Exception:
                stdout, stderr = b"", b""
            
            stdout_text = stdout.decode('utf-8', errors='replace').strip()
            stderr_text = stderr.decode('utf-8', errors='replace').strip()
            return {
                "success": False,
                "output": stdout_text,
                "error": stderr_text or "Process terminated unexpectedly (stdin closed)"
            }
        
        stdout_text = stdout.decode('utf-8', errors='replace').strip()
        stderr_text = stderr.decode('utf-8', errors='replace').strip()
        
        if run_process.returncode == 0:
            # executor_logger.info(f"[{execution_id}] [OK] C++ execution successful")
            return {
                "success": True,
                "output": limit_output(stdout_text) or "Code executed successfully",
                "error": None
            }
        else:
            executor_logger.warning(f"[{execution_id}] C++ execution failed: {run_process.returncode}")
            return {
                "success": False,
                "output": limit_output(stdout_text),
                "error": stderr_text or f"Exit code {run_process.returncode}"
            }
            
    except Exception as e:
        import traceback
        error_type = type(e).__name__
        error_msg = str(e) or "No error message"
        executor_logger.error(f"[{execution_id}] C++ exception: {error_type}: {error_msg}\n{traceback.format_exc()}")
        return {
            "success": False,
            "output": "",
            "error": f"{error_type}: {error_msg}"
        }
    finally:
        # Cleanup processes
        if compile_process and compile_process.returncode is None:
            try:
                compile_process.kill()
                await compile_process.wait()
            except:
                pass
        
        if run_process and run_process.returncode is None:
            try:
                run_process.kill()
                await run_process.wait()
            except:
                pass
        
        await asyncio.sleep(0.05)
        
        for attempt in range(3):
            try:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir, ignore_errors=True)
                break
            except Exception as e:
                if attempt < 2:
                    await asyncio.sleep(0.1)

async def execute_c(code: str, input_data: str = "") -> dict:
    """Execute C code with improved error handling, logging, and race condition prevention"""
    execution_id = str(uuid.uuid4())[:8]
    # executor_logger.info(f"[{execution_id}] Starting C execution | code_len={len(code)}")
    
    # Use unique temp directory to prevent race conditions
    temp_dir = tempfile.mkdtemp(prefix=f"ccode_{execution_id}_")
    code_file = os.path.join(temp_dir, "code.c")
    exe_file = os.path.join(temp_dir, "code.exe" if os.name == 'nt' else "code")
    
    compile_process = None
    run_process = None
    
    try:
        # Write code to file
        with open(code_file, 'w', encoding='utf-8') as f:
            f.write(code)
        # executor_logger.debug(f"[{execution_id}] Code written to: {code_file}")
        
        # Compile
        compile_cmd = ['gcc', 'code.c', '-o', 'code.exe' if os.name == 'nt' else 'code']
        try:
            compile_process = await asyncio.create_subprocess_exec(
                *compile_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=temp_dir
            )
            # executor_logger.debug(f"[{execution_id}] Compilation started: PID={compile_process.pid}")
        except FileNotFoundError:
            executor_logger.error(f"[{execution_id}] gcc not found")
            return {
                "success": False,
                "output": "",
                "error": "ERROR: C compiler (gcc) is not installed.\n\nInstall MinGW-w64 or Visual Studio to use C.\nSee LANGUAGE_REQUIREMENTS.md for instructions."
            }
        
        try:
            stdout, stderr = await asyncio.wait_for(
                compile_process.communicate(),
                timeout=10.0
            )
            # executor_logger.debug(f"[{execution_id}] Compilation completed: returncode={compile_process.returncode}")
        except asyncio.TimeoutError:
            executor_logger.warning(f"[{execution_id}] Compilation timeout")
            if compile_process:
                compile_process.kill()
                await compile_process.wait()
            return {
                "success": False,
                "output": "",
                "error": "Compilation timeout (10 seconds)"
            }
        
        if compile_process.returncode != 0:
            error_msg = stderr.decode('utf-8', errors='replace')
            executor_logger.warning(f"[{execution_id}] Compilation failed: {error_msg[:100]}")
            return {
                "success": False,
                "output": "",
                "error": f"Compilation error:\n{error_msg}"
            }
        
        # Verify executable exists
        if not os.path.exists(exe_file):
            executor_logger.error(f"[{execution_id}] Executable not found: {exe_file}")
            return {
                "success": False,
                "output": "",
                "error": "Compilation succeeded but executable not found"
            }
        
        # Make executable (Linux)
        if os.name != 'nt':
            os.chmod(exe_file, 0o755)
            # executor_logger.debug(f"[{execution_id}] Set executable permissions")
        
        # Run
        try:
            run_process = await asyncio.create_subprocess_exec(
                exe_file,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=temp_dir
            )
            # executor_logger.debug(f"[{execution_id}] Execution started: PID={run_process.pid}")
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e) or 'Unknown'}"
            executor_logger.error(f"[{execution_id}] Failed to start executable: {error_msg}")
            return {
                "success": False,
                "output": "",
                "error": f"Failed to start: {error_msg}"
            }
        
        try:
            stdout, stderr = await asyncio.wait_for(
                run_process.communicate(input=input_data.encode('utf-8')),
                timeout=10.0
            )
            # executor_logger.debug(f"[{execution_id}] Execution completed: returncode={run_process.returncode}")
        except asyncio.TimeoutError:
            executor_logger.warning(f"[{execution_id}] Execution timeout")
            if run_process:
                run_process.kill()
                await run_process.wait()
            return {
                "success": False,
                "output": "",
                "error": "Execution timeout (10 seconds)"
            }
        except (RuntimeError, BrokenPipeError) as e:
            executor_logger.error(f"[{execution_id}] C process stdin closed: {type(e).__name__}")
            try:
                await run_process.wait()
                stdout = await run_process.stdout.read() if run_process.stdout else b""
                stderr = await run_process.stderr.read() if run_process.stderr else b""
            except Exception:
                stdout, stderr = b"", b""
            
            stdout_text = stdout.decode('utf-8', errors='replace').strip()
            stderr_text = stderr.decode('utf-8', errors='replace').strip()
            return {
                "success": False,
                "output": stdout_text,
                "error": stderr_text or "Process terminated unexpectedly (stdin closed)"
            }
        
        stdout_text = stdout.decode('utf-8', errors='replace').strip()
        stderr_text = stderr.decode('utf-8', errors='replace').strip()
        
        if run_process.returncode == 0:
            # executor_logger.info(f"[{execution_id}] [OK] C execution successful | output_len={len(stdout_text)}")
            return {
                "success": True,
                "output": limit_output(stdout_text) or "Code executed successfully",
                "error": None
            }
        else:
            executor_logger.warning(f"[{execution_id}] C execution failed: returncode={run_process.returncode}")
            return {
                "success": False,
                "output": limit_output(stdout_text),
                "error": stderr_text or f"Exit code {run_process.returncode}"
            }
            
    except Exception as e:
        import traceback
        error_type = type(e).__name__
        error_msg = str(e) or "No error message"
        error_trace = traceback.format_exc()
        
        executor_logger.error(f"[{execution_id}] C exception: {error_type}: {error_msg}\n{error_trace}")
        
        return {
            "success": False,
            "output": "",
            "error": f"{error_type}: {error_msg}"
        }
    finally:
        # Cleanup processes
        if compile_process and compile_process.returncode is None:
            try:
                compile_process.kill()
                await compile_process.wait()
                # executor_logger.debug(f"[{execution_id}] Killed compile process")
            except:
                pass
        
        if run_process and run_process.returncode is None:
            try:
                run_process.kill()
                await run_process.wait()
                # executor_logger.debug(f"[{execution_id}] Killed run process")
            except:
                pass
        
        # Small delay for file handles to be released
        await asyncio.sleep(0.05)
        
        # Cleanup temp dir with retry to handle race conditions
        for attempt in range(3):
            try:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    # executor_logger.debug(f"[{execution_id}] Cleaned up: {temp_dir}")
                break
            except Exception as e:
                if attempt < 2:
                    await asyncio.sleep(0.1)
                else:
                    executor_logger.warning(f"[{execution_id}] Cleanup failed: {temp_dir} - {e}")

async def execute_go(code: str, input_data: str = "") -> dict:
    """Execute Go code"""
    return await execute_code_generic(
        code, input_data,
        ['go', 'run', 'code.go'],
        'code.go',
        'gocode_'
    )

async def execute_rust(code: str, input_data: str = "") -> dict:
    """Execute Rust code"""
    execution_id = str(uuid.uuid4())[:8]
    # executor_logger.info(f"[{execution_id}] Starting Rust execution")
    
    temp_dir = tempfile.mkdtemp(prefix=f"rustcode_{execution_id}_")
    code_file = os.path.join(temp_dir, "code.rs")
    exe_file = os.path.join(temp_dir, "code.exe" if os.name == 'nt' else "code")
    
    try:
        with open(code_file, 'w', encoding='utf-8') as f:
            f.write(code)
        
        # Compile
        compile_cmd = ['rustc', 'code.rs', '-o', 'code.exe' if os.name == 'nt' else 'code']
        compile_process = await asyncio.create_subprocess_exec(
            *compile_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=temp_dir
        )
        
        stdout, stderr = await asyncio.wait_for(
            compile_process.communicate(),
            timeout=15.0
        )
        
        if compile_process.returncode != 0:
            executor_logger.warning(f"[{execution_id}] Rust compilation failed")
            return {
                "success": False,
                "output": "",
                "error": f"Compilation error:\n{stderr.decode('utf-8', errors='replace')}"
            }
        
        # Run
        run_process = await asyncio.create_subprocess_exec(
            exe_file,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=temp_dir
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(
                run_process.communicate(input=input_data.encode('utf-8')),
                timeout=10.0
            )
        except asyncio.TimeoutError:
            run_process.kill()
            await run_process.wait()
            executor_logger.warning(f"[{execution_id}] Rust execution timeout")
            return {
                "success": False,
                "output": "",
                "error": "Execution timeout (10 seconds)"
            }
        
        stdout_text = stdout.decode('utf-8', errors='replace').strip()
        stderr_text = stderr.decode('utf-8', errors='replace').strip()
        
        if run_process.returncode == 0:
            # executor_logger.info(f"[{execution_id}] [OK] Rust execution successful")
            return {
                "success": True,
                "output": limit_output(stdout_text) or "Code executed successfully",
                "error": None
            }
        else:
            executor_logger.warning(f"[{execution_id}] Rust execution failed: {run_process.returncode}")
            return {
                "success": False,
                "output": limit_output(stdout_text),
                "error": stderr_text or "Execution failed"
            }
            
    except Exception as e:
        import traceback
        executor_logger.error(f"[{execution_id}] Rust exception: {e}\n{traceback.format_exc()}")
        return {
            "success": False,
            "output": "",
            "error": f"{type(e).__name__}: {str(e) or 'Unknown error'}"
        }
    finally:
        await asyncio.sleep(0.05)
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except:
            pass

async def execute_php(code: str, input_data: str = "") -> dict:
    """Execute PHP code"""
    return await execute_code_generic(
        code, input_data,
        ['php', 'code.php'],
        'code.php',
        'phpcode_'
    )

async def execute_ruby(code: str, input_data: str = "") -> dict:
    """Execute Ruby code"""
    return await execute_code_generic(
        code, input_data,
        ['ruby', 'code.rb'],
        'code.rb',
        'rubycode_'
    )

async def execute_bash(code: str, input_data: str = "") -> dict:
    """Execute Bash script"""
    return await execute_code_generic(
        code, input_data,
        ['bash', 'code.sh'],
        'code.sh',
        'bashcode_'
    )

# Language executors mapping
EXECUTORS = {
    'python': execute_python,
    'javascript': execute_javascript,
    'java': execute_java,
    'cpp': execute_cpp,
    'c': execute_c,
    'go': execute_go,
    'rust': execute_rust,
    'php': execute_php,
    'ruby': execute_ruby,
    'bash': execute_bash,
}

async def execute_code(language: str, code: str, input_data: str = "") -> dict:
    """Main execute function that routes to appropriate executor"""
    executor = EXECUTORS.get(language)
    
    if not executor:
        executor_logger.warning(f"Unsupported language: {language}")
        return {
            "success": False,
            "output": "",
            "error": f"Language '{language}' is not supported or compiler not installed"
        }
    
    return await executor(code, input_data)

