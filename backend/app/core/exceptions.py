import logging
import uuid
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

logger = logging.getLogger("voicemind.exceptions")

class APIException(Exception):
    def __init__(self, status_code: int, detail: str, error_code: str = "API_ERROR"):
        self.status_code = status_code
        self.detail = detail
        self.error_code = error_code

async def api_exception_handler(request: Request, exc: APIException):
    correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
    logger.error(
        f"APIException [{exc.error_code}]: {exc.detail} (Correlation ID: {correlation_id})"
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "error_code": exc.error_code,
            "correlation_id": correlation_id
        }
    )

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
    logger.warning(
        f"Validation Error: {exc.errors()} (Correlation ID: {correlation_id})"
    )
    # Sanitize validation errors to not leak full model structure details
    sanitized_errors = []
    for err in exc.errors():
        sanitized_errors.append({
            "loc": err.get("loc"),
            "msg": err.get("msg"),
            "type": err.get("type")
        })
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": sanitized_errors,
            "error_code": "VALIDATION_ERROR",
            "correlation_id": correlation_id
        }
    )

async def global_exception_handler(request: Request, exc: Exception):
    correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
    logger.error(
        f"Unhandled Exception: {str(exc)} (Correlation ID: {correlation_id})",
        exc_info=True
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An internal server error occurred.",
            "error_code": "INTERNAL_SERVER_ERROR",
            "correlation_id": correlation_id
        }
    )

