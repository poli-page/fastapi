"""Opt-in exception handler bridging PoliPageError to FastAPI JSON responses.

Register via:

    from poli_page import PoliPageError
    from poli_page_fastapi import poli_page_exception_handler

    app.add_exception_handler(PoliPageError, poli_page_exception_handler)
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
from poli_page import APIConnectionError, APIStatusError, PoliPageError


def poli_page_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Map any PoliPageError to a typed JSON response.

    Status code: matches exc.status for APIStatusError; 502 for
    APIConnectionError / APITimeoutError; 500 for the base PoliPageError
    (validation / programming errors). Body shape mirrors the SDK's own
    error structure, plus request_id (null when absent).
    """
    if not isinstance(exc, PoliPageError):
        return JSONResponse(
            status_code=500,
            content={"code": "UNKNOWN", "message": str(exc), "request_id": None},
            headers={"Cache-Control": "no-store, private"},
        )

    if isinstance(exc, APIStatusError) and exc.status is not None:
        status_code = exc.status
    elif isinstance(exc, APIConnectionError):
        status_code = 502
    else:
        status_code = 500

    return JSONResponse(
        status_code=status_code,
        content={
            "code": exc.code,
            "message": exc.message,
            "request_id": exc.request_id,
        },
        headers={"Cache-Control": "no-store, private"},
    )
