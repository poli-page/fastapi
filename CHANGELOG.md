# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- The live API CI job passes the optional `POLI_PAGE_BASE_URL` secret to the integration test (unset: the SDK default), next to the `pp_sandbox_` key in `POLI_PAGE_API_KEY`.

## [0.11.0] - 2026-10-30

First release. The version matches the `poli-page` SDK 0.11.0 it requires.

### Added
- `PoliPageSettings(BaseSettings)` — pydantic-settings reader for
  `POLI_PAGE_API_KEY` / `POLI_PAGE_BASE_URL` / `POLI_PAGE_TIMEOUT` /
  `POLI_PAGE_MAX_RETRIES` / `POLI_PAGE_RETRY_DELAY`. Validates the
  `POLI_PAGE_TIMEOUT`, `POLI_PAGE_MAX_RETRIES` and `POLI_PAGE_RETRY_DELAY`
  ranges at construction time; a key that does not match
  `pp_{environment}_{32 hex}` logs one warning.
- `get_poli_page_client()` — `@lru_cache(maxsize=1)` memoised factory,
  the canonical `Depends(...)` target. Tests inject mocks via
  `app.dependency_overrides[get_poli_page_client]`.
- `PoliPageDependency` — class-based dependency for per-router clients
  or explicit settings overrides.
- `PdfResponse`, `PdfStreamResponse`, `PreviewResponse`,
  `DocumentRedirectResponse` — Starlette response subclasses with
  correct `Content-Type`, RFC 5987-encoded `Content-Disposition`,
  `Cache-Control: no-store, private`, and `X-Content-Type-Options:
  nosniff`. PDF responses accept `inline=True` to flip the disposition.
- `poli_page_exception_handler` — answers a `PoliPageError` with the
  SDK's `to_payload()` body and its status (503 `network_error`, 504
  `timeout`, 500 when none); any other exception is re-raised.
  `setup_poli_page` registers it by default;
  `app.add_exception_handler(PoliPageError, poli_page_exception_handler)`
  registers it by hand.
- `poli_page_lifespan` — async context manager for
  `FastAPI(lifespan=...)` that warms the client at startup and closes
  it (plus clears the factory cache) at shutdown.
- `example-app/` — runnable FastAPI demo with an interactive dashboard
  at `GET /` exercising every SDK feature.
- `setup_poli_page(app, *, error_handler=True)`: wraps the app's lifespan in `poli_page_lifespan` (the app's own lifespan and startup/shutdown handlers still run) and registers the error handler, on by default. A `PoliPageError` a route lets through answers `application/json` with the SDK's `to_payload()` body, `{code, message, status, requestId}`, and its `status` (`503` for `network_error`, `504` for `timeout`, `500` when the error has none). `error_handler=False` turns it off.
- `PdfStreamResponse` accepts the SDK stream as is (`PdfStreamResponse(client.render.pdf_stream(input))`): it enters the stream at once, so a render or download error raises in the route and reaches the error handler, and closes it when the response ends: read to the end, failed, or the client disconnected. Iterators are still accepted.
- `app = FastAPI()` + `setup_poli_page(app)` sets up both the lifespan and the error handler; `poli_page_lifespan` and `poli_page_exception_handler` stay available to wire by hand. `setup_poli_page` raises `RuntimeError` if the app has already started.
- Contract tests: `example-app/tests/test_contract.py` runs the API contract's integration cases (`impl.*`) against the example app. CI runs them against the pinned `poli-page/api-contract` v1.3.0, and Dependabot proposes each new contract version.
- Release workflow (`.github/workflows/release.yml`): a `vX.Y.Z` tag runs the test suite against the pinned API contract, publishes the wheel and sdist to PyPI through Trusted Publishing, and creates the GitHub Release. See `RELEASING.md`.

### Changed (breaking)
- `PoliPageSettings` accepts environment keys (`pp_{environment}_{32 lowercase hex}`, for example `pp_sandbox_…`, `pp_live_…`, `pp_staging_…`). It no longer raises on a key that is not `pp_test_…` / `pp_live_…`: a missing or empty `POLI_PAGE_API_KEY` still fails when the client is built, any other value is accepted, and a value that does not match the key format logs one warning that shows no part of the key (not even its `pp_{environment}_` prefix) before the API decides. An explicit `PoliPageSettings(api_key=None)` or `api_key=""` leaves the SDK to read `POLI_PAGE_API_KEY`, and that value gets the same check.
- Requires the `poli-page` SDK 0.11.0 (`poli-page>=0.11.0,<2`, from PyPI), the first release with environment API keys and no template versions: render inputs carry no `version` and `render.preview` is gone. A missing key now raises the SDK's `PoliPageError` with the message `apiKey is required` (code `invalid_options`).
- `poli_page_exception_handler` answers with the SDK's `to_payload()` body as is: an error with no status answers `500` with `"status": null` in the body (it used to copy `500` into the body). Any exception that is not a `PoliPageError` is re-raised instead of being answered as a hand-built `{"code": "UNKNOWN", …}`.
- `PreviewResponse` is documented for `client.documents.preview` (the stored HTML of a rendered document).
- Example app: no `version` in any render; `GET /errors/not-found` (template `does-not-exist`, `404 TEMPLATE_NOT_FOUND`) replaces `GET /errors/bad-version`. The app is set up with `setup_poli_page(app)`, so that route answers through the default error handler. `GET /render/stream` passes the SDK stream to `PdfStreamResponse`, so a render error answers the handler's JSON instead of a `200` PDF with an empty body. The app loads `example-app/.env` instead of a `.env` above the repository.
- The integration test runs only with a sandbox key (`pp_sandbox_…`).

### CI
- The live API job runs on `main` (and on demand) against the production API with the sandbox key from the `POLI_PAGE_API_KEY` secret, and skips with a notice when the key is absent or not a `pp_sandbox_` key.

### Removed
- Example app: `GET /render/preview` and its dashboard button (`render.preview` no longer exists in the SDK).

### Fixed
- `PdfResponse` / `PdfStreamResponse`: the `Content-Disposition` filename is now escaped per RFC 6266 / RFC 9110 (`\` and `"` as quoted-pairs, ASCII fallback included) and stripped of control characters (CR/LF, TAB, DEL, C1), so a filename can no longer break the header or inject parameters.

### Compatibility
- Python 3.11, 3.12, 3.13
- FastAPI `^0.100`, `^0.110`
- Pydantic v2 + pydantic-settings v2
- `poli-page>=0.11.0,<2`

[Unreleased]: https://github.com/poli-page/fastapi/compare/v0.11.0...HEAD
[0.11.0]: https://github.com/poli-page/fastapi/releases/tag/v0.11.0
