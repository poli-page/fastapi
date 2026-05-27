# `poli-page-fastapi` — Specification

> Self-contained specification for **v0.1.0** of the Poli Page FastAPI integration. A new agent should be able to read this end-to-end and implement the package without consulting external chat history.

**Status**: approved design, ready to implement.
**Roadmap slot**: P1.2 (re-decided post-Symfony / Next / Django per `INTEGRATIONS_PLAN.md` "Order we're working"; package wins over recipe — see §1).
**Last updated**: 2026-05-27.

---

## 1. What this package is, and what it isn't

### Why ship a package, not a recipe ("FastAPI verdict change" justification)

`INTEGRATIONS_PLAN.md` originally classified FastAPI as **"probably skip as a package, ship as a recipe"** — the reasoning being that "`Depends(get_poli_page_client)` is one function; FastAPI has no bundle/module convention to satisfy." After scoping the work concretely, and watching the same trio shape land cleanly across `symfony-bundle`, `nextjs`, `nestjs`, `laravel`, and `django`, we ship as a full package — not a recipe — for one decisive reason: **FastAPI has strong-enough conventions that an idiomatic one-line `pip install` plus a small set of typed helpers beats any copy-paste recipe**. Specifically: `Depends()` for dependency injection is a first-class language feature users already understand; `pydantic-settings`' `BaseSettings` is the canonical env-loading idiom every modern FastAPI app uses; ASGI lifespan events (`@app.lifespan` / `lifespan=` arg) are the documented hook for startup/shutdown resources; Starlette's `Response` subclass hierarchy invites typed wrappers like `PdfResponse` that compose with `response_class=` on route declarations. A recipe asking users to "drop these 80 lines into your project" reinvents all of that and forces every consumer to maintain a copy. An installable package wires them once, ships typed surfaces, and earns its keep by participating in FastAPI's conventions instead of fighting them. We also ship after five sister integrations, so the trio shape (settings → dependency → response helpers → exception handler → example app at `/`) is now a proven pattern — reusing it here costs little and delivers a FastAPI-native feel. The bar is `sentry-sdk[fastapi]`'s extra: a dependency, a typed handler, and a lifespan-aware bootstrap, nothing more.

### Is
- A FastAPI-native wrapper around `poli-page` (the PyPI SDK) that gives users:
  - A `get_poli_page_client()` dependency factory reading `POLI_PAGE_*` env vars via `PoliPageSettings(BaseSettings)`.
  - A `PoliPageDependency` class for users who want per-instance overrides (`Depends(PoliPageDependency(settings=custom_settings))`).
  - Three response helpers (`PdfResponse`, `PreviewResponse`, `DocumentRedirectResponse`) subclassing Starlette response classes with correct headers and RFC 5987 filename encoding.
  - An **opt-in** exception handler `poli_page_exception_handler(request, exc)` registered via `app.add_exception_handler(PoliPageError, poli_page_exception_handler)`.
  - A lifespan helper `poli_page_lifespan(app)` (async context manager) that pre-warms the dependency cache on startup and calls `client.close()` on shutdown.
  - An interactive example app at `example-app/` with a single-page demo dashboard at `GET /`.

### Isn't
- A re-implementation of SDK behaviour. Tests do NOT cover transport, retries, 4xx mapping, idempotency, or stream chunking — `poli-page`'s test suite owns those.
- A Starlette middleware. The exception handler is the integration point; middleware would either fight FastAPI's own exception-handler chain or be ignored.
- A class-based `APIRoute` subclass. Users compose with regular `@app.get` / `@app.post` route declarations and the response helpers; subclassing `APIRoute` couples us to FastAPI internals that change frequently.
- An OpenAPI extension. The response helpers' `media_type` populates `responses=` declarations naturally; we don't ship custom OpenAPI generators.
- A CLI command. FastAPI has no per-app CLI entry point we can attach to (see CLAUDE.md §10.1). `uvicorn main:app` IS the smoke test.
- An auto-import / auto-registration mechanism. Python has no `INSTALLED_APPS` equivalent at the package level; users import what they want from `poli_page_fastapi` and call it explicitly. Same philosophy as `sentry-sdk[fastapi]`.
- A WebSocket helper. PDFs are request/response; WebSockets are out of scope.
- An async-only API. v0.1.0 wires the **sync** SDK client only (`PoliPage`); async endpoints call it via `await run_in_threadpool(client.render.pdf, ...)`. Native `AsyncPoliPage` support lands in v0.2 (see §17).

---

## 2. Required reading (concrete file paths)

Before writing code, read in this order:

1. `/Users/mickael/Projects/INTEGRATIONS_PLAN.md` — cross-repo plan, the "probably skip" verdict on FastAPI, and the five cross-cutting DX patterns (§"Cross-cutting DX patterns").
2. `/Users/mickael/Projects/django/CLAUDE.md` and `docs/spec/django-app-specification.md` — sister Python integration. Same SDK, parallel decisions for response helpers, per-endpoint `try/except`, and the `.env` workflow. The Django spec's §1 "borderline" justification is the model for our "recipe → package" paragraph above.
3. `/Users/mickael/Projects/django/docs/plan/2026-05-26-implementation.md` — model for plan task granularity.
4. `/Users/mickael/Projects/nextjs/CLAUDE.md` §10 + `docs/spec/nextjs-implementation.md` §18 — battle-tested cross-cutting gotchas and the 9 resolved decisions. Most carry forward.
5. `/Users/mickael/Projects/symfony-bundle/CLAUDE.md` and `docs/spec/bundle-specification.md` — the original template; useful for the response-factory parallel (§8 here ≈ §8 there).
6. `/Users/mickael/Projects/sdk-python/src/poli_page/__init__.py` + `_client.py` + `_errors.py` + `_render.py` + `_documents.py` + `types.py` + `fs.py` — the SDK surface we wrap. **Do NOT invent API shape; read the actual code.** Public classes are `PoliPage` (sync), `AsyncPoliPage` (async), `PoliPageError` + 9 subclasses, `RetryEvent`, `PreviewResult`, `DocumentDescriptor`, `DocumentPreviewResult`, `Thumbnail`, `ThumbnailOptions`. The `RenderInput` is `ProjectModeInput | InlineModeInput` (both `TypedDict`).
7. `/Users/mickael/Projects/sdk-python/demo/sync_demo.py` — the 10-step canonical demo. `example-app/` mirrors this 1:1 (§13).
8. `/Users/mickael/Projects/symfony-bundle/example-app/templates/demo.html` — the interactive demo-UI aesthetic we replicate (white, indigo `#4f5d99`, Manrope + IBM Plex Sans + JetBrains Mono).

