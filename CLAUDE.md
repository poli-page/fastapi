# CLAUDE.md

> Instructions for Claude Code agents working in `poli-page/fastapi`.

## 1. Repo at a glance

| Field        | Value |
| ------------ | ----- |
| Repository   | `poli-page/fastapi` |
| Type         | Framework integration (FastAPI package) |
| Language     | Python 3.11+ |
| FastAPI      | `^0.100`, `^0.110` |
| Registry     | PyPI — `poli-page-fastapi` |
| Depends on   | `poli-page` (PyPI; `^1.0`), `pydantic-settings` (`^2.0`) |
| Roadmap slot | P1.2 |

**Source-of-truth docs (read first):**
- `docs/spec/fastapi-package-specification.md` — full design spec for v0.1.0
- `docs/plan/2026-05-27-implementation.md` — implementation plan
- `/Users/mickael/Projects/INTEGRATIONS_PLAN.md` — cross-repo umbrella note, esp. §"Cross-cutting DX patterns"
- `/Users/mickael/Projects/django/CLAUDE.md` — sister Python integration (same SDK, different framework)
- `/Users/mickael/Projects/nextjs/CLAUDE.md` §10 — battle-tested cross-cutting gotchas

## 2. The package's job

This package is a **thin FastAPI-idiomatic wrapper** around the official Poli Page Python SDK (`poli-page` on PyPI, source at `/Users/mickael/Projects/sdk-python/`). It provides:

- A FastAPI dependency factory `get_poli_page_client()` plus the `PoliPageDependency` class for explicit `Depends(...)` use
- Pydantic `BaseSettings` (`PoliPageSettings`) reading `POLI_PAGE_*` env vars
- Response helpers (`PdfResponse`, `PreviewResponse`, `DocumentRedirectResponse`) that subclass Starlette response classes with correct headers (RFC 5987 filename encoding)
- An **opt-in** exception handler `poli_page_exception_handler(request, exc)` users register with `app.add_exception_handler(PoliPageError, poli_page_exception_handler)`
- An ASGI lifespan helper `poli_page_lifespan(app)` that warms / closes the client on startup / shutdown
- An example app at `example-app/` with the same interactive demo dashboard shipped in `symfony-bundle/example-app/templates/demo.html`

**This package does NOT** reimplement HTTP transport, retries, error classification, idempotency keys, stream chunking, or anything else the SDK already does. Bug in those areas? Fix it in `sdk-python`, not here.

**This package does NOT** ship: a Starlette middleware (the exception handler is the integration point), a CLI command, a class-based `APIRoute` subclass, an automatic OpenAPI extension, or Pages-Router-style decorators. See `docs/spec/fastapi-package-specification.md` §1 for the explicit "isn't" list.

## 3. Working language

- **Code, comments, file names, commit messages, PR descriptions, repository documentation**: English.
- **Day-to-day conversation with Xavier/Mickael**: French, tutoiement.
- **Conversation in this Claude Code session**: French is fine for the chat; artifacts stay English.

## 4. TDD is mandatory

RED → GREEN → refactor for every change. Tests live in `tests/unit/` (mocked SDK, 95%+ of the suite) and `tests/integration/` (one happy-path test against `api-develop.poli.page`, gated on `POLI_PAGE_API_KEY`).

### What to test (integration-specific!)
- **Settings**: `PoliPageSettings()` reads `POLI_PAGE_API_KEY` / `POLI_PAGE_BASE_URL` / `POLI_PAGE_TIMEOUT` / `POLI_PAGE_MAX_RETRIES` / `POLI_PAGE_RETRY_DELAY` env; missing key raises; `pp_test_*` / `pp_live_*` prefix enforced via Pydantic validator.
- **Dependency factory**: `get_poli_page_client()` memoises (LRU/process-wide); successive `Depends(get_poli_page_client)` calls receive the same `PoliPage` instance; `app.dependency_overrides[get_poli_page_client] = lambda: mock` works.
- **`PoliPageDependency` class**: callable returns a configured client; per-instance overrides (`PoliPageDependency(settings=...)`) bypass the global memo.
- **Response helpers**: `PdfResponse`, `PreviewResponse`, `DocumentRedirectResponse` each set the right `Content-Type`, RFC 5987 `Content-Disposition`, `Cache-Control`, `X-Content-Type-Options`. ASCII AND non-ASCII filenames both encode correctly. Port the bundle's filename tests character-for-character.
- **Exception handler**: `poli_page_exception_handler` maps each `PoliPageError` subclass to a `JSONResponse` with the documented status/body shape (4xx → same status, 5xx → same status, `APIConnectionError` / `APITimeoutError` → 502 with `code: 'NETWORK_ERROR'`). `request_id` field always present (null when absent).
- **Lifespan**: `poli_page_lifespan(app)` builds the client at startup, calls `client.close()` at shutdown; works with FastAPI's `TestClient` context-manager idiom.

