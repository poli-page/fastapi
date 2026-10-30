"""One call to set up the integration on an app: client lifespan and error handler."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from poli_page import PoliPageError

from poli_page_fastapi.exceptions import poli_page_exception_handler
from poli_page_fastapi.lifespan import poli_page_lifespan


def setup_poli_page(app: FastAPI, *, error_handler: bool = True) -> None:
    """Set up Poli Page on `app`. Call it once, before the app starts.

    - Wraps the app's lifespan in `poli_page_lifespan`: the client is built at
      startup and closed at shutdown. The app's own lifespan (or its startup and
      shutdown handlers) still runs, inside it.
    - Registers `poli_page_exception_handler` for `PoliPageError`, unless
      `error_handler=False`: a route that lets a `PoliPageError` through answers
      its `to_payload()` JSON with its status (500 when it has none).

    Usage:

        app = FastAPI()
        setup_poli_page(app)
    """
    if error_handler:
        app.add_exception_handler(PoliPageError, poli_page_exception_handler)

    app_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(lifespan_app: Any) -> AsyncIterator[Any]:
        async with poli_page_lifespan(lifespan_app), app_lifespan(lifespan_app) as state:
            yield state

    app.router.lifespan_context = lifespan
