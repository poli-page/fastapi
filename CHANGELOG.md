# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] — 2026-05-27

### Added
- `PoliPageSettings(BaseSettings)` — pydantic-settings reader for
  `POLI_PAGE_API_KEY` / `POLI_PAGE_BASE_URL` / `POLI_PAGE_TIMEOUT` /
  `POLI_PAGE_MAX_RETRIES` / `POLI_PAGE_RETRY_DELAY`. Validates the
  `pp_test_` / `pp_live_` API-key prefix and numeric ranges at
  construction time.
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
- `poli_page_exception_handler` — opt-in handler registered via
  `app.add_exception_handler(PoliPageError, ...)` mapping every SDK
  exception subclass to a typed JSON response (`{code, message,
  request_id}`). 4xx/5xx mirror the API status; transport errors map
  to 502; bare `PoliPageError` maps to 500; non-SDK exceptions surface
  as 500 with `code: "UNKNOWN"`.
- `poli_page_lifespan` — async context manager for
  `FastAPI(lifespan=...)` that warms the client at startup and closes
  it (plus clears the factory cache) at shutdown.
- `example-app/` — runnable FastAPI demo with an interactive dashboard
  at `GET /` exercising every SDK feature.

### Compatibility
- Python 3.11, 3.12, 3.13
- FastAPI `^0.100`, `^0.110`
- Pydantic v2 + pydantic-settings v2
- `poli-page>=1.0,<2`