### What NOT to test (the SDK already does)
- HTTP transport behaviour (`httpx` edge cases, connection pooling)
- Retry policy (backoff, max attempts, `Retry-After`, never-retry-4xx)
- 4xx / 5xx → `PoliPageError` subclass mapping
- Idempotency-Key generation
- Stream chunking correctness
- API contract drift — the SDK's contract tests own that

Re-testing these here doubles maintenance burden. **If you find yourself writing a `respx` mock HTTP server, stop — you're doing the SDK's job.**

## 5. Robustness over shortcuts

Mickael's hard rule (validated across symfony-bundle, nextjs, and django sessions): **no hacks to make a test pass or a corner case go away**. Fix root causes. If a workaround is genuinely required (framework bug, SDK quirk), document it inline with a `# Why:` comment naming the constraint.

Concretely: **no `# type: ignore`, no `# noqa` to silence warnings, no `pytest.skip` to mask flakes**. The skip we DO allow is `pytest.mark.skipif(os.getenv("POLI_PAGE_API_KEY") is None)` for the gated integration test — that one is by design.

## 6. Code conventions

- **ruff** for linting AND formatting. Config in `pyproject.toml`, mirrors the SDK's rules: `select = ["E", "F", "W", "I", "B", "UP", "RUF", "SIM"]`.
- **mypy strict mode**. Configured in `pyproject.toml`. No `# type: ignore`; if Pydantic / Starlette typing is annoying, file the workaround with a `# Why:` comment naming the upstream issue.
- **`from __future__ import annotations`** at the top of every module — lets us use PEP 604 (`X | Y`) cleanly on 3.11.
- **No commented-out code, no `TODO` without a linked issue, no `print()`** in committed code (use the `poli_page_fastapi` logger).
- **Default to no comments.** Add one only when the *why* is non-obvious. Comments restating *what* the code does are noise.
- **Async first where the SDK supports it.** The SDK ships both `PoliPage` (sync) and `AsyncPoliPage` (async). v0.1.0 wires the **sync** client only; async endpoints call `await run_in_threadpool(client.render.pdf, ...)`. Document the pattern in the README. Native `AsyncPoliPage` support is v0.2 (see spec §17).

## 7. Commits and PRs

- **Conventional Commits**: `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`.
- **One concern per PR**, reviewable in under 30 minutes.
- PR description: what changed, why, how it was tested.
- CI must be green before merge.

## 8. CI

Workflow: `.github/workflows/ci.yml`. Matrix: Python `3.11`/`3.12`/`3.13` × FastAPI `^0.100`/`^0.110`. Each step auto-skips if the relevant config is missing (so a freshly scaffolded repo is green from day one). Don't change that behaviour.

Local mirror:
```bash
uv sync --all-extras
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
uv run pytest
```

## 9. Unpublished-SDK note (dev-time only)

The Python SDK (`poli-page` on PyPI) is **already published**, so for normal dev you just `uv sync` / `pip install -e .[dev]`. When iterating against unreleased SDK changes, install the local checkout in editable mode:

```bash
uv pip install -e ../sdk-python    # from inside the fastapi repo's venv
```

The integration's `pyproject.toml` stays clean (`"poli-page>=1.0,<2"`). When the SDK ships a new compatible version, just bump the pin — no source-code changes here.

## 10. Known gotchas (battle-tested — don't relearn the hard way)

These caught us once in `symfony-bundle` / `nextjs` / `django` or surface from FastAPI / pytest-asyncio specifics. Recorded so future agents don't burn a session rediscovering them.

### 10.1 No CLI — `uvicorn` IS the smoke test

FastAPI ships **no per-app CLI for end-users**: `uvicorn main:app --reload` (or `fastapi dev` from the `fastapi-cli` package) is what users run. There is no Symfony Console / Artisan / `manage.py` equivalent we can attach a `poli_page:render` command to. The example-app's `uvicorn main:app` + the demo UI at `/` ARE the smoke test. **Do NOT** try to invent a `poli-page-fastapi` CLI script — it would not be discoverable through the framework's idiomatic surface. If a user wants programmatic smoke-testing, they import the SDK directly.

### 10.2 `TestClient` MUST be used as a context manager

FastAPI's `TestClient` (`starlette.testclient.TestClient`) only triggers the ASGI lifespan events when used as a context manager:

```python
with TestClient(app) as client:
    response = client.get("/")
```

Bare `TestClient(app).get(...)` skips `startup` / `shutdown` entirely — your `poli_page_lifespan` will not run, and resources won't get cleaned up. Every test that exercises the lifespan-wired client must use `with TestClient(app) as client:`. Documented in spec §10.4.

