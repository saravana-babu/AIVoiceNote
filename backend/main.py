import asyncio
import uuid
import time
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.exceptions import (
    APIException,
    api_exception_handler,
    validation_exception_handler,
    global_exception_handler
)
from app.api.v1.router import api_router
from app.database import engine, Base

# Setup logging configuration
setup_logging()
logger = logging.getLogger("voicemind.main")

# Correlation ID and Performance Middleware
class RequestMonitoringMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
        request.state.correlation_id = correlation_id
        
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        
        from app.core.metrics import track_api_request
        track_api_request(process_time)
        
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Process-Time"] = str(process_time)
        
        logger.info(
            f"Method: {request.method} Path: {request.url.path} "
            f"Status: {response.status_code} ProcessTime: {process_time:.4f}s CorrelationID: {correlation_id}"
        )
        return response

# Security Headers Middleware
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none';"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

# In-Memory Rate Limiting Middleware
import time
from collections import defaultdict
from fastapi.responses import JSONResponse

rate_limit_records = defaultdict(list)
RATE_LIMIT_WINDOW = 60  # 1 minute window
RATE_LIMIT_MAX_REQUESTS = 100  # maximum requests per window

class RateLimitingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Allow health, metrics endpoints, and testing runs without rate limiting
        if settings.ENVIRONMENT == "testing" or request.url.path.startswith("/health") or request.url.path == "/health" or request.url.path == "/metrics":
            return await call_next(request)
            
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        
        # Clean older timestamps
        timestamps = [t for t in rate_limit_records[client_ip] if now - t < RATE_LIMIT_WINDOW]
        rate_limit_records[client_ip] = timestamps
        
        if len(timestamps) >= RATE_LIMIT_MAX_REQUESTS:
            from app.core.metrics import metrics
            metrics["rate_limit_exceeded_count"] += 1
            logger.warning(f"Rate limit exceeded for client IP: {client_ip} on path {request.url.path}")
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again later."}
            )
            
        rate_limit_records[client_ip].append(now)
        return await call_next(request)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Run schema creations only in SQLite development mode.
    # Production databases must rely solely on Alembic migrations.
    if settings.DATABASE_URL.startswith("sqlite"):
        Base.metadata.create_all(bind=engine)
    
    # Initialize background worker processes
    from app.services.email_service import start_scheduled_email_worker_loop
    email_task = asyncio.create_task(start_scheduled_email_worker_loop())
    
    logger.info("VoiceMind AI Backend has started successfully.")
    yield
    # Shutdown
    email_task.cancel()
    try:
        await email_task
    except asyncio.CancelledError:
        pass
    logger.info("VoiceMind AI Backend has shutdown cleanly.")

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(RequestMonitoringMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitingMiddleware)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception Handlers
app.add_exception_handler(APIException, api_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)

# Register API v1 routes
app.include_router(api_router, prefix=settings.API_V1_STR)

def check_db_health() -> bool:
    from sqlalchemy.sql import text
    from app.database import SessionLocal
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"DB health check failed: {e}")
        return False
    finally:
        db.close()

def check_storage_health() -> bool:
    from app.core.r2 import r2_client
    if not r2_client.is_configured:
        # Local mock mode counts as OK when not in production environment
        return settings.ENVIRONMENT != "production"
    try:
        r2_client.client.list_objects_v2(Bucket=r2_client.bucket, MaxKeys=1)
        return True
    except Exception as e:
        logger.error(f"R2 storage health check failed: {e}")
        return False

@app.get("/health", tags=["health"])
def health_check():
    db_ok = check_db_health()
    storage_ok = check_storage_health()
    status_str = "ok" if (db_ok and storage_ok) else "degraded"
    return {
        "status": status_str,
        "project": settings.PROJECT_NAME,
        "database": "reachable" if db_ok else "unreachable",
        "storage": "configured" if storage_ok else "unconfigured_or_unreachable"
    }

@app.get("/health/db", tags=["health"])
def health_db():
    db_ok = check_db_health()
    if not db_ok:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Database is unreachable")
    return {"status": "ok", "database": "reachable"}

@app.get("/health/storage", tags=["health"])
def health_storage():
    storage_ok = check_storage_health()
    if not storage_ok:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Storage is unconfigured or unreachable")
    return {"status": "ok", "storage": "reachable_and_configured"}

@app.get("/metrics", tags=["monitoring"])
def get_metrics():
    from app.core.metrics import metrics
    return metrics

# Feature Flag Check API Mock Implementation
@app.get("/api/v1/features", tags=["features"])
def get_features(current_env: str = settings.ENVIRONMENT):
    return {
        "enable_prometheus": settings.ENABLE_PROMETHEUS,
        "enable_knowledge_chat": True,
        "enable_email_scheduling": True,
        "sandbox_mode": current_env != "production"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

