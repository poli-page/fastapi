"""Response helpers — Starlette response subclasses with the right headers."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

from starlette.background import BackgroundTask
from starlette.responses import Response, StreamingResponse

from poli_page_fastapi._headers import build_content_disposition

_PDF_DEFAULT_HEADERS = {
    "Cache-Control": "no-store, private",
    "X-Content-Type-Options": "nosniff",
}


class PdfResponse(Response):
    """A PDF response with correct Content-Type, Content-Disposition, Cache-Control."""

    media_type = "application/pdf"

    def __init__(
        self,
        content: bytes,
        *,
        status_code: int = 200,
        filename: str = "document.pdf",
        inline: bool = False,
        background: BackgroundTask | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        # Why: status_code is also exposed so FastAPI's OpenAPI generator can
        # discover the default response status when this class is used as
        # `response_class=PdfResponse` (otherwise /openapi.json returns 500
        # — UnboundLocalError in fastapi/openapi/utils.py).
        merged: dict[str, str] = dict(headers or {})
        merged["Content-Disposition"] = build_content_disposition(filename, inline=inline)
        for k, v in _PDF_DEFAULT_HEADERS.items():
            merged.setdefault(k, v)
        super().__init__(
            content=content,
            status_code=status_code,
            media_type="application/pdf",
            headers=merged,
            background=background,
        )


class PdfStreamResponse(StreamingResponse):
    """A streamed PDF response for client.render.pdf_stream(...) iterators."""

    media_type = "application/pdf"

    def __init__(
        self,
        content: Iterator[bytes] | AsyncIterator[bytes],
        *,
        status_code: int = 200,
        filename: str = "document.pdf",
        inline: bool = False,
        background: BackgroundTask | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        merged: dict[str, str] = dict(headers or {})
        merged["Content-Disposition"] = build_content_disposition(filename, inline=inline)
        for k, v in _PDF_DEFAULT_HEADERS.items():
            merged.setdefault(k, v)
        super().__init__(
            content=content,
            status_code=status_code,
            media_type="application/pdf",
            headers=merged,
            background=background,
        )


class PreviewResponse(Response):
    """An HTML preview response — text/html; charset=utf-8."""

    media_type = "text/html; charset=utf-8"

    def __init__(
        self,
        content: str,
        *,
        status_code: int = 200,
        background: BackgroundTask | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        merged: dict[str, str] = dict(headers or {})
        merged.setdefault("Cache-Control", "no-store, private")
        merged.setdefault("X-Content-Type-Options", "nosniff")
        super().__init__(
            content=content,
            status_code=status_code,
            media_type="text/html; charset=utf-8",
            headers=merged,
            background=background,
        )


class DocumentRedirectResponse(Response):
    """A 302 (or 308 if permanent=True) redirect to a document's presigned URL."""

    def __init__(
        self,
        url: str,
        *,
        permanent: bool = False,
        background: BackgroundTask | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        merged: dict[str, str] = dict(headers or {})
        merged["Location"] = url
        merged.setdefault("Cache-Control", "no-store, private")
        status_code = 308 if permanent else 302
        super().__init__(
            content=b"",
            status_code=status_code,
            headers=merged,
            background=background,
        )
