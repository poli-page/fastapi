"""Response helpers — Starlette response subclasses with the right headers."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from contextlib import AbstractContextManager

import anyio
import anyio.to_thread
from starlette.background import BackgroundTask
from starlette.responses import Response, StreamingResponse
from starlette.types import Receive, Scope, Send

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


class _OpenedStream:
    """The chunks of an SDK stream entered at once; exhausting them, or an error, exits it."""

    def __init__(self, stream: AbstractContextManager[Iterator[bytes]]) -> None:
        self._stream = stream
        self._chunks = iter(stream.__enter__())
        self._open = True

    def __iter__(self) -> Iterator[bytes]:
        return self

    def __next__(self) -> bytes:
        try:
            return next(self._chunks)
        except BaseException:
            self.close()
            raise

    def close(self) -> None:
        if self._open:
            self._open = False
            self._stream.__exit__(None, None, None)


class PdfStreamResponse(StreamingResponse):
    """A streamed PDF response.

    Pass the SDK's stream as is: `PdfStreamResponse(client.render.pdf_stream(input))`.
    The render and the download start here, in the route, so a `PoliPageError` raises
    before the response starts and reaches the error handler. The stream is closed when
    the response ends: read to the end, failed, or the client disconnected. A response
    built and never sent leaves it to the garbage collector.

    Opening the stream does the render and the download's first request synchronously:
    build the response in a `def` route (FastAPI runs it in its threadpool), or in
    `run_in_threadpool` from an `async def` route.

    An iterator of bytes (sync or async) is streamed as given: an error it raises comes
    after the 200 has been sent.
    """

    media_type = "application/pdf"

    def __init__(
        self,
        content: AbstractContextManager[Iterator[bytes]] | Iterator[bytes] | AsyncIterator[bytes],
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
        self._opened: _OpenedStream | None = None
        if isinstance(content, AbstractContextManager):
            content = self._opened = _OpenedStream(content)
        super().__init__(
            content=content,
            status_code=status_code,
            media_type="application/pdf",
            headers=merged,
            background=background,
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            await super().__call__(scope, receive, send)
        finally:
            # Starlette never closes a sync iterator: on a client disconnect it cancels
            # the send (ASGI < 2.4) or raises ClientDisconnect (2.4+). Close the SDK
            # stream here, shielded from that cancellation, so its connection returns.
            if self._opened is not None:
                with anyio.CancelScope(shield=True):
                    await anyio.to_thread.run_sync(self._opened.close)


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
