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

Set `POLI_PAGE_API_KEY` to a sandbox key (`pp_sandbox_...`) in the workspace-root
`.env` (two levels up from `example-app/`). `POLI_PAGE_BASE_URL` is optional. Real
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
| `/errors/not-found`           | GET    | Renders template `does-not-exist`: `404 TEMPLATE_NOT_FOUND` with `code`, `status`, `message`, `requestId` |
