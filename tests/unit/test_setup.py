"""Tests for poli_page_fastapi.setup.setup_poli_page: error handler on by default, lifespan."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from poli_page import APIConnectionError, APITimeoutError, NotFoundError, PoliPageError
from pytest_mock import MockerFixture

from poli_page_fastapi import setup_poli_page
from poli_page_fastapi.dependencies import get_poli_page_client
from tests.unit.keys import SANDBOX_KEY

ERRORS: dict[str, PoliPageError] = {
    "api": NotFoundError(
        "Template 'does-not-exist' not found in project 'getting-started'.",
        code="TEMPLATE_NOT_FOUND",
        status=404,
        request_id="req_123",
    ),
    "network": APIConnectionError("Network request failed", code="network_error"),
    "timeout": APITimeoutError("Request timed out after 60000ms", code="timeout"),
    "no-status": PoliPageError("apiKey is required", code="invalid_options"),
}


@pytest.fixture(autouse=True)
def _clear_factory_cache() -> None:
    get_poli_page_client.cache_clear()


def _app(**kwargs: Any) -> FastAPI:
    app = FastAPI(**kwargs)

    @app.get("/raise/{kind}")
    def raise_error(kind: str) -> None:
        if kind == "other":
            raise ValueError("not a Poli Page error")
        raise ERRORS[kind]

    @app.get("/async/raise/{kind}")
    async def raise_error_async(kind: str) -> None:
        raise ERRORS[kind]

    return app


@pytest.mark.parametrize(
    ("kind", "status", "body"),
    [
        pytest.param(
            "api",
            404,
            {
                "code": "TEMPLATE_NOT_FOUND",
                "message": "Template 'does-not-exist' not found in project 'getting-started'.",
                "status": 404,
                "requestId": "req_123",
            },
            id="api-error",
        ),
        pytest.param(
            "network",
            503,
            {
                "code": "network_error",
                "message": "Network request failed",
                "status": 503,
                "requestId": None,
            },
            id="network_error",
        ),
        pytest.param(
            "timeout",
            504,
            {
                "code": "timeout",
                "message": "Request timed out after 60000ms",
                "status": 504,
                "requestId": None,
            },
            id="timeout",
        ),
        pytest.param(
            "no-status",
            500,
            {
                "code": "invalid_options",
                "message": "apiKey is required",
                "status": None,
                "requestId": None,
            },
            id="no-status",
        ),
    ],
)
def test_error_handler_is_on_by_default(kind: str, status: int, body: dict[str, Any]) -> None:
    app = _app()
    setup_poli_page(app)

    response = TestClient(app).get(f"/raise/{kind}")

    assert response.status_code == status
    assert response.headers["content-type"] == "application/json"
    assert response.json() == body


def test_error_handler_answers_an_async_route() -> None:
    app = _app()
    setup_poli_page(app)

    response = TestClient(app).get("/async/raise/api")

    assert response.status_code == 404
    assert response.json() == ERRORS["api"].to_payload()


def test_error_handler_lets_other_exceptions_through() -> None:
    app = _app()
    setup_poli_page(app)

    with pytest.raises(ValueError, match="not a Poli Page error"):
        TestClient(app).get("/raise/other")


def test_error_handler_false_registers_no_handler() -> None:
    app = _app()
    setup_poli_page(app, error_handler=False)

    assert PoliPageError not in app.exception_handlers
    with pytest.raises(NotFoundError):
        TestClient(app).get("/raise/api")
    response = TestClient(app, raise_server_exceptions=False).get("/raise/api")
    assert response.status_code == 500
    assert response.text == "Internal Server Error"


def test_setup_runs_the_client_lifespan_around_the_app_lifespan(
    monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
) -> None:
    monkeypatch.setenv("POLI_PAGE_API_KEY", SANDBOX_KEY)
    mock_client = MagicMock()
    mock_cls = mocker.patch("poli_page_fastapi.dependencies.PoliPage", return_value=mock_client)
    calls: list[str] = []

    @asynccontextmanager
    async def app_lifespan(app: FastAPI) -> AsyncIterator[dict[str, str]]:
        calls.append(f"startup, client built: {mock_cls.call_count}")
        yield {"from": "app lifespan"}
        calls.append(f"shutdown, client closed: {mock_client.close.call_count}")

    app = _app(lifespan=app_lifespan)
    setup_poli_page(app)

    @app.get("/ping")
    def ping() -> dict[str, str]:
        return {"ok": "true"}

    with TestClient(app) as client:
        assert client.get("/ping").status_code == 200
        assert mock_cls.call_count == 1

    # The client is built before the app's startup and closed after its shutdown.
    assert calls == ["startup, client built: 1", "shutdown, client closed: 0"]
    mock_client.close.assert_called_once()


def test_setup_keeps_startup_and_shutdown_handlers(
    monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
) -> None:
    monkeypatch.setenv("POLI_PAGE_API_KEY", SANDBOX_KEY)
    mocker.patch("poli_page_fastapi.dependencies.PoliPage", return_value=MagicMock())
    calls: list[str] = []
    app = _app(on_startup=[lambda: calls.append("startup")])
    setup_poli_page(app)

    with TestClient(app):
        assert calls == ["startup"]
