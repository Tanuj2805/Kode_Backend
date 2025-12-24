from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.openapi.utils import get_openapi
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from dotenv import load_dotenv
import os
import sys
import asyncio
import logging
import time

# Windows-specific fix for subprocess execution
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Load environment variables BEFORE importing routes (so they can access env vars)
load_dotenv(override=True)

from app.database import connect_db, close_db
from app.routes import auth, codes, execute, problems, solutions, admin, admin_problems, weekly_challenges, folders, download, websocket_routes, websocket_routes_pubsub, execute_redis, support

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# Create FastAPI app
app = FastAPI(
    title="Code Compiler Backend API",
    description="Backend API for online code compiler platform",
    version="1.0.0",
    swagger_ui_parameters={
        "persistAuthorization": True,
    },
    # FIX: Disable automatic trailing slash redirects (causing HTTP redirect issue)
    redirect_slashes=False
)

# Add rate limiter state and exception handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configure CORS
# Allow requests from multiple origins for development and production
allowed_origins = [
    "http://localhost:3000",  # React/Next.js dev server
    "http://localhost:3001",
    "http://localhost:5173",  # Vite dev server
    "http://localhost:8000",  # Alternative frontend
    "http://localhost:8080",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]

# Get additional origins from environment variable
env_origins = os.getenv("ALLOWED_ORIGINS", "")
if env_origins:
    if env_origins == "*":
        # Use wildcard - allow all origins (no credentials)
        allowed_origins = ["*"]
    else:
        # Add specific origins from environment
        additional_origins = [origin.strip() for origin in env_origins.split(",")]
        allowed_origins.extend(additional_origins)

# Determine credentials setting based on origins
# Cannot use credentials with "*" wildcard
# credentials=True is REQUIRED for httpOnly cookies to work
allow_credentials = "*" not in allowed_origins

print(f"CORS Configuration: origins={allowed_origins}, credentials={allow_credentials}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=allow_credentials,  # Required for httpOnly cookie authentication
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,  # Cache preflight requests for 10 minutes
)

# Configure logging for better visibility
# FORCE OUTPUT IMMEDIATELY (before any logging setup)
print("=" * 70, flush=True)
print("🚀 BACKEND MAIN.PY LOADING...", flush=True)
print(f"Python: {sys.version}", flush=True)
print(f"Working Dir: {os.getcwd()}", flush=True)
print("=" * 70, flush=True)

# Configure logging inline (no external module needed)
# Use explicit StreamHandler to ensure logs go to stdout/systemd
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ],
    force=True  # Override any existing configuration
)

logger = logging.getLogger(__name__)

# Force flush for every log message
for handler in logging.root.handlers:
    handler.flush = lambda: sys.stdout.flush()

logger.info("✅ Logger initialized successfully")
print("✅ Logger initialized successfully", flush=True)  # Also print directly

# Test logging immediately
print("=" * 70, flush=True)
print("🧪 TESTING LOGGING - If you see this, print() works!", flush=True)
print("=" * 70, flush=True)
logger.info("🧪 TESTING LOGGING - If you see this, logger works!")

# Middleware to handle X-Forwarded-Proto (HTTPS detection behind proxy)
@app.middleware("http")
async def handle_forwarded_proto(request: Request, call_next):
    """Fix HTTPS redirects when behind nginx reverse proxy"""
    # Check if we're behind a proxy with X-Forwarded-Proto header
    forwarded_proto = request.headers.get("X-Forwarded-Proto")
    if forwarded_proto:
        # Update request scope to use the correct scheme
        request.scope["scheme"] = forwarded_proto
        print(f"🔒 [DEBUG] Detected X-Forwarded-Proto: {forwarded_proto}", flush=True)
    
    response = await call_next(request)
    return response

# Request logging middleware - logs every API request
@app.middleware("http")
async def log_requests(request: Request, call_next):
    # ALWAYS print at the start to verify middleware is running
    print(f"🔥 MIDDLEWARE TRIGGERED: {request.method} {request.url.path}", flush=True)
    start_time = time.time()
    
    # Log incoming request (both logger and print for reliability)
    log_msg = f"📥 {request.method} {request.url.path} - Client: {request.client.host if request.client else 'unknown'}"
    logger.info(log_msg)
    print(log_msg, flush=True)  # Ensure it appears in systemd
    
    # Process request
    response = await call_next(request)
    
    # Calculate duration
    duration = time.time() - start_time
    
    # Log response (both logger and print for reliability)
    response_msg = (
        f"📤 {request.method} {request.url.path} - "
        f"Status: {response.status_code} - "
        f"Duration: {duration:.3f}s"
    )
    logger.info(response_msg)
    print(response_msg, flush=True)  # Ensure it appears in systemd
    
    return response