### 10.3 Async task / signal-handler / event-loop leak hygiene

pytest-asyncio + uvicorn / Starlette can leave dangling tasks and signal handlers between tests. Two specific hazards we carry from the symfony-bundle's `RestoresGlobalHandlers` lesson:

1. **`signal.signal(SIGINT, ...)` handlers** — uvicorn's worker registers them; tests that load uvicorn programmatically can leak.
2. **Dangling asyncio tasks** — a coroutine started in one test that isn't awaited can resurface in the next test's event loop.

**Fix in place**: `tests/conftest.py` ships an autouse `restore_signal_handlers` fixture that snapshots `signal.getsignal(SIGINT)` in setup and unwinds in teardown, plus a `check_no_pending_tasks` fixture that asserts `asyncio.all_tasks()` is empty after each test using a running loop. Apply to any test that constructs `TestClient(app)` or imports uvicorn.

Pattern carried from `symfony-bundle/tests/RestoresGlobalHandlers.php` and `django/tests/conftest.py`. Documented as cross-cutting in `INTEGRATIONS_PLAN.md` §4.

**Do NOT** "fix" this by disabling pytest-asyncio's `loop_scope="function"`. Same rule as symfony-bundle §10.1.

### 10.4 Single root `.env`, no per-app `.env.local`

The example app's `main.py` loads the workspace-root `.env` (`/Users/mickael/Projects/.env`) via `python-dotenv` with explicit `dotenv_path`, and `tests/conftest.py` does the same for the test suite. Real shell exports always win (`load_dotenv(..., override=False)`).

**Do NOT** introduce a `.env.local` in `example-app/` or instruct users to `cp .env .env.local`. This was an explicit hard requirement from Mickael during the symfony-bundle session. See `INTEGRATIONS_PLAN.md` §"Cross-cutting DX patterns" §2.

### 10.5 Response helpers and the exception handler do NOT auto-catch

The response helpers in `poli_page_fastapi.responses` are pure transformations — they do NOT call the SDK and do NOT wrap calls in `try/except`. Users either compose explicit `try/except PoliPageError` in their endpoints OR opt into the global handler via `app.add_exception_handler(PoliPageError, poli_page_exception_handler)`. This is the **same opt-in philosophy** as `@poli-page/nestjs`'s `PoliPageExceptionFilter` and a deliberate delta from `@poli-page/nextjs`'s `createPoliPageRouteHandler()` (which catches by default). Documented in spec §10.

### 10.6 The dependency factory is memoised — testing requires `app.dependency_overrides`

`get_poli_page_client()` is decorated with `@lru_cache` (or `functools.cache`) so successive `Depends(...)` calls receive the same `PoliPage` instance. To inject a mock in tests, use FastAPI's first-class override mechanism:

```python
app.dependency_overrides[get_poli_page_client] = lambda: mock_client
# ... run tests ...
app.dependency_overrides.clear()
```

**Do NOT** try to `get_poli_page_client.cache_clear()` and rebuild — the override mechanism is the idiomatic FastAPI surface. Documented in spec §7.

### 10.7 Demo lives at `GET /` in the example app, not as `curl` recipes

The example app's home page (`GET /`, returning an `HTMLResponse`) is a single-page interactive dashboard with one button per SDK feature, inline `<iframe>` PDF previews, JSON pretty-print, and a document-lifecycle state machine in client-side JS. Aesthetic copied from `/Users/mickael/Projects/symfony-bundle/example-app/templates/demo.html`: white surface, brand indigo `#4f5d99`, Manrope display sans + IBM Plex Sans body + JetBrains Mono code.

**Do NOT** replace this with a README listing `curl` commands. Cross-cutting requirement from `INTEGRATIONS_PLAN.md` §"Cross-cutting DX patterns" §1.

## 11. When stuck

- Re-read `docs/spec/fastapi-package-specification.md` first; most "open questions" are answered there or in §18 "Resolved decisions".
- Compare with `sdk-python` at `/Users/mickael/Projects/sdk-python/` — public classes, exception hierarchy, `RetryEvent` shape.
- Compare patterns with `sentry-sdk[fastapi]`, `fastapi-users`, `slowapi`, `strawberry-graphql[fastapi]`, `fastapi-pagination` (the package's industry benchmarks).
- Look at the sister Django integration at `/Users/mickael/Projects/django/` — same SDK, parallel decisions for response helpers and per-endpoint `try/except`.
- Ask Mickael early. A two-line message is faster than a half-day rebuilding the wrong thing.
- If a CI failure looks unrelated to your change, check `main` first before assuming you caused it.
