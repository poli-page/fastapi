"""FastAPI integration for the Poli Page PDF rendering SDK."""

from __future__ import annotations

from poli_page_fastapi._version import __version__
from poli_page_fastapi.settings import PoliPageSettings

__all__ = [
    "PoliPageSettings",
    "__version__",
]
