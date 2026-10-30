"""Tests for poli_page_fastapi.responses."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from poli_page_fastapi.responses import (
    DocumentRedirectResponse,
    PdfResponse,
    PdfStreamResponse,
    PreviewResponse,
)


def test_pdf_response_default_headers() -> None:
    resp = PdfResponse(b"%PDF-1.4\n...", filename="invoice.pdf")
    assert resp.status_code == 200
    assert resp.media_type == "application/pdf"
    assert resp.headers["content-type"].startswith("application/pdf")
    assert resp.headers["content-disposition"] == 'attachment; filename="invoice.pdf"'
    assert resp.headers["cache-control"] == "no-store, private"
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.body == b"%PDF-1.4\n..."


def test_pdf_response_inline_flips_disposition() -> None:
    resp = PdfResponse(b"%PDF", filename="x.pdf", inline=True)
    assert resp.headers["content-disposition"] == 'inline; filename="x.pdf"'


def test_pdf_response_non_ascii_filename() -> None:
    resp = PdfResponse(b"%PDF", filename="résumé.pdf")
    disp = resp.headers["content-disposition"]
    assert disp.startswith("attachment; filename=\"r?sum?.pdf\"; filename*=UTF-8''")
    assert "r%C3%A9sum%C3%A9.pdf" in disp


def test_pdf_response_user_headers_merged() -> None:
    resp = PdfResponse(b"%PDF", filename="x.pdf", headers={"X-Custom": "yes"})
    assert resp.headers["x-custom"] == "yes"
    assert resp.headers["cache-control"] == "no-store, private"


def test_pdf_response_user_can_override_cache_control() -> None:
    resp = PdfResponse(b"%PDF", filename="x.pdf", headers={"Cache-Control": "public, max-age=60"})
    assert resp.headers["cache-control"] == "public, max-age=60"


def test_pdf_stream_response_headers() -> None:
    def gen() -> Iterator[bytes]:
        yield b"%PDF-1.4\n"
        yield b"...\n"

    resp = PdfStreamResponse(gen(), filename="big.pdf")
    assert resp.media_type == "application/pdf"
    assert resp.headers["content-disposition"] == 'attachment; filename="big.pdf"'
    assert resp.headers["cache-control"] == "no-store, private"
    assert resp.headers["x-content-type-options"] == "nosniff"


def test_preview_response_headers() -> None:
    resp = PreviewResponse("<p>Hello</p>")
    assert resp.status_code == 200
    assert resp.media_type.startswith("text/html")
    assert "charset=utf-8" in resp.headers["content-type"]
    assert resp.headers["cache-control"] == "no-store, private"
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.body == b"<p>Hello</p>"


def test_document_redirect_response_default() -> None:
    resp = DocumentRedirectResponse("https://s3.example.com/doc.pdf?sig=abc")
    assert resp.status_code == 302
    assert resp.headers["location"] == "https://s3.example.com/doc.pdf?sig=abc"
    assert resp.headers["cache-control"] == "no-store, private"


def test_document_redirect_response_permanent() -> None:
    resp = DocumentRedirectResponse("https://s3.example.com/doc.pdf", permanent=True)
    assert resp.status_code == 308


def test_response_classes_yield_valid_openapi_schema() -> None:
    """Regression: response_class=Pdf/PdfStream/PreviewResponse must not crash
    FastAPI's OpenAPI schema generation.

    FastAPI's get_openapi_path() inspects `response_class.__init__` for a
    `status_code` parameter; absence of one references an uninitialised
    local variable (UnboundLocalError at fastapi/openapi/utils.py). Symptom
    in the demo app: /openapi.json returns 500 and /docs (Swagger UI) shows
    "Failed to load API definition".
    """
    from fastapi import FastAPI

    app = FastAPI()

    @app.get("/pdf", response_class=PdfResponse)
    def _pdf() -> PdfResponse:
        return PdfResponse(b"%PDF-1.4\n", filename="x.pdf")

    @app.get("/stream", response_class=PdfStreamResponse)
    def _stream() -> PdfStreamResponse:
        def gen() -> Iterator[bytes]:
            yield b"%PDF"

        return PdfStreamResponse(gen(), filename="x.pdf")

    @app.get("/preview", response_class=PreviewResponse)
    def _preview() -> PreviewResponse:
        return PreviewResponse("<p>x</p>")

    schema = app.openapi()
    assert "/pdf" in schema["paths"]
    assert "/stream" in schema["paths"]
    assert "/preview" in schema["paths"]


class _FakeStream:
    """Stands in for the SDK's `client.render.pdf_stream(...)` context manager."""

    def __init__(self, chunks: list[bytes], error: Exception | None = None) -> None:
        self.chunks = chunks
        self.error = error
        self.entered = False
        self.exited = 0

    def __enter__(self) -> Iterator[bytes]:
        self.entered = True
        if self.error is not None:
            raise self.error
        return iter(self.chunks)

    def __exit__(self, *exc: object) -> None:
        self.exited += 1


def test_pdf_stream_response_enters_an_sdk_stream_at_once_and_closes_it_once_read() -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from poli_page_fastapi.responses import PdfStreamResponse

    stream = _FakeStream([b"%PDF", b"-1.4"])
    response = PdfStreamResponse(stream, filename="s.pdf")
    assert stream.entered
    assert stream.exited == 0

    app = FastAPI()
    app.get("/s")(lambda: response)
    assert TestClient(app).get("/s").content == b"%PDF-1.4"
    assert stream.exited == 1


def test_pdf_stream_response_raises_the_sdk_error_before_any_response() -> None:
    from poli_page import PoliPageError

    from poli_page_fastapi.responses import PdfStreamResponse

    error = PoliPageError("Failed to download PDF: HTTP 403", code="DOWNLOAD_FAILED", status=403)
    with pytest.raises(PoliPageError) as raised:
        PdfStreamResponse(_FakeStream([], error), filename="s.pdf")
    assert raised.value is error
