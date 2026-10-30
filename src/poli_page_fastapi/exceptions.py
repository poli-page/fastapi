"""Exception handler answering a `PoliPageError` as JSON.

`setup_poli_page(app)` registers it by default. To register it yourself:

    from poli_page import PoliPageError
    from poli_page_fastapi import poli_page_exception_handler

    app.add_exception_handler(PoliPageError, poli_page_exception_handler)
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
from poli_page import PoliPageError


def poli_page_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Answer a `PoliPageError` with its `to_payload()` body.

    Body: exactly `exc.to_payload()`, `{code, message, status, requestId}` (camelCase
    on the wire, `null` when unknown). Status: the payload's `status` (the API status,
    503 for `network_error`, 504 for `timeout`), or 500 when it is `null`.

    Any other exception is re-raised, so the application's own handling applies.
    """
    if not isinstance(exc, PoliPageError):
        raise exc
    payload = exc.to_payload()
    status = payload["status"]
    return JSONResponse(
        status_code=status if isinstance(status, int) else 500,
        content=payload,
        headers={"Cache-Control": "no-store, private"},
    )
