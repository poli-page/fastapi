"""Tests for poli_page_fastapi.responses."""

from __future__ import annotations

from collections.abc import Iterator

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
