# poli-page-fastapi

FastAPI integration for [Poli Page](https://poli.page) — render PDFs in any
FastAPI route with idiomatic `Depends()` injection, pydantic-settings
configuration, and Starlette response subclasses that ship the right
`Content-Type`, RFC 5987 `Content-Disposition`, and `Cache-Control` headers.

This package is a **thin wrapper** around the official Python SDK
[`poli-page`](https://pypi.org/project/poli-page/). It does not reimplement
HTTP transport, retries, error classification, idempotency, or streaming —
the SDK already does. It exists for one reason: to plug the SDK into a
FastAPI app the way a Pythonista would expect.

## Install

```bash
pip install poli-page-fastapi
# or: uv add poli-page-fastapi
```

`fastapi`, `pydantic`, `pydantic-settings`, and `poli-page` come along
automatically.

## Quick start

```python
from typing import Annotated

from fastapi import Depends, FastAPI
from poli_page import PoliPage, PoliPageError
from poli_page_fastapi import (
    PdfResponse,
    get_poli_page_client,
    poli_page_exception_handler,
    poli_page_lifespan,
)

app = FastAPI(lifespan=poli_page_lifespan)
app.add_exception_handler(PoliPageError, poli_page_exception_handler)

Client = Annotated[PoliPage, Depends(get_poli_page_client)]


@app.get("/invoice/{invoice_id}.pdf", response_class=PdfResponse)
def invoice_pdf(invoice_id: str, client: Client) -> PdfResponse:
    pdf = client.render.pdf({
        "project": "invoices",
        "template": "monthly",
        "version": "1.4.0",
        "data": {"invoice_id": invoice_id},
    })
    return PdfResponse(pdf, filename=f"invoice-{invoice_id}.pdf")
```

Set `POLI_PAGE_API_KEY=pp_test_...` in your environment and run with
`uvicorn main:app`. Hitting `GET /invoice/42.pdf` returns a real PDF with
the correct headers.

## Settings

`PoliPageSettings` is a pydantic-settings reader. By default it builds
the client from `POLI_PAGE_*` env vars and matches the SDK's own kwargs
1:1 — anything left unset falls through to the SDK's defaults.

| Env var                  | Field         | Type   | Notes                                       |
| ------------------------ | ------------- | ------ | ------------------------------------------- |
| `POLI_PAGE_API_KEY`      | `api_key`     | `str`  | Must start with `pp_test_` or `pp_live_`.   |
| `POLI_PAGE_BASE_URL`     | `base_url`    | `str`  | Override for sandbox/regional endpoints.    |
| `POLI_PAGE_TIMEOUT`      | `timeout`     | `float`| Per-request timeout in seconds (0, 600].    |
| `POLI_PAGE_MAX_RETRIES`  | `max_retries` | `int`  | Retries per failed request, [0, 10].        |
| `POLI_PAGE_RETRY_DELAY`  | `retry_delay` | `float`| Initial backoff in seconds, [0, 30].        |

The package never calls `load_dotenv()` itself — loading a `.env` file
is your call (typically once in `main.py` before instantiating `FastAPI`,
or via pydantic-settings' own `SettingsConfigDict(env_file=".env")`).

## Dependency injection

### The factory — `get_poli_page_client`

The canonical access path. It's `@lru_cache(maxsize=1)`-memoised, so every
`Depends(get_poli_page_client)` in your app shares the same `PoliPage`
instance for the life of the process.

```python
from typing import Annotated
from fastapi import Depends
from poli_page import PoliPage
from poli_page_fastapi import get_poli_page_client

Client = Annotated[PoliPage, Depends(get_poli_page_client)]


@app.get("/pdf")
def render(client: Client) -> PdfResponse:
    ...
```

### The class — `PoliPageDependency`

Use it when you need a per-router or per-endpoint client with explicit
settings — a sandbox client alongside production, or a dependency that
takes a pre-built mock in tests.

```python
from poli_page_fastapi import PoliPageDependency, PoliPageSettings

sandbox = PoliPageDependency(
    settings=PoliPageSettings(api_key="pp_test_sandbox", base_url="..."),
)


@app.get("/sandbox/pdf")
def sandbox_render(client: Annotated[PoliPage, Depends(sandbox)]) -> PdfResponse:
    ...
```

Each instance memoises its own client. Call `sandbox.close()` when you
need to release it explicitly (typically on shutdown).

## Response helpers

All four subclass Starlette's `Response` / `StreamingResponse` and set the
right headers — `Content-Type`, RFC 5987-encoded `Content-Disposition`
(handles non-ASCII filenames), `Cache-Control: no-store, private`,
`X-Content-Type-Options: nosniff`.

| Class                       | Wraps                | Typical use                                    |
| --------------------------- | -------------------- | ---------------------------------------------- |
| `PdfResponse`               | `Response`           | `client.render.pdf` — bytes in memory.         |
| `PdfStreamResponse`         | `StreamingResponse`  | `client.render.pdf_stream` — chunked iterator. |
| `PreviewResponse`           | `Response`           | `client.render.preview` — HTML preview.        |
| `DocumentRedirectResponse`  | `Response` (302/308) | Redirect to a presigned PDF URL.               |

Pass `inline=True` on the PDF responses to flip the disposition from
`attachment` to `inline` (browsers render in-place).

## Error handling

The SDK raises one exception family: `PoliPageError` with status-specific
subclasses (`BadRequestError`, `RateLimitError`, `APIConnectionError`, …).
You have two ways to surface them as HTTP responses.

### Opt-in: a global handler

Register `poli_page_exception_handler` once and the SDK's typed exceptions
become typed JSON responses for every route:

```python
from poli_page import PoliPageError
from poli_page_fastapi import poli_page_exception_handler

app.add_exception_handler(PoliPageError, poli_page_exception_handler)
```

| Exception                       | HTTP | Body                                  |
| ------------------------------- | ---- | ------------------------------------- |
| `APIStatusError` (4xx/5xx)      | same | `{code, message, request_id}`         |
| `APIConnectionError` / Timeout  | 502  | `{code, message, request_id}`         |
| `PoliPageError` (catch-all)     | 500  | `{code, message, request_id}`         |
| Any other exception             | 500  | `{code: "UNKNOWN", message, ...}`     |

### Per-endpoint `try/except`

When you want bespoke handling (custom fallback, escalation, etc.) just
catch directly:

```python
from poli_page import PoliPageError, RateLimitError


@app.get("/pdf")
def render(client: Client) -> Response:
    try:
        pdf = client.render.pdf({...})
    except RateLimitError as exc:
        return JSONResponse(
            status_code=429,
            content={"retry_after": exc.response.headers.get("Retry-After")},
        )
    except PoliPageError as exc:
        # ... your fallback
        raise
    return PdfResponse(pdf, filename="invoice.pdf")
```

The two patterns compose — `try/except` inside a route wins over the
global handler for that path.

## Async endpoints

The SDK exposes both a sync `PoliPage` and an `AsyncPoliPage`; this
package wires the **sync** client in v0.1.0. FastAPI runs sync routes
in a threadpool automatically, so the synchronous client is safe to
call from any `def` route.

For `async def` routes, dispatch the SDK call through Starlette's
threadpool to keep the event loop free:

```python
from starlette.concurrency import run_in_threadpool


@app.get("/pdf")
async def render(client: Client) -> PdfResponse:
    pdf = await run_in_threadpool(
        client.render.pdf,
        {"project": "...", "template": "...", "version": "...", "data": {}},
    )
    return PdfResponse(pdf, filename="invoice.pdf")
```

Native `AsyncPoliPage` support lands in v0.2.

## Testing

Use FastAPI's first-class `app.dependency_overrides` to inject a mock.
This is the idiomatic FastAPI test pattern and the right way to bypass
the `lru_cache`-memoised factory:

```python
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from poli_page_fastapi import get_poli_page_client


def test_invoice_pdf() -> None:
    mock_client = MagicMock()
    mock_client.render.pdf.return_value = b"%PDF-1.4\n..."

    app.dependency_overrides[get_poli_page_client] = lambda: mock_client
    try:
        with TestClient(app) as client:
            response = client.get("/invoice/42.pdf")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.content[:5] == b"%PDF-"
```

Two things to remember:

1. **Use `TestClient` as a context manager** (`with TestClient(app) as
   client:`). Bare `TestClient(app).get(...)` skips ASGI lifespan events,
   so `poli_page_lifespan` never fires.
2. **Clear overrides afterwards** — they persist across tests within the
   same `app` object.

## Lifespan (optional)

`FastAPI(lifespan=poli_page_lifespan)` warms the client at startup (the
`PoliPageSettings()` constructor runs at process boot, surfacing missing
or malformed env early) and closes it cleanly at shutdown. It is optional
— without it, the first request that uses `Depends(get_poli_page_client)`
triggers the same lazy build.

```python
from poli_page_fastapi import poli_page_lifespan

app = FastAPI(lifespan=poli_page_lifespan)
```

Compose with your own lifespan if you have one — wrap them in an
`@asynccontextmanager` that yields after delegating to ours.

## Example app

A self-contained FastAPI app with an interactive demo dashboard lives
under [`example-app/`](./example-app/). One button per SDK feature,
inline iframe PDF previews, document-lifecycle state machine in vanilla
JS. Run it with `uv run uvicorn main:app --reload`.

## What this package is *not*

- **Not a re-implementation** of the SDK. HTTP, retries, error mapping,
  idempotency keys, and stream chunking live in
  [`poli-page`](https://pypi.org/project/poli-page/). Bug in any of
  those areas? Open an issue against the SDK.
- **Not a Starlette middleware**. The exception handler is the
  integration point — opt-in, per the same philosophy as
  `@poli-page/nestjs`.
- **Not a CLI**. FastAPI ships no per-app CLI surface; `uvicorn` is the
  smoke test.

## Compatibility

- Python 3.11, 3.12, 3.13
- FastAPI `^0.100`, `^0.110` (other 0.x versions likely work; tested
  against these two)
- Pydantic v2 + pydantic-settings v2

## Documentation

- Poli Page docs: [docs.poli.page](https://docs.poli.page)
- SDK reference: [docs.poli.page/reference/sdk/python](https://docs.poli.page/reference/sdk/python/)
- Spec & implementation plan: [`docs/`](./docs/)

## License

MIT — see [LICENSE](./LICENSE).
