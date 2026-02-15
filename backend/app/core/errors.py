"""Structured error response utilities."""

import logging

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse

_log = logging.getLogger(__name__)


async def http_error_handler(request: Request, exc: HTTPException):
    """Return structured error responses for all HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": f"HTTP_{exc.status_code}",
                "message": exc.detail,
            }
        },
    )


async def generic_error_handler(request: Request, exc: Exception):
    """Catch-all for unhandled exceptions — log and return generic 500."""
    _log.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
            }
        },
    )
