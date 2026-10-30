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
- The `poli-page` Python SDK 0.11.0 or later (installed with the package, `poli-page>=0.11.0,<2`)

## Install

```bash
pip install poli-page-fastapi
```

This installs the `poli-page` SDK 0.11.0 or later with it.

Set the API key in your environment before the app starts:

```bash
# .env (or your shell)
POLI_PAGE_API_KEY=pp_sandbox_...
```

Get a key at [app.poli.page/settings/api-keys](https://app.poli.page/settings/api-keys). The package does not call `load_dotenv()` for you — load the file yourself, or rely on pydantic-settings' `SettingsConfigDict(env_file=...)`.

## API keys

A key is `pp_{environment}_{32 lowercase hex}` and belongs to one environment of your organization. The key alone selects the environment, and so which published copy of a project renders: render inputs carry no version.

| Environment                           | Key            | Watermark | Counted |
| ------------------------------------- | -------------- | --------- | ------- |
| `sandbox` (every org)                 | `pp_sandbox_…` | yes       | no      |
| `live` (every org, deletable on Pro+) | `pp_live_…`    | no        | yes     |
| created on Pro+ (e.g. `staging`)      | `pp_staging_…` | no        | yes     |

"Counted" means the render counts toward the organization's monthly PDF quota.

The API is the only authority on keys. This package checks only that `POLI_PAGE_API_KEY` is set and not empty. A value that does not match `pp_{environment}_{32 lowercase hex}` logs one warning through the `poli_page_fastapi.settings` logger, which names the expected format and shows no part of the key, and the client starts anyway: the API answers `401 INVALID_API_KEY` (or `401 MISSING_API_KEY` for a value without `pp_`) if the key is not valid. A key passed explicitly (`PoliPageSettings(api_key=…)`) gets the same check. When that explicit value is `None` or empty, the client is built without a key and the SDK reads `POLI_PAGE_API_KEY` itself, so that value is checked instead.

## Quick start

```python
# main.py
from typing import Annotated

from fastapi import Depends, FastAPI
from poli_page import PoliPage
from poli_page_fastapi import PdfResponse, get_poli_page_client, setup_poli_page

app = FastAPI()
setup_poli_page(app)  # client lifespan + error handler

Client = Annotated[PoliPage, Depends(get_poli_page_client)]


@app.get("/invoice/{invoice_id}.pdf", response_class=PdfResponse)
def invoice_pdf(invoice_id: str, client: Client) -> PdfResponse:
    pdf = client.render.pdf({
        "project": "invoices",
        "template": "monthly",
        "data": {"invoice_id": invoice_id},
    })
    return PdfResponse(pdf, filename=f"invoice-{invoice_id}.pdf")
```

Run with `uvicorn main:app` and `GET /invoice/42.pdf` returns a PDF with the correct headers. `setup_poli_page(app)` builds the client at startup, closes it at shutdown (your own `lifespan` still runs, inside it), and registers the error handler (see [Errors](#errors)).

## Configuration

`PoliPageSettings` reads `POLI_PAGE_*` env vars and maps one-to-one with the SDK's `PoliPage(__init__)` kwargs. Unset fields fall through to the SDK's defaults.

| Env var                  | Field         | Type    | Notes                                       |
| ------------------------ | ------------- | ------- | ------------------------------------------- |
| `POLI_PAGE_API_KEY`      | `api_key`     | `str`   | Required: missing or empty, building the client raises `PoliPageError`. A value that is not `pp_{environment}_{32 lowercase hex}` logs one warning, then the API decides (see [API keys](#api-keys)). |
| `POLI_PAGE_BASE_URL`     | `base_url`    | `str`   | Override for sandbox or regional endpoints. |
| `POLI_PAGE_TIMEOUT`      | `timeout`     | `float` | Per-request timeout in seconds, `(0, 600]`. |
| `POLI_PAGE_MAX_RETRIES`  | `max_retries` | `int`   | Retries per failed request, `[0, 10]`.      |
| `POLI_PAGE_RETRY_DELAY`  | `retry_delay` | `float` | Initial backoff in seconds, `[0, 30]`.      |

To use explicit settings on a per-router or per-endpoint basis, pass a `PoliPageSettings` instance to `PoliPageDependency`:

```python
# main.py
import os

from poli_page_fastapi import PoliPageDependency, PoliPageSettings

sandbox = PoliPageDependency(
    settings=PoliPageSettings(api_key=os.environ["POLI_PAGE_API_KEY"]),
)
```

## API at a glance

| Symbol                      | Purpose                                                                |
| --------------------------- | ---------------------------------------------------------------------- |
| `get_poli_page_client`      | `@lru_cache` memoised factory — the canonical `Depends(...)` target.   |
| `PoliPageDependency`        | Class-based dependency for per-router or per-instance settings.        |
| `PoliPageSettings`          | Pydantic-settings reader for `POLI_PAGE_*` env vars.                   |
| `PdfResponse`               | `Response` subclass for `client.render.pdf` bytes.                     |
| `PdfStreamResponse`         | `StreamingResponse` subclass for `client.render.pdf_stream(...)`: pass the SDK stream as is, so SDK errors reach the error handler. |
| `PreviewResponse`           | `text/html` response for the stored HTML from `client.documents.preview`. |
| `DocumentRedirectResponse`  | 302/308 redirect to a presigned document URL.                          |
| `setup_poli_page`           | Sets up an app: the client lifespan and the error handler (on by default). |
| `poli_page_exception_handler` | The error handler: answers a `PoliPageError` with its `to_payload()` JSON. |
| `poli_page_lifespan`        | ASGI lifespan that warms the client on startup and closes on shutdown. |

Full reference: [docs/api.md](docs/api.md).

## Errors

### Error handler (on by default)

`setup_poli_page(app)` registers `poli_page_exception_handler` for `PoliPageError`. A route that lets an SDK error through answers JSON:

- the body is the SDK's `exc.to_payload()`, exactly `{"code", "message", "status", "requestId"}`;
- the HTTP status is that payload's `status`: the API's status for an API error, `503` for `network_error`, `504` for `timeout`, and `500` when the error has none (the body's `status` is then `null`);
- `Content-Type: application/json`, with `Cache-Control: no-store, private`.

```json
{
  "code": "TEMPLATE_NOT_FOUND",
  "message": "Template 'does-not-exist' not found in project 'getting-started'.",
  "status": 404,
  "requestId": "req_..."
}
```

Other exceptions are not touched. To handle SDK errors yourself, turn the handler off:

```python
setup_poli_page(app, error_handler=False)
```

`FastAPI(lifespan=poli_page_lifespan)` on its own registers no handler: use `setup_poli_page(app)` instead (not both, or the client lifespan runs twice), or register the handler yourself with `app.add_exception_handler(PoliPageError, poli_page_exception_handler)`. Call `setup_poli_page` before the app starts; afterwards it raises `RuntimeError`.

For a streamed PDF, pass the SDK stream to `PdfStreamResponse` as is, `PdfStreamResponse(client.render.pdf_stream(input))`, instead of opening it inside a generator: an error raised once the body is streaming comes after the `200` is sent, and no handler can answer it. The response closes the stream when it ends, including when the client disconnects, and before it runs a `background` task. Opening the stream sends the render and the download's first request synchronously, so build the response in a `def` route (FastAPI runs it in its threadpool), or through `run_in_threadpool` in an `async def` route.

### Error types

The SDK raises one exception family rooted at `PoliPageError`. The four categories in the shared taxonomy map to these SDK classes:

- **Auth** — `AuthenticationError`
- **Rate limit** — `RateLimitError`
- **Request rejected** — `BadRequestError`, `UnprocessableEntityError` (4xx subclasses of `APIStatusError`)
- **Network / transport** — `APIConnectionError`, `APITimeoutError`

Catch one in the route when it needs its own answer:

```python
# main.py
from fastapi.responses import JSONResponse
from poli_page import RateLimitError


@app.get("/invoice/{invoice_id}.pdf")
def invoice_pdf(invoice_id: str, client: Client) -> PdfResponse:
    try:
        pdf = client.render.pdf({"project": "...", "template": "...", "data": {}})
    except RateLimitError as exc:
        return JSONResponse(
            status_code=429,
            content={"retry_after": exc.response.headers.get("Retry-After")},
        )
    return PdfResponse(pdf, filename=f"invoice-{invoice_id}.pdf")
```

## Example app

[`example-app/`](./example-app/) is a self-contained FastAPI app with an interactive dashboard at `GET /`. It exercises every SDK method — `render.pdf`, `render.pdf_stream`, `render.document`, document retrieval, `documents.preview`, thumbnails, and deletion — and demonstrates `setup_poli_page()`, `Depends()`, the response helpers and the default error handler (`GET /errors/not-found` answers `404 TEMPLATE_NOT_FOUND`). Set `POLI_PAGE_API_KEY` to a sandbox key (`pp_sandbox_…`); `POLI_PAGE_BASE_URL` is optional.

```bash
cd example-app
uv sync
uv run uvicorn main:app --reload --port 8000
```

Open <http://localhost:8000>.

## Going further

The following deep dives are forthcoming under `docs/`:

- `docs/lifespan.md` — wiring `poli_page_lifespan` by hand instead of `setup_poli_page`.
- `docs/async.md` — calling the sync client from `async def` routes via `run_in_threadpool`, and the path to native `AsyncPoliPage` in v0.2.
- `docs/testing.md` — overriding `get_poli_page_client` with `app.dependency_overrides`, and the `TestClient` context-manager requirement.
- `docs/errors.md` — the full status mapping the global exception handler applies.
- `docs/responses.md` — RFC 5987 filename encoding, `inline=True`, and streaming responses.

## Compatibility

| Package version | FastAPI                | Python              |
| --------------- | ---------------------- | ------------------- |
| 0.11.x          | `^0.100`, `^0.110`     | 3.11, 3.12, 3.13    |

Tested against the FastAPI versions listed above; other 0.x releases in that range are expected to work. The SDK requirement is `poli-page>=0.11.0,<2`.

## Contributing

Run the checks CI runs from the repository root: `uv sync --all-extras`, then `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src tests example-app/tests` and `uv run pytest tests/unit`.

### Contract tests

`example-app/tests/test_contract.py` runs the integration cases (`kind: "impl"`) of the [Poli Page API contract](https://github.com/poli-page/api-contract) against the example app: a local server plays the API, the app's SDK points at it through `POLI_PAGE_BASE_URL`, and FastAPI's `TestClient` checks each answer. CI runs them against the contract version pinned in `.github/workflows/ci.yml`. Locally:

```bash
cd example-app
uv sync
POLI_CONTRACT=<path to contract.json> uv run pytest
```

Without `POLI_CONTRACT` the test is skipped (in CI it fails). `example-app/tests/contract-skip.json` lists the cases allowed to fail, each with its reason.

## License

Released under the MIT License — see [LICENSE](./LICENSE).
