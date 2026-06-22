"""One end-to-end test against the live API.

Skipped automatically when POLI_PAGE_API_KEY is unset. Refuses to run with
a pp_live_* key. Target a non-default environment by setting
POLI_PAGE_TEST_BASE_URL.
"""

from __future__ import annotations

import os
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from poli_page import PoliPage

from poli_page_fastapi import (
    PdfResponse,
    PoliPageDependency,
    PoliPageSettings,
    poli_page_lifespan,
)

pytestmark = pytest.mark.skipif(
    os.environ.get("POLI_PAGE_API_KEY") is None,
    reason="POLI_PAGE_API_KEY env var not set",
)


def _check_test_key() -> str:
    key = os.environ["POLI_PAGE_API_KEY"]
    if key.startswith("pp_live_"):
        pytest.fail("Integration test refuses to run with a pp_live_* key.")
    return key


def _make_dep() -> PoliPageDependency:
    """Build a PoliPageDependency for the configured test environment.

    Module-scope (called immediately below) so that FastAPI's get_type_hints
    pass can resolve `dep` from globals when introspecting the route's
    Annotated[..., Depends(dep)] annotation — locally-scoped dependencies
    don't resolve under `from __future__ import annotations` (PEP 563).
    """
    settings = PoliPageSettings.model_construct(
        api_key=os.environ.get("POLI_PAGE_API_KEY", ""),
        base_url=os.environ.get("POLI_PAGE_TEST_BASE_URL"),
    )
    return PoliPageDependency(settings=settings)


dep = _make_dep()
app = FastAPI(lifespan=poli_page_lifespan)


@app.get("/render", response_class=PdfResponse)
def render(client: Annotated[PoliPage, Depends(dep)]) -> PdfResponse:
    pdf = client.render.pdf(
        {
            "project": "getting-started",
            "template": "welcome",
            "version": "1.0.0",
            "data": {"name": "fastapi integration test"},
        }
    )
    return PdfResponse(pdf, filename="welcome.pdf")


@pytest.mark.integration
def test_render_pdf_against_develop_api() -> None:
    _check_test_key()
    with TestClient(app) as client:
        response = client.get("/render")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content[:5] == b"%PDF-"
    assert len(response.content) > 1000
