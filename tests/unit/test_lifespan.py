"""Tests for poli_page_fastapi.lifespan.poli_page_lifespan."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture

from poli_page_fastapi.dependencies import get_poli_page_client
from poli_page_fastapi.lifespan import poli_page_lifespan


@pytest.fixture(autouse=True)
def _clear_factory_cache() -> None:
    get_poli_page_client.cache_clear()


def test_lifespan_warms_and_closes_client(
    monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
) -> None:
    monkeypatch.setenv("POLI_PAGE_API_KEY", "pp_test_x")
    mock_client = MagicMock()
    mock_cls = mocker.patch("poli_page_fastapi.dependencies.PoliPage", return_value=mock_client)

    app = FastAPI(lifespan=poli_page_lifespan)

    @app.get("/ping")
    def ping() -> dict[str, str]:
        return {"ok": "true"}

    with TestClient(app) as client:
        assert mock_cls.call_count == 1
        response = client.get("/ping")
        assert response.status_code == 200
    mock_client.close.assert_called_once()


def test_lifespan_no_warmup_without_context_manager(
    monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
) -> None:
    """Bare TestClient(app).get(...) without `with` skips lifespan.

    Documented in CLAUDE.md §10.2. This test PROVES the gotcha: the
    factory is NOT called when the lifespan doesn't fire.
    """
    monkeypatch.setenv("POLI_PAGE_API_KEY", "pp_test_x")
    mock_cls = mocker.patch("poli_page_fastapi.dependencies.PoliPage")

    app = FastAPI(lifespan=poli_page_lifespan)

    @app.get("/ping")
    def ping() -> dict[str, str]:
        return {"ok": "true"}

    client = TestClient(app)
    client.get("/ping")
    assert mock_cls.call_count == 0
