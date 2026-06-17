import time
from typing import Dict, Any

# Lightweight, in-memory metrics tracker for production VPS monitoring
metrics = {
    "api_latency_sum": 0.0,
    "api_request_count": 0,
    "sync_failures_count": 0,
    "ai_processing_duration_sum": 0.0,
    "ai_processing_count": 0,
    "upload_failures_count": 0,
    "rate_limit_exceeded_count": 0
}

def track_api_request(latency: float):
    metrics["api_latency_sum"] += latency
    metrics["api_request_count"] += 1

def track_sync_failure():
    metrics["sync_failures_count"] += 1

def track_ai_processing(duration: float):
    metrics["ai_processing_duration_sum"] += duration
    metrics["ai_processing_count"] += 1

def track_upload_failure():
    metrics["upload_failures_count"] += 1
