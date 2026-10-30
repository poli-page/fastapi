# poli-page-fastapi — example app

Self-contained FastAPI app that exercises every method of the Poli Page SDK
via the `poli-page-fastapi` package. The home page (`GET /`) is an
interactive dashboard with one button per SDK feature.

## Run

```bash
cd example-app
uv sync
uv run uvicorn main:app --reload --port 8000
```

Then open <http://localhost:8000>.

## Env

Set `POLI_PAGE_API_KEY` to a sandbox key (`pp_sandbox_...`) in your shell or in
`example-app/.env`. `POLI_PAGE_BASE_URL` is optional. Real
shell exports always win.

The demo renders the `getting-started` project's `welcome` template, which every
organization has in its `sandbox` environment. The key selects the environment, so
no render sends a version.

## Routes

| Path                          | Method | SDK feature                          |
| ----------------------------- | ------ | ------------------------------------ |
| `/`                           | GET    | Interactive dashboard                |
| `/render/pdf`                 | GET    | `client.render.pdf`                  |
| `/render/stream`              | GET    | `client.render.pdf_stream`           |
| `/render/file`                | POST   | `poli_page.fs.render_to_file`        |
| `/documents`                  | POST   | `client.render.document`             |
| `/documents/{id}`             | GET    | `client.documents.get` (302)         |
| `/documents/{id}/thumbnails`  | GET    | `client.documents.thumbnails`        |
| `/documents/{id}/preview`     | GET    | `client.documents.preview`           |
| `/documents/{id}`             | DELETE | `client.documents.delete`            |
| `/errors/not-found`           | GET    | Renders template `does-not-exist` and lets the error through: the default error handler answers `404` with the `to_payload()` body, `{code: "TEMPLATE_NOT_FOUND", message, status, requestId}` |

The app calls `setup_poli_page(app)`: the client is built at startup and closed at
shutdown, and an uncaught `PoliPageError` answers its `to_payload()` JSON.

## Contract tests

`tests/test_contract.py` runs the integration cases of the
[Poli Page API contract](https://github.com/poli-page/api-contract) against this app,
with its SDK pointed at a local mock server:

```bash
uv sync
POLI_CONTRACT=<path to contract.json> uv run pytest
```
