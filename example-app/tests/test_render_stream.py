"""`GET /render/stream`: an SDK error answers the error handler's JSON, not a started PDF."""

from __future__ import annotations

import base64
import json
import os
from collections.abc import Mapping, Sequence
from typing import Any

import pytest
from fastapi.testclient import TestClient
from main import app
from mock_api import MockServer

from poli_page_fastapi import get_poli_page_client

TEST_API_KEY = "pp_sandbox_0123456789abcdef0123456789abcdef"
PDF = b"%PDF-1.4\n%%EOF\n"

DESCRIPTOR: dict[str, Any] = {
    "apiKeyId": None,
    "createdAt": "2026-09-29T09:45:22.000Z",
    "diagnostics": [],
    "documentId": "doc_abc123",
    "environment": "sandbox",
    "expiresAt": "2026-09-29T10:00:22.000Z",
    "format": "A4",
    "locale": None,
    "metadata": {},
    "organizationId": "org_xyz",
    "orientation": "portrait",
    "pageCount": 1,
    "presignedPdfUrl": "{{mock}}/storage/doc_abc123.pdf",
    "projectId": None,
    "projectSlug": "getting-started",
    "sizeBytes": len(PDF),
    "templateId": None,
    "templateSlug": "welcome",
}


def _get_stream(
    responses: Sequence[Mapping[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> tuple[Any, bytes, MockServer]:
    server = MockServer(responses)
    try:
        for name in [n for n in os.environ if n.upper().startswith("POLI_PAGE_")]:
            monkeypatch.delenv(name)
        monkeypatch.setenv("POLI_PAGE_API_KEY", TEST_API_KEY)
        monkeypatch.setenv("POLI_PAGE_BASE_URL", server.origin)
        get_poli_page_client.cache_clear()
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/render/stream")
    finally:
        server.close()
        get_poli_page_client.cache_clear()
    return response, response.content, server


def test_streams_the_pdf(monkeypatch: pytest.MonkeyPatch) -> None:
    response, body, server = _get_stream(
        [
            {"status": 200, "json": DESCRIPTOR},
            {
                "status": 200,
                "headers": {"content-type": "application/pdf"},
                "base64": base64.b64encode(PDF).decode(),
            },
        ],
        monkeypatch,
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"] == 'inline; filename="welcome-stream.pdf"'
    assert body == PDF
    assert [(r.method, r.path) for r in server.requests] == [
        ("POST", "/v1/render"),
        ("GET", "/storage/doc_abc123.pdf"),
    ]


@pytest.mark.parametrize(
    ("responses", "status", "payload"),
    [
        pytest.param(
            [
                {
                    "status": 404,
                    "headers": {"x-request-id": "req_stream_404"},
                    "json": {
                        "error": "TEMPLATE_NOT_FOUND",
                        "detail": "Template 'welcome' not found in project 'getting-started'.",
                        "requestId": "req_stream_404",
                    },
                }
            ],
            404,
            {
                "code": "TEMPLATE_NOT_FOUND",
                "message": "Template 'welcome' not found in project 'getting-started'.",
                "status": 404,
                "requestId": "req_stream_404",
            },
            id="render-404",
        ),
        pytest.param(
            [{"fault": "drop"}, {"fault": "drop"}, {"fault": "drop"}],
            503,
            {
                "code": "network_error",
                "message": "Network request failed",
                "status": 503,
                "requestId": None,
            },
            id="network-error",
        ),
        pytest.param(
            [{"status": 200, "json": DESCRIPTOR}, {"status": 403, "text": "AccessDenied"}],
            403,
            {
                "code": "DOWNLOAD_FAILED",
                "message": "Failed to download PDF: HTTP 403",
                "status": 403,
                "requestId": None,
            },
            id="download-403",
        ),
    ],
)
def test_sdk_error_answers_the_error_handler_json(
    responses: list[dict[str, Any]],
    status: int,
    payload: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response, body, _ = _get_stream(responses, monkeypatch)

    assert response.status_code == status
    assert response.headers["content-type"] == "application/json"
    assert "content-disposition" not in response.headers
    assert json.loads(body) == payload
