"""Tests for poli_page_fastapi._headers.build_content_disposition."""

from __future__ import annotations

import pytest

from poli_page_fastapi._headers import build_content_disposition


def test_ascii_filename_attachment() -> None:
    assert build_content_disposition("invoice.pdf") == 'attachment; filename="invoice.pdf"'


def test_ascii_filename_inline() -> None:
    assert build_content_disposition("invoice.pdf", inline=True) == 'inline; filename="invoice.pdf"'


def test_non_ascii_filename_attachment() -> None:
    result = build_content_disposition("naïve.pdf")
    assert result.startswith("attachment; filename=\"na?ve.pdf\"; filename*=UTF-8''")
    assert "na%C3%AFve.pdf" in result


def test_non_ascii_filename_inline() -> None:
    result = build_content_disposition("résumé.pdf", inline=True)
    assert result.startswith("inline; filename=\"r?sum?.pdf\"; filename*=UTF-8''")
    assert "r%C3%A9sum%C3%A9.pdf" in result


@pytest.mark.parametrize(
    "filename,expected_encoded",
    [
        ("über.pdf", "%C3%BCber.pdf"),
        ("é.pdf", "%C3%A9.pdf"),
        ("naïve résumé.pdf", "na%C3%AFve%20r%C3%A9sum%C3%A9.pdf"),
        ("漢字.pdf", "%E6%BC%A2%E5%AD%97.pdf"),
        ("emoji 🎉.pdf", "emoji%20%F0%9F%8E%89.pdf"),
    ],
)
def test_rfc5987_encoding(filename: str, expected_encoded: str) -> None:
    result = build_content_disposition(filename)
    assert expected_encoded in result


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        pytest.param(
            'say "hi".pdf',
            'attachment; filename="say \\"hi\\".pdf"',
            id="double-quote-is-escaped",
        ),
        pytest.param(
            "a\\b.pdf",
            'attachment; filename="a\\\\b.pdf"',
            id="backslash-is-escaped",
        ),
        pytest.param(
            "evil.pdf\r\nSet-Cookie: sid=1",
            'attachment; filename="evil.pdfSet-Cookie: sid=1"',
            id="crlf-is-stripped",
        ),
        pytest.param(
            "tab\there\x00\x1f\x7f.pdf",
            'attachment; filename="tabhere.pdf"',
            id="control-chars-are-stripped",
        ),
        pytest.param(
            'x.pdf"; filename="pwn.exe',
            'attachment; filename="x.pdf\\"; filename=\\"pwn.exe"',
            id="parameter-injection-stays-inside-the-quoted-string",
        ),
        pytest.param(
            "résumé François.pdf",
            'attachment; filename="r?sum? Fran?ois.pdf"; '
            "filename*=UTF-8''r%C3%A9sum%C3%A9%20Fran%C3%A7ois.pdf",
            id="non-ascii-uses-rfc5987-dual-notation",
        ),
        pytest.param(
            'résumé "final"\\v2.pdf',
            'attachment; filename="r?sum? \\"final\\"\\\\v2.pdf"; '
            "filename*=UTF-8''r%C3%A9sum%C3%A9%20%22final%22%5Cv2.pdf",
            id="non-ascii-fallback-is-escaped",
        ),
        pytest.param(
            "résumé\r\n\x85.pdf",
            "attachment; filename=\"r?sum?.pdf\"; filename*=UTF-8''r%C3%A9sum%C3%A9.pdf",
            id="non-ascii-control-chars-are-stripped-from-both-forms",
        ),
    ],
)
def test_content_disposition_is_rfc6266_safe(filename: str, expected: str) -> None:
    assert build_content_disposition(filename) == expected


def test_inline_content_disposition_is_escaped() -> None:
    assert build_content_disposition('q"\r\n.pdf', inline=True) == 'inline; filename="q\\".pdf"'
