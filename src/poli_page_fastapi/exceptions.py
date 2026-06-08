"""Opt-in exception handler bridging PoliPageError to FastAPI JSON responses.

Register via:

    from poli_page import PoliPageError
    from poli_page_fastapi import poli_page_exception_handler

    app.add_exception_handler(PoliPageError, poli_page_exception_handler)
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
from poli_page import PoliPageError


def poli_page_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Map any PoliPageError to a canonical JSON response.

    Body shape: `{code, message, status, requestId}` (camelCase on the wire).
    Status: from the SDK's `to_payload()` — the API status for `APIStatusError`,
    503 for connection failures, 504 for timeouts. Non-`PoliPageError`
    exceptions surface as a 500 with `code="UNKNOWN"`.
    """
    if not isinstance(exc, PoliPageError):
        return JSONResponse(
            status_code=500,
            content={
                "code": "UNKNOWN",
                "message": str(exc),
                "status": 500,
                "requestId": None,
            },
            headers={"Cache-Control": "no-store, private"},
        )

    payload = exc.to_payload()
    status_code = payload["status"] or 500
    return JSONResponse(
        status_code=status_code,
        content={
            "code": payload["code"],
            "message": payload["message"],
            "status": status_code,
            "requestId": payload["requestId"],
        },
        headers={"Cache-Control": "no-store, private"},
    )
