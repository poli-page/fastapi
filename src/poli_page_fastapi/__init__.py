"""FastAPI integration for the Poli Page PDF rendering SDK."""

from __future__ import annotations

from poli_page_fastapi._version import __version__
from poli_page_fastapi.dependencies import PoliPageDependency, get_poli_page_client
from poli_page_fastapi.exceptions import poli_page_exception_handler
from poli_page_fastapi.responses import (
    DocumentRedirectResponse,
    PdfResponse,
    PdfStreamResponse,
    PreviewResponse,
)
from poli_page_fastapi.settings import PoliPageSettings

__all__ = [
    "DocumentRedirectResponse",
    "PdfResponse",
    "PdfStreamResponse",
    "PoliPageDependency",
    "PoliPageSettings",
    "PreviewResponse",
    "__version__",
    "get_poli_page_client",
    "poli_page_exception_handler",
]
