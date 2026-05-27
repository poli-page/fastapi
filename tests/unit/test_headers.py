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


def test_filename_with_quotes_escaped() -> None:
    result = build_content_disposition('he"llo.pdf')
    assert result == 'attachment; filename="he"llo.pdf"'
