"""One end-to-end test against the live API.

Skipped unless POLI_PAGE_API_KEY is a sandbox key (pp_sandbox_…): renders with any
other key count toward the organization's PDF quota.

The API is the SDK default base URL, or POLI_PAGE_BASE_URL when it is set (the SDK
reads that variable itself; CI passes the optional secret of the same name).
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
    not os.environ.get("POLI_PAGE_API_KEY", "").startswith("pp_sandbox_"),
    reason="POLI_PAGE_API_KEY is not a sandbox key (pp_sandbox_…)",
)


def _make_dep() -> PoliPageDependency:
    """Build a PoliPageDependency for the configured test environment.

    Module-scope (called immediately below) so that FastAPI's get_type_hints
    pass can resolve `dep` from globals when introspecting the route's
    Annotated[..., Depends(dep)] annotation — locally-scoped dependencies
    don't resolve under `from __future__ import annotations` (PEP 563).
    """
    settings = PoliPageSettings.model_construct(
        api_key=os.environ.get("POLI_PAGE_API_KEY", ""),
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
            "data": {"name": "fastapi integration test"},
        }
    )
    return PdfResponse(pdf, filename="welcome.pdf")


@pytest.mark.integration
def test_render_pdf_against_develop_api() -> None:
    with TestClient(app) as client:
        response = client.get("/render")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content[:5] == b"%PDF-"
    assert len(response.content) > 1000