Reference packages to compare patterns against (open on GitHub or local pip):
- **`sentry-sdk[fastapi]`** (the closest in shape: third-party SDK exposed as a FastAPI extra; lifespan-aware init; opt-in error handling). **Primary reference.**
- **`fastapi-users`** — large config surface (Pydantic settings) + a `Depends()` dependency tree. Excellent for the dependency-factory pattern.
- **`slowapi`** — small, focused package adding one cross-cutting concern (rate limiting) via dependencies + an exception handler. Almost exactly our shape.
- **`strawberry-graphql[fastapi]`** — `BaseSettings`-driven config + `APIRouter` plug-in pattern (we don't ship a router but the env handling is identical).
- **`fastapi-pagination`** — small, response-helper-shaped library; useful for the "thin wrapper" precedent.

---

## 3. Version targets

| Dimension | Constraint | Rationale |
|---|---|---|
| Python | `>=3.11` | Matches the SDK's `requires-python = ">=3.11"` (verified in `sdk-python/pyproject.toml`). Cutting 3.10 lets us use PEP 655 `Required[...]` / `NotRequired[...]` without `typing_extensions`. |
| FastAPI | `^0.100`, `^0.110` (CI tests both) | FastAPI 0.100 was the first release with stable Pydantic v2 + the modern `lifespan=` argument. 0.110 is the current minor we recommend. Future minors are caught by the unbounded `^` constraint on the SDK's side. |
| Starlette | inherited transitively from FastAPI | We do not pin directly. |
| Pydantic | `>=2.0,<3` | FastAPI 0.100+ requires Pydantic v2; the SDK and the integration both target it. |
| `pydantic-settings` | `>=2.0,<3` | Separate package since Pydantic v2; the `BaseSettings` class moved out of pydantic core. |
| `poli-page` (SDK) | `>=1.0,<2` | First stable major; SemVer guarantees compatibility through `2.0`. |
| `httpx` | inherited transitively from `poli-page` | We do not pin directly. |
| `python-dotenv` | optional, dev/example only | Used by `tests/conftest.py` and `example-app/main.py` to load the workspace-root `.env`. No hard dep. |

CI matrix: Python `3.11`/`3.12`/`3.13` × FastAPI `^0.100`/`^0.110`. 6 cells. See §15.

---

## 4. Architecture style

Functional + Pydantic, no classes for the API surface except `PoliPageDependency` (which is a class because it must be callable as a dependency instance). Five primitives:

1. **`PoliPageSettings(BaseSettings)`** — env loader; reads `POLI_PAGE_*` vars.
2. **`get_poli_page_client()`** — memoised module-level function returning a `PoliPage`; the canonical access path via `Depends(get_poli_page_client)`.
3. **`PoliPageDependency`** — class-based dependency for users who want per-instance overrides (`Depends(PoliPageDependency(settings=...))`).
4. **`poli_page_fastapi.responses`** — three response classes subclassing `FileResponse` / `Response` / `RedirectResponse`.
5. **`poli_page_exception_handler(request, exc)`** — opt-in handler, registered via `app.add_exception_handler(PoliPageError, ...)`.

Plus framework plumbing:
- `poli_page_lifespan(app)` — async context manager users pass to `FastAPI(lifespan=...)`.
- `_headers.py` — internal RFC 5987 filename encoding helper.

That's the whole API surface. No middleware, no router, no class-based view base, no decorator.

The package is **tree-shakeable in the Python sense**: each submodule has minimal cross-imports, so users who only want `PdfResponse` can `from poli_page_fastapi.responses import PdfResponse` without instantiating the client.

---

## 5. File layout

```
fastapi/
├── src/
│   └── poli_page_fastapi/
│       ├── __init__.py                       # re-exports the public surface (settings + dependency + responses + handler + lifespan)
│       ├── settings.py                       # PoliPageSettings(BaseSettings)
│       ├── dependencies.py                   # get_poli_page_client() + PoliPageDependency
│       ├── responses.py                      # PdfResponse / PreviewResponse / DocumentRedirectResponse
│       ├── exceptions.py                     # poli_page_exception_handler(request, exc)
│       ├── lifespan.py                       # poli_page_lifespan(app)
│       ├── _headers.py                       # internal: RFC 5987 filename encoding
│       ├── _version.py                       # __version__ = "0.1.0"
│       └── py.typed                          # PEP 561 marker
├── tests/
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── test_settings.py                  # PoliPageSettings env loading + prefix validator
│   │   ├── test_dependencies.py              # get_poli_page_client + PoliPageDependency
│   │   ├── test_responses.py                 # 3 response classes (headers, filenames)
│   │   ├── test_exceptions.py                # poli_page_exception_handler mapping
│   │   ├── test_lifespan.py                  # startup / shutdown sequence
│   │   ├── test_headers.py                   # RFC 5987 helper
│   │   └── conftest.py                       # signal-handler / asyncio-task snapshots
│   ├── integration/
│   │   ├── __init__.py
│   │   └── test_render_against_develop_api.py    # gated on POLI_PAGE_API_KEY
│   └── conftest.py                           # repo-root .env loader
├── example-app/                              # see §13
│   ├── main.py                               # FastAPI app + lifespan + routes + GET / HTML dashboard
│   ├── pyproject.toml                        # path-installs `../`
│   └── README.md
├── docs/
│   ├── spec/fastapi-package-specification.md     # this file
│   └── plan/2026-05-27-implementation.md
├── pyproject.toml                            # PEP 621 + ruff + mypy + pytest + hatchling
├── .github/workflows/ci.yml
├── README.md
├── CHANGELOG.md                              # Keep a Changelog format
├── LICENSE                                   # MIT
└── CLAUDE.md                                 # integration-flavored (replaces inherited SDK template)
```

**File count**: 8 source files in `src/poli_page_fastapi/` (the 7 modules listed plus `__init__.py`). That is the entire package. Test files are 1:1 with source files; the example app is a single `main.py`.

---

## 6. Settings (Pydantic `BaseSettings`) — `POLI_PAGE_*` env loading

`PoliPageSettings(BaseSettings)` is the canonical env reader. Users either:
1. Let `get_poli_page_client()` instantiate it automatically (zero config).
2. Construct it themselves and pass into `PoliPageDependency(settings=...)`.

### 6.1 Surface

```python
# src/poli_page_fastapi/settings.py
from __future__ import annotations

import re
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_API_KEY_RE = re.compile(r"^pp_(test|live)_")


class PoliPageSettings(BaseSettings):
    """Pydantic-settings reader for POLI_PAGE_* env vars.

    Maps one-to-one with the SDK's PoliPage(__init__) kwargs. Unset values
    are left as None so the SDK applies its own defaults — we never duplicate
    default literals between SDK and integration.
    """

    model_config = SettingsConfigDict(
        env_prefix="POLI_PAGE_",
        env_file=None,                # users load .env themselves (or via lifespan)
        case_sensitive=False,
        extra="ignore",
    )

    api_key: str | None = Field(default=None, alias="POLI_PAGE_API_KEY")
    base_url: str | None = Field(default=None, alias="POLI_PAGE_BASE_URL")
    timeout: float | None = Field(default=None, alias="POLI_PAGE_TIMEOUT")
    max_retries: int | None = Field(default=None, alias="POLI_PAGE_MAX_RETRIES")
    retry_delay: float | None = Field(default=None, alias="POLI_PAGE_RETRY_DELAY")

    @field_validator("api_key")
    @classmethod
    def _validate_api_key_shape(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        if not _API_KEY_RE.match(v):
            raise ValueError(
                "POLI_PAGE_API_KEY must start with pp_test_ or pp_live_. "
                "Get one at https://app.poli.page/settings/api-keys.",
            )
        return v

    @field_validator("timeout")
    @classmethod
    def _validate_timeout(cls, v: float | None) -> float | None:
        if v is not None and not (0 < v <= 600):
            raise ValueError("POLI_PAGE_TIMEOUT must be > 0 and <= 600 seconds.")
        return v

    @field_validator("max_retries")
    @classmethod
    def _validate_max_retries(cls, v: int | None) -> int | None:
        if v is not None and not (0 <= v <= 10):
            raise ValueError("POLI_PAGE_MAX_RETRIES must be between 0 and 10.")
        return v

    @field_validator("retry_delay")
    @classmethod
    def _validate_retry_delay(cls, v: float | None) -> float | None:
        if v is not None and not (0 <= v <= 30):
            raise ValueError("POLI_PAGE_RETRY_DELAY must be between 0 and 30 seconds.")
        return v
```

### 6.2 Env var names (verified against SDK)

The SDK's `PoliPage.__init__` reads `POLI_PAGE_API_KEY` and `POLI_PAGE_BASE_URL` natively. We extend that with `POLI_PAGE_TIMEOUT`, `POLI_PAGE_MAX_RETRIES`, `POLI_PAGE_RETRY_DELAY` for FastAPI users who prefer env vars over code config. The names mirror the nextjs integration's spec §6 exactly so multi-language teams see the same vocabulary.

### 6.3 When is validation enforced?

`PoliPageSettings()` raises `pydantic.ValidationError` at construction time when any validator fails. `get_poli_page_client()` calls `PoliPageSettings()` lazily — first invocation triggers validation. In production this happens at app startup if `poli_page_lifespan` is wired in (recommended); without lifespan, it happens at first request that uses the dependency.

### 6.4 No env-file loading inside the package

We do NOT call `load_dotenv()` from anywhere in `src/`. Loading `.env` is the user's responsibility:
- Production: real env vars (Docker, systemd, Kubernetes secrets).
- Dev: users typically call `load_dotenv()` from their `main.py` before instantiating `FastAPI()`, OR pydantic-settings reads the file directly via `model_config = SettingsConfigDict(env_file=".env")`.
- Our example-app does load `.env` from the workspace root, but that's example-app code, not package code.

This matches `sentry-sdk[fastapi]`'s behavior and avoids hidden filesystem reads.

---

## 7. FastAPI dependency factory + `PoliPageDependency` class

### 7.1 `get_poli_page_client()` — memoised factory

```python
# src/poli_page_fastapi/dependencies.py
from __future__ import annotations

from functools import lru_cache

from poli_page import PoliPage

from .settings import PoliPageSettings


@lru_cache(maxsize=1)
def get_poli_page_client() -> PoliPage:
    """Return the process-wide memoised PoliPage client.

    Used as `Depends(get_poli_page_client)` in route signatures. The `lru_cache`
    decorator guarantees one instance per process; to inject a mock in tests,
    use `app.dependency_overrides[get_poli_page_client] = lambda: mock`.
    """
    settings = PoliPageSettings()
    kwargs: dict[str, object] = {}
    if settings.api_key is not None:
        kwargs["api_key"] = settings.api_key
    if settings.base_url is not None:
        kwargs["base_url"] = settings.base_url
    if settings.timeout is not None:
        kwargs["timeout"] = settings.timeout
    if settings.max_retries is not None:
        kwargs["max_retries"] = settings.max_retries
    if settings.retry_delay is not None:
        kwargs["retry_delay"] = settings.retry_delay
    return PoliPage(**kwargs)
```

### 7.2 `PoliPageDependency` class — explicit, override-friendly

```python
# src/poli_page_fastapi/dependencies.py (continued)
class PoliPageDependency:
    """Callable dependency that builds a per-instance client.

    Use when you want explicit settings or a per-router client distinct
    from the global memo:

        custom = PoliPageDependency(settings=PoliPageSettings(api_key="pp_test_b"))

        @app.get("/sandbox/pdf")
        def sandbox_pdf(client: PoliPage = Depends(custom)) -> Response:
            ...

    Each instance memoises its own client (one per `PoliPageDependency()`).
    """

    def __init__(
        self,
        *,
        settings: PoliPageSettings | None = None,
        client: PoliPage | None = None,
    ) -> None:
        self._settings = settings
        self._explicit_client = client
        self._cached_client: PoliPage | None = None

    def __call__(self) -> PoliPage:
        if self._explicit_client is not None:
            return self._explicit_client
        if self._cached_client is None:
            settings = self._settings or PoliPageSettings()
            kwargs: dict[str, object] = {}
            if settings.api_key is not None:
                kwargs["api_key"] = settings.api_key
            if settings.base_url is not None:
                kwargs["base_url"] = settings.base_url
            if settings.timeout is not None:
                kwargs["timeout"] = settings.timeout
            if settings.max_retries is not None:
                kwargs["max_retries"] = settings.max_retries
            if settings.retry_delay is not None:
                kwargs["retry_delay"] = settings.retry_delay
            self._cached_client = PoliPage(**kwargs)
        return self._cached_client

    def close(self) -> None:
        if self._cached_client is not None:
            self._cached_client.close()
            self._cached_client = None
```

### 7.3 Test ergonomics

The idiomatic FastAPI override mechanism:

```python
from fastapi.testclient import TestClient
from poli_page_fastapi import get_poli_page_client

def test_my_endpoint(app, mock_client):
    app.dependency_overrides[get_poli_page_client] = lambda: mock_client
    try:
        with TestClient(app) as client:
            response = client.get("/render/pdf")
        assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()
```

`lru_cache` is NOT cleared in tests — `dependency_overrides` takes precedence. Documented in README.

### 7.4 Why two surfaces (function + class)?

`get_poli_page_client` covers the 95% case: env-only config, one client per process. `PoliPageDependency` covers the 5%: multi-tenant apps with per-router API keys, sandbox-vs-production split, advanced lifecycle. We could have shipped only the function and asked advanced users to roll their own, but the class is 20 lines and matches `slowapi`'s `Limiter` pattern — present in the README, invisible to simple users.

### 7.5 Why no `BackgroundTasks`-aware dependency?

The SDK is sync; calling it from a `BackgroundTasks` handler works without any wrapper (FastAPI runs background tasks in a threadpool). v0.2 may ship a native `AsyncPoliPage` dependency once we promote async; until then, no surface.

---

## 8. `poli_page_fastapi.responses` — response helpers

Three subclasses of Starlette response classes. **No state.** Pure construction from SDK output → typed Response.

### 8.1 `PdfResponse(FileResponse)` — bytes or stream

```python
# src/poli_page_fastapi/responses.py
from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

from starlette.responses import Response, StreamingResponse
from starlette.background import BackgroundTask

from ._headers import build_content_disposition


class PdfResponse(Response):
    """A PDF response with correct headers.

    Use with `bytes` from `client.render.pdf(...)` or `client.documents.preview(...)`:

        @app.get("/invoice/{id}")
        def invoice(id: str, client: PoliPage = Depends(get_poli_page_client)) -> PdfResponse:
            pdf = client.render.pdf({"project": "invoices", "template": "default", "version": "1.0.0", "data": {"id": id}})
            return PdfResponse(pdf, filename=f"invoice-{id}.pdf")
    """

    media_type = "application/pdf"

    def __init__(
        self,
        content: bytes,
        *,
        filename: str = "document.pdf",
        inline: bool = False,
        background: BackgroundTask | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        merged: dict[str, str] = dict(headers or {})
        merged["Content-Disposition"] = build_content_disposition(filename, inline=inline)
        merged.setdefault("Cache-Control", "no-store, private")
        merged.setdefault("X-Content-Type-Options", "nosniff")
        super().__init__(content=content, media_type="application/pdf", headers=merged, background=background)


class PdfStreamResponse(StreamingResponse):
    """A streamed PDF response for `client.render.pdf_stream(...)` consumers."""

    media_type = "application/pdf"

    def __init__(
        self,
        content: Iterator[bytes] | AsyncIterator[bytes],
        *,
        filename: str = "document.pdf",
        inline: bool = False,
        background: BackgroundTask | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        merged: dict[str, str] = dict(headers or {})
        merged["Content-Disposition"] = build_content_disposition(filename, inline=inline)
        merged.setdefault("Cache-Control", "no-store, private")
        merged.setdefault("X-Content-Type-Options", "nosniff")
        super().__init__(content=content, media_type="application/pdf", headers=merged, background=background)


class PreviewResponse(Response):
    """An HTML preview response (for `render.preview` / `documents.preview`)."""

    media_type = "text/html; charset=utf-8"

    def __init__(
        self,
        content: str,
        *,
        background: BackgroundTask | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        merged: dict[str, str] = dict(headers or {})
        merged.setdefault("Cache-Control", "no-store, private")
        merged.setdefault("X-Content-Type-Options", "nosniff")
        super().__init__(
            content=content,
            media_type="text/html; charset=utf-8",
            headers=merged,
            background=background,
        )


class DocumentRedirectResponse(Response):
    """A 302 (or 308 if permanent=True) redirect to a document's presigned URL."""

    def __init__(
        self,
        url: str,
        *,
        permanent: bool = False,
        background: BackgroundTask | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        merged: dict[str, str] = dict(headers or {})
        merged["Location"] = url
        merged.setdefault("Cache-Control", "no-store, private")
        status_code = 308 if permanent else 302
        super().__init__(content=b"", status_code=status_code, headers=merged, background=background)
```

### 8.2 Headers each helper sets

| Helper | Content-Type | Content-Disposition | Cache-Control | X-Content-Type-Options |
|---|---|---|---|---|
| `PdfResponse` | `application/pdf` | `attachment; filename="..."; filename*=UTF-8''...` (or `inline` when `inline=True`) | `no-store, private` (override via `headers=`) | `nosniff` |
| `PdfStreamResponse` | `application/pdf` | same as `PdfResponse` | same | `nosniff` |
| `PreviewResponse` | `text/html; charset=utf-8` | — | `no-store, private` | `nosniff` |
| `DocumentRedirectResponse` | — | — | `no-store, private` | — |

### 8.3 Filename encoding (RFC 5987 / RFC 6266)

```python
# src/poli_page_fastapi/_headers.py
from __future__ import annotations

from urllib.parse import quote


def build_content_disposition(filename: str, *, inline: bool = False) -> str:
    """Build an RFC 5987-compliant Content-Disposition header.

    ASCII-safe filenames: `attachment; filename="..."`.
    Non-ASCII filenames: dual form — `attachment; filename="<ascii-fallback>"; filename*=UTF-8''...`.

    Ported character-for-character from symfony-bundle's PoliPageResponseFactory
    and nextjs's headers.ts.
    """
    disposition = "inline" if inline else "attachment"
    try:
        filename.encode("ascii")
        return f'{disposition}; filename="{filename}"'
    except UnicodeEncodeError:
        ascii_fallback = filename.encode("ascii", "replace").decode("ascii")
        encoded = quote(filename, safe="")
        return f'{disposition}; filename="{ascii_fallback}"; filename*=UTF-8\'\'{encoded}'
```

Same algorithm as the symfony-bundle's `PoliPageResponseFactory` and the nextjs / django integrations. The bundle's unit tests for non-ASCII filenames are the canonical reference — port them.

### 8.4 What these helpers do NOT do

- **They do not call the SDK.** They take SDK output (bytes / str / url) and produce a Response. The user calls `client.render.pdf(...)` in their endpoint, then `return PdfResponse(pdf, filename=...)`.
- **They do not catch `PoliPageError`.** See §10 for the opt-in exception-handler philosophy.
- **They do not check `accept` headers** to negotiate inline-vs-attachment. The caller decides via the `inline=` kwarg.

### 8.5 Why subclass instead of factory functions?

FastAPI route declarations have a `response_class=` argument:

```python
@app.get("/invoice/{id}", response_class=PdfResponse)
def invoice(...) -> bytes: ...
```

Subclasses participate in this idiom naturally; factory functions don't. We borrow this from `fastapi.responses.JSONResponse` / `HTMLResponse` etc. — same pattern.

---

## 9. No CLI — `uvicorn` IS the smoke test

FastAPI ships no per-app CLI for end-users. The closest thing is the `fastapi-cli` package (`fastapi dev main.py`), which is just a wrapper around `uvicorn`. There is **no Symfony Console / Artisan / `manage.py` equivalent** we can attach a `poli_page_render` command to.

Therefore, v0.1.0 ships **no console-entry-point script**. The example app's `uvicorn main:app --reload` plus the demo dashboard at `GET /` ARE the smoke test. A user wanting programmatic config validation can write:

```python
# scripts/validate_settings.py
from poli_page_fastapi import PoliPageSettings
print(PoliPageSettings())
```

That's all that would be in a `poli-page-fastapi` CLI anyway. Documented in README + CLAUDE.md §10.1.

---

## 10. Exception handler — opt-in via `app.add_exception_handler`

The SDK raises a typed hierarchy: `PoliPageError` (base) → `APIConnectionError` (→ `APITimeoutError`) and `APIStatusError` (→ `BadRequestError`, `AuthenticationError`, `PermissionDeniedError`, `NotFoundError`, `ConflictError`, `GoneError`, `UnprocessableEntityError`, `RateLimitError`, `InternalServerError`).

### 10.1 The handler

```python
# src/poli_page_fastapi/exceptions.py
from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from poli_page import APIConnectionError, APIStatusError, PoliPageError


def poli_page_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Map any PoliPageError to a typed JSON response.

    Register via:

        from poli_page import PoliPageError
        from poli_page_fastapi import poli_page_exception_handler

        app.add_exception_handler(PoliPageError, poli_page_exception_handler)

    Status code: matches `exc.status` for APIStatusError; 502 for
    APIConnectionError / APITimeoutError; 500 for the base PoliPageError
    (validation / programming errors). Body shape mirrors the SDK's own
    error structure, plus `request_id` (null when absent).
    """
    if not isinstance(exc, PoliPageError):
        # Should not happen if registered correctly, but be defensive.
        return JSONResponse(
            status_code=500,
            content={"code": "UNKNOWN", "message": str(exc), "request_id": None},
        )

    if isinstance(exc, APIStatusError) and exc.status is not None:
        status_code = exc.status
    elif isinstance(exc, APIConnectionError):
        status_code = 502
    else:
        status_code = 500

    body = {
        "code": exc.code,
        "message": exc.message,
        "request_id": exc.request_id,
    }
    return JSONResponse(
        status_code=status_code,
        content=body,
        headers={"Cache-Control": "no-store, private"},
    )
```

### 10.2 Why opt-in?

Same philosophy as `@poli-page/nestjs`'s `PoliPageExceptionFilter` (also opt-in). Three reasons:

1. **FastAPI users often own their global exception handler.** Auto-registering ours would either conflict or be invisibly shadowed.
2. **The handler shape is a documented contract.** Users who want a different body (e.g., wrapping in a `{"error": {...}}` envelope) can copy ours and adjust — easier than monkey-patching.
3. **`app.add_exception_handler(PoliPageError, ...)` is one line.** The "auto-register" gain is microscopic; the "explicit and clear" gain is substantial.

This is a **delta from `@poli-page/nextjs`'s `createPoliPageRouteHandler()`** (which catches by default) — driven by FastAPI's exception-handler chain being more pluggable than Next's route-handler shape. Same delta as django's per-view `try/except` approach.

### 10.3 The four user patterns

| Pattern | Code | When to use |
|---|---|---|
| Global handler | `app.add_exception_handler(PoliPageError, poli_page_exception_handler)` | Simplest; handles every endpoint uniformly. **Recommended default.** |
| Per-endpoint `try/except` | `try: ... except PoliPageError as e: return JSONResponse(...)` | When you want endpoint-specific responses (e.g., a fallback PDF instead of an error). |
| Custom handler reusing ours | `def my_handler(req, exc): resp = poli_page_exception_handler(req, exc); ... return resp` | When you want logging / telemetry plus the default response. |
| No handler | `client.render.pdf(...)` bubbles `PoliPageError` to FastAPI's default 500 | When you don't care about a typed response (probably never). |

### 10.4 `TestClient` and the handler

Because `add_exception_handler` is an `app` mutation, the handler is registered at app construction time. Tests that need to assert the handler's behavior construct a small `FastAPI()` app, register the handler, define a route that raises a specific `PoliPageError` subclass, then assert the response. Use `with TestClient(app) as client:` (context-manager form) so the lifespan fires correctly (see CLAUDE.md §10.2).

### 10.5 The SDK's on_retry / on_error hooks

The SDK's `on_retry` / `on_error` constructor params are **NOT** bridged to FastAPI events or signals by default. Reasoning:

- FastAPI has no built-in event bus. Starlette ships nothing comparable to Django signals or Symfony's EventDispatcher.
- Adding `blinker` (or another signal lib) as a hard dep would force every consumer to take a new transitive dep for a feature most won't use.
- Users who want hook coverage pass plain callables straight to `PoliPage(on_retry=..., on_error=...)` — that's already a function dispatch, just not Django-flavored.

If a future user persistently asks, we ship `poli_page_fastapi.signals` (opt-in via `pip install poli-page-fastapi[signals]`) wrapping `blinker`. Deferred to v0.2 per §17. For v0.1, document the pattern in the README:

```python
def log_retry(event):
    logger.warning("Poli Page retry: %d after %.3fs (%s)", event.attempt, event.delay_seconds, event.reason.code)

dependency = PoliPageDependency(settings=PoliPageSettings(...))
dependency._cached_client = PoliPage(api_key="...", on_retry=log_retry)  # set explicitly
app.dependency_overrides[get_poli_page_client] = dependency
```

(That's awkward enough that the v0.2 wrapper is justified — captured as an open question in §20.)

---

## 11. Installation (one `pip install` + zero or one `app.add_exception_handler` line)

There is no auto-registration. The README documents the canonical setup:

```python
# main.py
from fastapi import FastAPI, Depends
from poli_page import PoliPage, PoliPageError
from poli_page_fastapi import (
    get_poli_page_client,
    poli_page_exception_handler,
    poli_page_lifespan,
    PdfResponse,
)

app = FastAPI(lifespan=poli_page_lifespan)
app.add_exception_handler(PoliPageError, poli_page_exception_handler)


@app.get("/invoice/{id}", response_class=PdfResponse)
def invoice(id: str, client: PoliPage = Depends(get_poli_page_client)) -> PdfResponse:
    pdf = client.render.pdf({
        "project": "invoices",
        "template": "default",
        "version": "1.0.0",
        "data": {"id": id},
    })
    return PdfResponse(pdf, filename=f"invoice-{id}.pdf")
```

Set `POLI_PAGE_API_KEY=pp_test_...` in the environment. That's the entire integration. No `INSTALLED_APPS`, no Flex recipe, no `forRoot()`, no decorator.

---

## 12. Unpublished-SDK workaround — local editable install (dev only)

**Status**: the Python SDK (`poli-page`) is **already published on PyPI** — so for production / CI / contributors who don't need unreleased SDK changes, `pip install poli-page-fastapi` resolves everything from PyPI normally.

**During active dev** where we test against unreleased `sdk-python` changes:

```bash
# from /Users/mickael/Projects/fastapi (inside the dev venv)
uv pip install -e ../sdk-python
```

This shadows the PyPI `poli-page` with the local sibling checkout. The integration's `pyproject.toml` stays clean (`"poli-page>=1.0,<2"`). When done, `uv pip install --force-reinstall poli-page` restores the published version.

### 12.1 What changes when the SDK ships a new compat-breaking version

1. Bump `dependencies` in `pyproject.toml`: `"poli-page>=2.0,<3"`.
2. Update any SDK-API usages flagged by the upgrade.
3. Update the CI matrix to test against the new pin.
4. Tag a new minor (or major) of `poli-page-fastapi`.

No path-repo trickery, no merge-plugin equivalent — Python's editable-install machinery is a clean primitive that `pip` / `uv` understand directly. Same as django's §12.

### 12.2 CI handling

CI installs from PyPI. The `requirements-dev.txt` (or `[project.optional-dependencies].dev` block) pins `poli-page` to a known-good version. To test against an unreleased SDK from CI, override at the workflow level:

```yaml
- run: uv pip install -e ${{ github.workspace }}/sdk-python
```

Optional, only used in the integration-test job. The main matrix uses the PyPI version.

---

## 13. Example app

`example-app/` is a self-contained FastAPI project that mirrors `sdk-python/demo/sync_demo.py` feature-for-feature. **Mirrors `demo/sync_demo.py` 1:1**, so a reader can put the two files side-by-side and verify the package adds shape, not behaviour.

### 13.1 Routes (mirror SDK demo steps 1–10)

The `example-app/main.py` file exposes:

| SDK demo step | URL | Method | Endpoint function | SDK call |
|---|---|---|---|---|
| (UI) | `GET /` | `dashboard()` | Returns an `HTMLResponse` with the demo dashboard (see §13.2) |
| 1. `render.pdf` | `GET /render/pdf` | `render_pdf(client)` | `client.render.pdf(...)` → `PdfResponse(...)` |
| 2. `render.pdf_stream` | `GET /render/stream` | `render_stream(client)` | `client.render.pdf_stream(...)` → `PdfStreamResponse(...)` |
| 3. `render_to_file` | `POST /render/file` | `render_to_file(client)` | `poli_page.fs.render_to_file(client, ...)`; returns JSON with the written path |
| 4. `render.preview` | `GET /render/preview` | `render_preview(client)` | `client.render.preview(...)` → `PreviewResponse(...)` |
| 5. `render.document` | `POST /documents` | `document_create(client)` | `client.render.document(...)` → JSON descriptor |
| 6. `documents.get` | `GET /documents/{id}` | `document_get(id, client)` | `client.documents.get(id)` → `DocumentRedirectResponse(...)` (302) |
| 7. `documents.thumbnails` | `GET /documents/{id}/thumbnails` | `document_thumbnails(id, client)` | base64 thumbnails as JSON |
| 8. `documents.preview` | `GET /documents/{id}/preview` | `document_preview(id, client)` | `client.documents.preview(id)` → `PreviewResponse(...)` |
| 9. `documents.delete` | `DELETE /documents/{id}` | `document_delete(id, client)` | `client.documents.delete(id)` → 204 |
| 10. Error handling | `GET /errors/bad-version` | `error_bad_version(client)` | Deliberately calls with an invalid template version; relies on the global handler to produce JSON |

Each endpoint uses `client: PoliPage = Depends(get_poli_page_client)`. Sync calls are made directly (FastAPI runs sync route functions in a threadpool); the `render.pdf_stream` endpoint reads chunks in a generator passed to `PdfStreamResponse`. No `await run_in_threadpool(...)` is needed at the endpoint level since the routes are `def` not `async def` — that's covered in the README's "async endpoint" recipe.

### 13.2 Interactive demo UI at `GET /`

`main.py` defines a constant `DASHBOARD_HTML: str` containing a single self-contained HTML document with the same interactive dashboard pattern shipped in `symfony-bundle/example-app/templates/demo.html` — one button per SDK feature, inline `<iframe>` PDF previews, inline `<iframe srcdoc>` HTML previews, document-lifecycle state machine in vanilla JS, JSON pretty-print (red on non-2xx), copy-button blocks for any CLI step.

**Aesthetic**: white surface (`--bg: #ffffff`), muted brand indigo `#4f5d99`, Manrope display sans + IBM Plex Sans body + JetBrains Mono code. Fonts pulled from Google Fonts via `<link>` (no build step). CSS scoped at the top of the document in a single `<style>` block — no Tailwind, no CSS-in-JS.

The page calls the 10 JSON / file routes via `fetch()`. PDF responses render in `<iframe src="...">`. Preview HTML renders in `<iframe srcdoc="...">`. Document IDs returned by step 5 are stored in JS state; steps 6–9 are gated on its presence (buttons disabled until step 5 runs).

Served via:

```python
from fastapi.responses import HTMLResponse

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def dashboard() -> str:
    return DASHBOARD_HTML
```

Alternative considered: `app.mount("/", StaticFiles(directory="example-app/public", html=True))` with a separate `index.html`. Rejected because keeping everything in one `main.py` makes the demo easier to read top-to-bottom. The inline string costs ~440 lines but is self-documenting.

### 13.3 `main.py` env loading

```python
from pathlib import Path
from dotenv import load_dotenv

# Single root .env — see INTEGRATIONS_PLAN.md §"Cross-cutting DX patterns" §2
_ROOT_ENV = Path(__file__).resolve().parent.parent.parent / ".env"
if _ROOT_ENV.exists():
    load_dotenv(_ROOT_ENV, override=False)   # real env wins

from fastapi import FastAPI, Depends   # noqa: E402 (must load env first)
# ... rest of the app
```

Real shell exports still win (`override=False`). No `.env.local` anywhere. Hard requirement (per `INTEGRATIONS_PLAN.md` §"Cross-cutting DX patterns" §2).

### 13.4 Running it

```bash
cd example-app
uv sync
uv run uvicorn main:app --reload     # → http://localhost:8000
```

No per-app `.env.local` needed. Hard requirement (carried from `symfony-bundle`).

### 13.5 What example-app proves

- The package boots in a real FastAPI app (not just `pytest-asyncio`'s test runner).
- `get_poli_page_client()` resolves correctly via `Depends`.
- The lifespan helper wires up cleanly with `FastAPI(lifespan=poli_page_lifespan)`.
- Every SDK surface is reachable via the response helpers without manual `httpx` plumbing.
- The opt-in exception handler maps `PoliPageError` to JSON as documented.

---

## 14. Testing strategy

### 14.1 Layers

**Unit tests** (95%+ of the suite, run in milliseconds, no network):

| Test | What it covers |
|---|---|
| `test_settings.py` | `PoliPageSettings()` reads `POLI_PAGE_*` env. Each `field_validator` rejects out-of-range / bad-prefix values. `monkeypatch.setenv(...)` for env injection. Missing env var → `api_key=None` (no raise; SDK env fallback applies). |
| `test_dependencies.py` | `get_poli_page_client()` returns a `PoliPage`; second call returns the same instance (memoised). `app.dependency_overrides[get_poli_page_client] = lambda: mock` works. `PoliPageDependency()` builds independently; `PoliPageDependency(client=...)` returns the explicit client. `PoliPageDependency.close()` calls `client.close()`. |
| `test_responses.py` | `PdfResponse(b"%PDF...", filename="x.pdf")` sets `Content-Type: application/pdf`, `Content-Disposition: attachment; filename="x.pdf"`, `Cache-Control: no-store, private`, `X-Content-Type-Options: nosniff`. Non-ASCII filename → dual `filename=` / `filename*=UTF-8''` form. `inline=True` flips disposition. `PreviewResponse("<p>x</p>")` → `text/html; charset=utf-8`. `DocumentRedirectResponse("https://...")` → 302 + `Location`. |
| `test_exceptions.py` | `poli_page_exception_handler(request, exc)` maps each `PoliPageError` subclass to correct status code + body. Use a fake `Request` (Starlette's `Request(scope={"type": "http", ...})`). Mock `BadRequestError(status=400, code='X', message='m', request_id='rid')` → `JSONResponse(status_code=400, content={"code": "X", "message": "m", "request_id": "rid"})`. Same for 401, 403, 404, 409, 410, 422, 429, 500. `APIConnectionError` → 502. `APITimeoutError` → 502. Bare `PoliPageError` → 500. |
| `test_lifespan.py` | `poli_page_lifespan(app)` is an async context manager. Entering it triggers `get_poli_page_client()` (assert via `mocker.patch`); exiting calls `client.close()`. Use `TestClient(app)` as a context manager to drive the lifespan. |
| `test_headers.py` | `build_content_disposition("x.pdf")` → `attachment; filename="x.pdf"`. `build_content_disposition("naïve.pdf")` → `attachment; filename="na?ve.pdf"; filename*=UTF-8''na%C3%AFve.pdf`. `inline=True` flips the disposition string. |

**Integration test** (single test, gated):

`test_render_against_develop_api.py`:
- Skipped automatically with `@pytest.mark.skipif(os.environ.get("POLI_PAGE_API_KEY") is None)`.
- Refuses to run with `pp_live_*` keys (safety belt — integration tests should never hit production).
- Builds a `FastAPI()` app with the dependency wired to `PoliPageSettings(base_url="https://api-develop.poli.page", api_key=os.environ["POLI_PAGE_API_KEY"])`, registers a single endpoint that calls `client.render.pdf({"project": "getting-started", "template": "welcome", "version": "1.0.0", "data": {"name": "fastapi integration test"}})`, hits it via `TestClient`, asserts `200 OK` and `response.content[:5] == b"%PDF-"`.
- One test, idempotent, ~3 seconds when it runs.

### 14.2 What we explicitly do NOT test

Anything tested by the SDK:
- HTTP transport behaviour (`httpx` edge cases, connection pooling).
- Retry policy (exponential backoff, max attempts, `Retry-After` parsing, never retrying 4xx).
- 4xx / 5xx → `PoliPageError` subclass mapping inside the SDK.
- Idempotency-Key generation.
- Stream chunking correctness.
- API contract drift — the SDK's contract tests cover that.

The package wraps — it does not re-test.

### 14.3 Test-runner hygiene (signal-handler / asyncio-task leaks)

`tests/unit/conftest.py` ships two autouse fixtures:

1. **`restore_signal_handlers`**: snapshots `signal.getsignal(signal.SIGINT)` at setup, restores at teardown. uvicorn's worker can install SIGINT handlers; tests that load uvicorn programmatically can leak.
2. **`check_no_pending_tasks`**: after each test, if an asyncio event loop is running, asserts `asyncio.all_tasks(loop)` is empty (excluding the current test's task itself). Catches dangling coroutines that didn't get awaited.

Pattern carried from `symfony-bundle/tests/RestoresGlobalHandlers.php`, `nextjs/tests/setup.ts`, and `django/tests/conftest.py`. Documented as cross-cutting in `INTEGRATIONS_PLAN.md` §4.

### 14.4 `TestClient` context-manager discipline

`fastapi.testclient.TestClient` only fires ASGI `startup` / `shutdown` events when used as a context manager:

```python
with TestClient(app) as client:
    response = client.get("/")
```

Bare `TestClient(app).get(...)` skips the lifespan entirely. **Every test that exercises `poli_page_lifespan` MUST use the context-manager form.** Documented in CLAUDE.md §10.2.

### 14.5 Tooling

- **pytest 8** + **pytest-asyncio** (`asyncio_mode = "auto"` so `async def test_*` is the default). No bundled unittest runner.
- **respx** is a dev-time dep but used SPARINGLY. Most unit tests mock the `PoliPage` class itself (`mocker.patch("poli_page_fastapi.dependencies.PoliPage")`); we don't re-test transport.
- **httpx** comes transitively via FastAPI's `TestClient` — no separate pin.
- **mypy strict** for `src/`. Tests are typed but allow `disallow_untyped_decorators = false` for `@pytest.fixture` and `@pytest.mark.parametrize`.

---

## 15. CI matrix

`.github/workflows/ci.yml`:

```yaml
name: CI
on:
  push:
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        python: ["3.11", "3.12", "3.13"]
        fastapi: ["0.100", "0.110"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python }}
      - uses: astral-sh/setup-uv@v3
      - name: Install
        run: |
          uv sync --all-extras
          uv pip install "fastapi~=${{ matrix.fastapi }}.0"
      - name: Lint
        run: uv run ruff check .
      - name: Format
        run: uv run ruff format --check .
      - name: Type check
        run: uv run mypy src tests
      - name: Unit tests
        run: uv run pytest tests/unit -v

  integration:
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - uses: astral-sh/setup-uv@v3
      - run: uv sync --all-extras
      - name: Integration test against develop API
        env:
          POLI_PAGE_API_KEY: ${{ secrets.POLI_PAGE_DEVELOP_API_KEY }}
        run: uv run pytest tests/integration -v
```

**Auto-skip behaviour**: each step short-circuits when the relevant file is missing (`pyproject.toml`, `tests/unit/`, etc.), so a freshly scaffolded repo is green from day one. Same convention as the symfony-bundle, nextjs, and django.

6 cells: 3 Python versions × 2 FastAPI minors. All cells run on every push.

---

## 16. Versioning & release

- **SemVer**. v0.x while the API stabilises.
- **`CHANGELOG.md`** in Keep a Changelog format. Updated in the same commit as every version bump.
- **Conventional Commits** for every commit (`feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`).
- **Release process** (PyPI):
  1. Bump version in `src/poli_page_fastapi/_version.py` and `CHANGELOG.md`.
  2. `git tag v0.x.y && git push --tags`.
  3. GitHub Actions release workflow builds + publishes to PyPI on tag push (one-time setup: register the package on PyPI after first release).
- **v0.1.0 launch sequence**:
  1. Verify CI green on all 6 matrix cells.
  2. Verify the integration test passes against `api-develop.poli.page`.
  3. Tag v0.1.0.
  4. Write a launch blog post on poli.page/blog (optional but recommended).

---

## 17. Deferred to v0.2+ (do NOT build in v0.1.0)

Calling these out explicitly so they don't sneak in mid-implementation.

| Feature | Why deferred |
|---|---|
| **Native async client support** (`AsyncPoliPage` + `async def` endpoints) | The SDK ships both `PoliPage` (sync) and `AsyncPoliPage` (async). v0.1.0 wires the sync client only. Async FastAPI endpoints work fine with the sync client via the framework's automatic threadpool; native async is the obvious v0.2. Will ship as `get_async_poli_page_client()` alongside the sync surface. |
| **Hook → signal bridge (`poli_page_fastapi.signals`)** | The SDK's `on_retry` / `on_error` callable hooks could be wrapped in `blinker` signals à la Django. Adds a transitive dep; not worth it until users ask. Document the explicit-callable pattern in v0.1's README. |
| **Custom OpenAPI generator** (auto-document `PdfResponse` etc. in OpenAPI schemas) | FastAPI's `response_class=` already populates the response section; explicit annotation by users handles the rest. Niche enough to defer. |
| **`PoliPageRouter`** (an `APIRouter` subclass with the exception handler pre-registered) | Tempting sugar; risk of fighting users' router-composition patterns. Defer until at least 3 users ask. |
| **Server-Sent Events / WebSocket helpers** | PDFs are request/response. Out of scope. |
| **Built-in caching helpers** (e.g., a `cached_pdf_response` that integrates with `fastapi-cache`) | Niche; caching strategies vary too much per app to pick a default. |
| **`get_poli_page_client_factory(settings: PoliPageSettings)`** (parametric dependency) | The `PoliPageDependency` class covers this case. No need for two surfaces. |
| **Multi-client config (`PoliPageSettings(model_config=SettingsConfigDict(env_prefix="POLI_PAGE_LIVE_"))` patterns)** | Doable today by hand; we don't ship sugar yet. Re-evaluate at v0.2 if multi-tenant use cases emerge. |
| **Sentry / OpenTelemetry auto-instrumentation** | Real value but only if the user is already on those stacks. Ship as separate `poli-page-fastapi-sentry` later. |
| **`fastapi-cli` plugin (`fastapi poli-page render ...`)** | Even if `fastapi-cli` matures into a real CLI ecosystem, we wait for it to stabilise before attaching commands. |

**Discipline rule**: when implementing, if a "small addition" feels tempting, check this list first. If it's here, defer. If it's not here, ask before adding.

---

## 18. Decision log

Captured so future agents don't relitigate.

| Decision | Choice | Why |
|---|---|---|
| Verdict (package vs recipe) | **Full package** | INTEGRATIONS_PLAN.md's "probably skip" was made before the trio shape was validated across five sister integrations. With Symfony / Next / Nest / Laravel / Django all shipping a thin idiomatic surface in <500 LOC, the same shape applied to FastAPI delivers more value than another README of `curl` recipes — see §1. |
| Sync vs async client in v0.1.0 | **Sync only** | Covers ~95% of FastAPI deployments today (most route functions are sync `def`). Async lands in v0.2 without breaking v0.1 — `get_async_poli_page_client()` ships alongside, no rename. |
| Client memo strategy | **`@lru_cache(maxsize=1)`** | Standard Python idiom; users override via FastAPI's first-class `app.dependency_overrides` mechanism. Mirrors the nextjs integration's memoisation. |
| Settings reader | **Pydantic `BaseSettings` (from `pydantic-settings`)** | Canonical FastAPI idiom; users already understand `model_config = SettingsConfigDict(...)`. Avoids a hand-rolled env parser. |
| Settings key style | **lowercase fields + `POLI_PAGE_*` env aliases** | Pydantic's `Field(alias=...)` lets us keep Pythonic field names while reading the canonical env names. |
| Response helpers shape | **Subclasses of Starlette response classes** | Participates in FastAPI's `response_class=` argument naturally. Same pattern `JSONResponse` / `HTMLResponse` use. Factory functions don't compose as well. |
| Exception handler registration | **Opt-in via `app.add_exception_handler(PoliPageError, ...)`** | Same philosophy as `@poli-page/nestjs`'s `PoliPageExceptionFilter`. FastAPI's exception-handler chain is pluggable — auto-registering would conflict with users' existing handlers. Delta from `@poli-page/nextjs` (which catches by default). |
| Response helpers catch errors? | **No — explicit `try/except` OR global handler** | Matches Django's choice. Pure transformation: `(SDK output) → Response`. Users compose with the handler from §10 for global error mapping, or per-endpoint `try/except`. |
| Lifespan integration | **Provide `poli_page_lifespan(app)` as opt-in helper** | Users pass it to `FastAPI(lifespan=poli_page_lifespan)`. Pre-warms the memo and calls `client.close()` on shutdown. Skipping it works too — the memo just initialises lazily on first request. |
| SDK hook bridge | **None in v0.1.0** | FastAPI has no built-in event bus; adding `blinker` as a hard dep isn't justified yet. Users pass callables directly to `PoliPage(on_retry=..., on_error=...)`. v0.2 may add `poli_page_fastapi.signals` as an opt-in extra. |
| CLI command | **None — `uvicorn` IS the smoke test** | FastAPI has no per-app CLI; users run `uvicorn main:app`. The example app's dashboard at `/` is the equivalent of a smoke command. See §9. |
| Lint + format | **ruff** | Replaces black + isort + flake8. Same as the SDK and django. |
| Type checker | **mypy strict** | De-facto standard; FastAPI's own codebase uses it. |
| Test runner | **pytest 8 + pytest-asyncio** | `asyncio_mode = "auto"` so `async def test_*` Just Works. No unittest. |
| Build backend | **hatchling** | Same as the SDK (`pyproject.toml`-based, PEP 621). Fast, zero-config. |
| Python version floor | **3.11** | Matches the SDK (`requires-python = ">=3.11"` in `sdk-python/pyproject.toml`). Cutting 3.10 lets us use PEP 655 `Required[...]` / `NotRequired[...]` cleanly. |
| FastAPI version range | **`^0.100`, `^0.110`** | 0.100 was the first stable Pydantic v2 release; 0.110 is the current recommended minor. Newer minors (`^0.120`+) will be added to CI as they ship. |
| Demo UI | **Inline HTML string in `main.py`** | Matches the symfony-bundle's interactive demo dashboard. Inline keeps the demo readable top-to-bottom; no Jinja2 dep. Cross-cutting requirement per INTEGRATIONS_PLAN.md §1. |
| Single-source `.env` | **Yes — workspace-root file only** | Hard requirement from Mickael (validated symfony-bundle session). No per-app `.env.local`. `python-dotenv` with explicit `dotenv_path=` in `main.py` + `tests/conftest.py`. |
| Unpublished SDK workaround | **`uv pip install -e ../sdk-python`** | Editable install — same as django §12. Clean primitive pip / uv understand directly. |
| Multi-client / multiple `POLI_PAGE_*` configs | **Use `PoliPageDependency(settings=...)` for per-instance** | The class-based dependency handles this without inventing a multi-client config schema. |
| CI / matrix | **GitHub Actions matrix (Py 3.11/3.12/3.13 × FastAPI 0.100/0.110)** | 6 cells, no tox layer needed since FastAPI's version range is narrow. |
| `TestClient` discipline | **Context-manager form mandatory in tests touching lifespan** | Bare `TestClient(app).get(...)` skips lifespan; tests would silently miss bugs. Documented in spec §14.4 + CLAUDE.md §10.2. |

---

## 19. Definition of done (v0.1.0)

- All §5 files exist; all §7 / §8 / §10 surfaces typed and tested.
- `pytest tests/unit` green with mypy + ruff also green.
- Integration test against `api-develop.poli.page` passes when run with a `pp_test_*` key.
- Example app boots with `uvicorn main:app --reload` and the `/` dashboard exercises all 10 SDK demo steps.
- README + CHANGELOG match the v0.1.0 row.
- Replacement `CLAUDE.md` (integration-flavoured) in place — drops the SDK-flavoured test-everything sections inherited from the template.
- CI matrix green across the 6 cells defined in §15.

---

## 20. Open questions (none blocking v0.1.0)

- Should `poli_page_lifespan` pre-warm the client by accessing one attribute (e.g., `_ = client.base_url`), forcing the memo to materialise at startup instead of on first request? **Default: no** — defeats the "no network at startup" guarantee for users who don't want a network-touching app boot. Document the trade-off; defer to v0.2.
- Should the `User-Agent` carry the `poli-page-fastapi` version on top of the SDK's? **Default: defer to first PR review** — same open question as symfony-bundle §20 and django §20.
- Should we ship a `PoliPageRouter` (`APIRouter` subclass with the exception handler pre-registered)? **Default: defer** per §17 — only if at least 3 users ask.
- Should we provide `get_poli_page_client_async` (a stub returning the sync client wrapped in `asyncio.to_thread`) before v0.2 ships the native async surface? **Default: no** — async users can call `await run_in_threadpool(client.render.pdf, ...)` themselves; adding a stub would set a precedent we'd want to deprecate in v0.2.
- Should the demo dashboard live inside `poli_page_fastapi` itself (a `dashboard_router: APIRouter`) so users can mount it in their own project? **Default: no** — the demo is an `example-app/` concern, not a feature. Re-evaluate if users ask.

These are noted, not blocking. Implementor can decide at first encounter.
