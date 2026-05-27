"""ASGI lifespan helper: warm the client at startup, close at shutdown."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from poli_page_fastapi.dependencies import get_poli_page_client


@asynccontextmanager
async def poli_page_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """ASGI lifespan that warms the Poli Page client on startup and closes
    it on shutdown.

    Usage:

        app = FastAPI(lifespan=poli_page_lifespan)
    """
    client = get_poli_page_client()
    try:
        yield
    finally:
        client.close()
        get_poli_page_client.cache_clear()
