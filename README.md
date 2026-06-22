# poli-page-fastapi

> Render Poli Page documents from FastAPI endpoints.

## About

This package exposes the Poli Page Python SDK as a FastAPI dependency: a memoised client factory you inject with `Depends()`, Starlette response subclasses that ship the correct PDF headers, and a pydantic-settings reader for `POLI_PAGE_*` env vars. It is a thin wrapper around [`poli-page`](https://pypi.org/project/poli-page/) — the SDK owns transport, retries, error classification, and stream chunking.

**When to use this:**

- You return generated PDFs from FastAPI routes and want `Depends()` instead of a hand-rolled global client.
- You want correct `Content-Type`, RFC 5987 `Content-Disposition`, and `Cache-Control` headers without writing them yourself.
- You want exceptions raised by the SDK to surface as typed JSON responses.

**When not to:**

- You are not on FastAPI — use [`poli-page`](https://pypi.org/project/poli-page/) directly, or the integration for your framework.
- You need a CLI command, an `APIRoute` subclass, or an automatic OpenAPI extension — this package ships none of those by design.

## Requirements

- Python 3.11, 3.12, or 3.13
- FastAPI `>=0.100,<1.0`
- Pydantic v2 and pydantic-settings v2

## Install

```bash
pip install poli-page-fastapi
```

Set the API key in your environment before the app starts:

```bash
# .env (or your shell)
POLI_PAGE_API_KEY=pp_test_...
```

Get a key at [app.poli.page/settings/api-keys](https://app.poli.page/settings/api-keys). The package does not call `load_dotenv()` for you — load the file yourself, or rely on pydantic-settings' `SettingsConfigDict(env_file=...)`.

## Quick start

```python
# main.py
from typing import Annotated

from fastapi import Depends, FastAPI
from poli_page import PoliPage
from poli_page_fastapi import PdfResponse, get_poli_page_client

app = FastAPI()

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

Run with `uvicorn main:app` and `GET /invoice/42.pdf` returns a PDF with the correct headers.

## Configuration

`PoliPageSettings` reads `POLI_PAGE_*` env vars and maps one-to-one with the SDK's `PoliPage(__init__)` kwargs. Unset fields fall through to the SDK's defaults.

| Env var                  | Field         | Type    | Notes                                       |
| ------------------------ | ------------- | ------- | ------------------------------------------- |
| `POLI_PAGE_API_KEY`      | `api_key`     | `str`   | Must start with `pp_test_` or `pp_live_`.   |
| `POLI_PAGE_BASE_URL`     | `base_url`    | `str`   | Override for sandbox or regional endpoints. |
| `POLI_PAGE_TIMEOUT`      | `timeout`     | `float` | Per-request timeout in seconds, `(0, 600]`. |
| `POLI_PAGE_MAX_RETRIES`  | `max_retries` | `int`   | Retries per failed request, `[0, 10]`.      |
| `POLI_PAGE_RETRY_DELAY`  | `retry_delay` | `float` | Initial backoff in seconds, `[0, 30]`.      |

To use explicit settings on a per-router or per-endpoint basis, pass a `PoliPageSettings` instance to `PoliPageDependency`:

```python
# main.py
from poli_page_fastapi import PoliPageDependency, PoliPageSettings

sandbox = PoliPageDependency(
    settings=PoliPageSettings(api_key="pp_test_sandbox"),
)
```

## API at a glance

| Symbol                      | Purpose                                                                |
| --------------------------- | ---------------------------------------------------------------------- |
| `get_poli_page_client`      | `@lru_cache` memoised factory — the canonical `Depends(...)` target.   |
| `PoliPageDependency`        | Class-based dependency for per-router or per-instance settings.        |
| `PoliPageSettings`          | Pydantic-settings reader for `POLI_PAGE_*` env vars.                   |
| `PdfResponse`               | `Response` subclass for `client.render.pdf` bytes.                     |
| `PdfStreamResponse`         | `StreamingResponse` subclass for `client.render.pdf_stream` iterators. |
| `PreviewResponse`           | HTML preview response for `client.render.preview`.                     |
| `DocumentRedirectResponse`  | 302/308 redirect to a presigned document URL.                          |
| `poli_page_exception_handler` | Opt-in global handler mapping SDK exceptions to JSON responses.      |
| `poli_page_lifespan`        | ASGI lifespan that warms the client on startup and closes on shutdown. |

Full reference: [docs/api.md](docs/api.md).

## Errors

The SDK raises one exception family rooted at `PoliPageError`. The four categories in the shared taxonomy map to these SDK classes:

- **Auth** — `AuthenticationError`
- **Rate limit** — `RateLimitError`
- **Request rejected** — `BadRequestError`, `UnprocessableEntityError` (4xx subclasses of `APIStatusError`)
- **Network / transport** — `APIConnectionError`, `APITimeoutError`

Catch them per endpoint:

```python
# main.py
from fastapi.responses import JSONResponse
from poli_page import PoliPageError, RateLimitError


@app.get("/invoice/{invoice_id}.pdf")
def invoice_pdf(invoice_id: str, client: Client) -> PdfResponse:
    try:
        pdf = client.render.pdf({"project": "...", "template": "...", "version": "...", "data": {}})
    except RateLimitError as exc:
        return JSONResponse(
            status_code=429,
            content={"retry_after": exc.response.headers.get("Retry-After")},
        )
    return PdfResponse(pdf, filename=f"invoice-{invoice_id}.pdf")
```

Or register `poli_page_exception_handler` once to map every `PoliPageError` to a typed JSON response — see [docs/errors.md](docs/errors.md).

## Example app

[`example-app/`](./example-app/) is a self-contained FastAPI app with an interactive dashboard at `GET /`. It exercises every SDK method — `render.pdf`, `render.pdf_stream`, `render.preview`, `render.document`, document retrieval, thumbnails, and deletion — and demonstrates `Depends()`, the response helpers, the exception handler, and lifespan wiring.

```bash
cd example-app
uv sync
uv run uvicorn main:app --reload --port 8000
```

Open <http://localhost:8000>.

## Going further

The following deep dives are forthcoming under `docs/`:

- `docs/lifespan.md` — wiring `poli_page_lifespan` and composing it with your own ASGI lifespan.
- `docs/async.md` — calling the sync client from `async def` routes via `run_in_threadpool`, and the path to native `AsyncPoliPage` in v0.2.
- `docs/testing.md` — overriding `get_poli_page_client` with `app.dependency_overrides`, and the `TestClient` context-manager requirement.
- `docs/errors.md` — the full status mapping the global exception handler applies.
- `docs/responses.md` — RFC 5987 filename encoding, `inline=True`, and streaming responses.

## Compatibility

| Package version | FastAPI                | Python              |
| --------------- | ---------------------- | ------------------- |
| 0.1.x           | `^0.100`, `^0.110`     | 3.11, 3.12, 3.13    |

Tested against the FastAPI versions listed above; other 0.x releases in that range are expected to work. The SDK is pinned to `poli-page>=0.9,<2`.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Released under the MIT License — see [LICENSE](./LICENSE).