# Event handlers
@app.on_event("startup")
async def startup_event():
    # Force unbuffered output
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
    
    logger.info("=" * 60)
    logger.info("🚀 BACKEND STARTING UP")
    logger.info("=" * 60)
    logger.info(f"Python version: {sys.version.split()[0]}")
    logger.info(f"Working directory: {os.getcwd()}")
    logger.info(f"Server port: {os.getenv('PORT', '8000')}")
    
    try:
        await connect_db()
        logger.info("✅ MongoDB connected successfully")
    except Exception as e:
        logger.warning("=" * 60)
        logger.warning(f"⚠️  Could not connect to MongoDB: {e}")
        logger.warning("GUEST MODE ACTIVE - code execution works without DB!")
        logger.warning("To enable saving code, install and start MongoDB")
        logger.warning("=" * 60)
    
    # Initialize Redis Pub/Sub for WebSocket
    try:
        from app.routes.websocket_routes_pubsub import setup_pubsub
        await setup_pubsub()
        logger.info("✅ Redis Pub/Sub initialized")
    except Exception as e:
        logger.warning(f"⚠️  Redis Pub/Sub not available: {e}")
        logger.warning("   WebSocket will work but without Pub/Sub features")
    
    # Initialize Redis Queue for job processing
    try:
        from app.redis_queue_service import redis_queue_service
        await redis_queue_service.connect()
        logger.info("✅ Redis Queue initialized (for worker communication)")
    except Exception as e:
        logger.warning(f"⚠️  Redis Queue not available: {e}")
        logger.warning("   Jobs will NOT be processed by separate workers!")
    
    # Initialize HTTP execute route Pub/Sub listener
    try:
        from app.routes.execute_redis import setup_http_pubsub
        await setup_http_pubsub()
        logger.info("✅ HTTP execute route Pub/Sub initialized")
    except Exception as e:
        logger.warning(f"⚠️  HTTP execute Pub/Sub not available: {e}")
    
    # Start workers in background for local development
    if os.getenv('USE_QUEUE', 'false').lower() == 'false':
        # Get number of workers from environment (default: 10 for dev)
        num_workers = int(os.getenv('DEV_WORKERS', '10'))
        
        logger.info("=" * 60)
        logger.info(f"Starting {num_workers} parallel background workers...")
        logger.info("(Set DEV_WORKERS env variable to change)")
        logger.info("=" * 60)
        
        # Import worker loop
        from worker import worker_loop
        
        # Start multiple worker tasks for parallel processing
        for i in range(num_workers):
            asyncio.create_task(worker_loop())
        
        logger.info(f"SUCCESS: {num_workers} workers ready for parallel processing!")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("=" * 60)
    logger.info("🛑 BACKEND SHUTTING DOWN")
    logger.info("=" * 60)
    
    try:
        await close_db()
        logger.info("✅ MongoDB connection closed")
    except Exception as e:
        logger.error(f"❌ Error closing MongoDB: {e}")
    
    # Clean up Redis Pub/Sub
    try:
        from app.routes.websocket_routes_pubsub import cleanup_pubsub
        await cleanup_pubsub()
        logger.info("✅ Redis Pub/Sub cleaned up")
    except Exception as e:
        logger.error(f"❌ Error cleaning up Redis: {e}")
    
    logger.info("👋 Shutdown complete")

# Health check endpoint
@app.get("/health")
async def health_check():
    from app.database import db
    mongodb_status = "connected" if db is not None else "disconnected (guest mode active)"
    return {
        "status": "OK",
        "message": "Backend API is running",
        "mongodb": mongodb_status,
        "guest_mode": db is None
    }

# TEST ENDPOINT - for debugging logs
@app.get("/test-logging")
async def test_logging():
    print("🧪 TEST ENDPOINT CALLED - print() with flush", flush=True)
    logger.info("🧪 TEST ENDPOINT CALLED - logger.info()")
    return {
        "status": "success",
        "message": "If you see this in the response, the endpoint works. Check journalctl for logs!"
    }

# Include routers
# WebSocket route first (no prefix needed)
app.include_router(websocket_routes.router, tags=["WebSocket"])

# WebSocket with Pub/Sub (for Redis Pub/Sub support)
app.include_router(websocket_routes_pubsub.router, tags=["WebSocket Pub/Sub"])

# Then REST API routes
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(codes.router, prefix="/api/codes", tags=["Codes"])
app.include_router(folders.router, prefix="/api/folders", tags=["Folders"])
app.include_router(download.router, prefix="/api", tags=["Download"])

# Use Redis-based execute (with Pub/Sub - no polling needed!)
app.include_router(execute_redis.router, prefix="/api", tags=["Execute (Redis)"])

# Old execute (polling-based) - disabled
# app.include_router(execute.router, prefix="/api", tags=["Execute"])
app.include_router(problems.router, prefix="/api/problems", tags=["Problems"])
app.include_router(admin_problems.router, prefix="/api/admin", tags=["Admin - Problems"])
app.include_router(weekly_challenges.router, prefix="/api/weekly-challenges", tags=["Weekly Challenges"])
app.include_router(solutions.router, prefix="/api", tags=["Solutions & Interview Experiences"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])
app.include_router(support.router, prefix="/api/support", tags=["Support"])

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", 5000))
    
    # Windows-specific: Set event loop policy for subprocess support
    # This is ONLY for Windows - Linux works fine with default policy
    if sys.platform == 'win32':
        print("=" * 50)
        print("WINDOWS DETECTED - Applying ProactorEventLoop Fix")
        print("=" * 50)
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
        # Verify policy is set
        policy = asyncio.get_event_loop_policy()
        print(f"Event Loop Policy: {policy.__class__.__name__}")
        
        # IMPORTANT: reload must be False on Windows to preserve event loop
        print("Starting server WITHOUT reload (Windows requirement)")
        print("=" * 50)
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=port,
            reload=False,  # MUST be False on Windows for ProactorEventLoop
            loop="asyncio"
        )
    else:
        # Linux: Can use reload
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=port,
            reload=False,
            loop="asyncio"
        )


