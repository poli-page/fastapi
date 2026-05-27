# `poli-page-fastapi` v0.1.0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship v0.1.0 of `poli-page-fastapi` — a FastAPI integration wrapping the official Python SDK (`poli-page` on PyPI, source at `../sdk-python/`). Gives FastAPI projects a memoised `Depends(get_poli_page_client)` factory, three Starlette-subclass response helpers, an opt-in `poli_page_exception_handler`, an ASGI lifespan helper, and a runnable `example-app/` with an interactive demo dashboard at `GET /` covering every SDK method.

**Architecture:** Modern src-layout Python package (PEP 621 / hatchling). Pydantic `BaseSettings` reads env; `@lru_cache` memoises the SDK client; pure-function and class-based dependencies; subclassed Starlette responses; opt-in exception handler registered via `app.add_exception_handler`. Wraps without reimplementing — HTTP, retries, error mapping all stay in the SDK.

**Tech stack:** Python 3.11+, FastAPI ^0.100 / ^0.110, Pydantic v2 + `pydantic-settings`, pytest 8 + pytest-asyncio, ruff (lint + format), mypy strict, hatchling, `uv` for env management.

**Spec:** `/Users/mickael/Projects/fastapi/docs/spec/fastapi-package-specification.md` — authoritative source for all design decisions. This plan implements that spec in 13 bite-sized, independently-reviewable tasks.

**Working directory throughout:** `/Users/mickael/Projects/fastapi/`

---

## Pre-flight: clean the scaffold

Before Task 1, inspect what's in the repo so existing `.gitkeep` placeholders or empty directories don't end up muddled with real code.

- [ ] **Step 0.1: Inspect repo state**

```bash
cd /Users/mickael/Projects/fastapi
ls -la src/ tests/ example-app/
git status
```

If empty `.gitkeep` files exist (`src/.gitkeep`, `tests/.gitkeep`, `example-app/.gitkeep`), remove them — but **fold the deletions into Task 1's commit**, not as a standalone change.

- [ ] **Step 0.2: Review the spec once**

```bash
less docs/spec/fastapi-package-specification.md
```

Pay particular attention to §1 (recipe → package justification), §6 (settings shape), §7 (dependency factory + class), §8 (response subclasses), §10 (exception handler), §13 (example app layout), §18 (decision log).

---

## Task 1: Bootstrap `pyproject.toml`, tooling, and CI

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore` (append if exists)
- Create: `tests/__init__.py`, `tests/unit/__init__.py`, `tests/integration/__init__.py`
- Create: `.github/workflows/ci.yml`
- Create: `LICENSE` (MIT) if absent

**Goal:** repo is `uv sync`-able and CI runs green (with auto-skip on no-tests-yet behaviour). No package code yet.

- [ ] **Step 1.1: Write `pyproject.toml`**

Create `/Users/mickael/Projects/fastapi/pyproject.toml`:

```toml
[build-system]
requires = ["hatchling>=1.21"]
build-backend = "hatchling.build"

[project]
name = "poli-page-fastapi"
dynamic = ["version"]
description = "FastAPI integration for the Poli Page PDF rendering API"
readme = "README.md"
license = { text = "MIT" }
requires-python = ">=3.11"
authors = [{ name = "Poli Page" }]
keywords = ["pdf", "html", "template", "rendering", "poli-page", "fastapi", "starlette"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Environment :: Web Environment",
    "Framework :: FastAPI",
    "Framework :: AsyncIO",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3 :: Only",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Topic :: Software Development :: Libraries :: Python Modules",
    "Typing :: Typed",
]
dependencies = [
    "fastapi>=0.100,<1.0",
    "pydantic>=2.0,<3",
    "pydantic-settings>=2.0,<3",
    "poli-page>=1.0,<2",
]

[project.optional-dependencies]
dev = [
    "pytest>=8",
    "pytest-asyncio>=0.23",
    "pytest-mock>=3.12",
    "httpx>=0.25",                  # required by FastAPI's TestClient
    "ruff>=0.6",
    "mypy>=1.10",
    "respx>=0.21",
    "python-dotenv>=1.0",
    "build>=1",
    "twine>=5",
]

[project.urls]
Homepage = "https://poli.page"
Documentation = "https://docs.poli.page/reference/sdk/python/"
Source = "https://github.com/poli-page/fastapi"
Issues = "https://github.com/poli-page/fastapi/issues"
Changelog = "https://github.com/poli-page/fastapi/blob/main/CHANGELOG.md"

[tool.hatch.version]
source = "regex"
path = "src/poli_page_fastapi/_version.py"
pattern = '__version__ = "(?P<version>[^"]+)"'

[tool.hatch.build.targets.wheel]
packages = ["src/poli_page_fastapi"]

[tool.hatch.build.targets.sdist]
include = [
    "/src",
    "/tests",
    "/README.md",
    "/CHANGELOG.md",
    "/LICENSE",
    "/pyproject.toml",
]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "B", "UP", "RUF", "SIM"]

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = ["B017"]   # B017 allows bare Exception in pytest.raises

[tool.mypy]
python_version = "3.11"
strict = true
files = ["src", "tests"]

[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_decorators = false       # @pytest.fixture / @pytest.mark.parametrize

[tool.pytest.ini_options]
asyncio_mode = "auto"
python_files = ["test_*.py"]
testpaths = ["tests"]
markers = ["integration: hits the live API; requires POLI_PAGE_API_KEY"]
```

- [ ] **Step 1.2: Append to `.gitignore`**

If `.gitignore` does not already cover them, append:

```
__pycache__/
*.py[cod]
*.egg-info/
.venv/
dist/
build/
.coverage
.mypy_cache/
.ruff_cache/
.pytest_cache/
```

Read the existing file first so you only append entries that aren't already there.

- [ ] **Step 1.3: Create empty test scaffolding**

```bash
mkdir -p /Users/mickael/Projects/fastapi/tests/unit /Users/mickael/Projects/fastapi/tests/integration
touch /Users/mickael/Projects/fastapi/tests/__init__.py
touch /Users/mickael/Projects/fastapi/tests/unit/__init__.py
touch /Users/mickael/Projects/fastapi/tests/integration/__init__.py
```

- [ ] **Step 1.4: Write `.github/workflows/ci.yml`**

Create `/Users/mickael/Projects/fastapi/.github/workflows/ci.yml`:

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
          if [ -f pyproject.toml ]; then
            uv sync --all-extras
            uv pip install "fastapi~=${{ matrix.fastapi }}.0"
          else
            echo "Skipping install: no pyproject.toml yet"
          fi
      - name: Lint
        run: |
          if [ -f pyproject.toml ]; then
            uv run ruff check .
          else
            echo "Skipping lint: no pyproject.toml yet"
          fi
      - name: Format
        run: |
          if [ -f pyproject.toml ]; then
            uv run ruff format --check .
          else
            echo "Skipping format: no pyproject.toml yet"
          fi
      - name: Type check
        run: |
          if [ -f pyproject.toml ] && [ -d src/poli_page_fastapi ]; then
            uv run mypy src tests
          else
            echo "Skipping mypy: no src/poli_page_fastapi yet"
          fi
      - name: Unit tests
        run: |
          if [ -d tests/unit ] && [ -n "$(find tests/unit -name 'test_*.py' 2>/dev/null)" ]; then
            uv run pytest tests/unit -v
          else
            echo "Skipping tests: no tests/unit/test_*.py yet"
          fi

  integration:
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - uses: astral-sh/setup-uv@v3
      - name: Install
        run: |
          if [ -f pyproject.toml ]; then
            uv sync --all-extras
          fi
      - name: Integration test against develop API
        env:
          POLI_PAGE_API_KEY: ${{ secrets.POLI_PAGE_DEVELOP_API_KEY }}
        run: |
          if [ -d tests/integration ] && [ -n "$(find tests/integration -name 'test_*.py' 2>/dev/null)" ]; then
            uv run pytest tests/integration -v
          else
            echo "Skipping integration tests: no tests/integration/test_*.py yet"
          fi
```

Each step's `if [ -f ... ]` guard makes a freshly-scaffolded repo green from day one. Don't remove the guards — they're the same auto-skip pattern used by symfony-bundle, nextjs, and django.

- [ ] **Step 1.5: Add MIT `LICENSE` if missing**

Use the standard SPDX MIT text. Copyright line: `Copyright (c) 2026 Poli Page`.

- [ ] **Step 1.6: Verify**

```bash
cd /Users/mickael/Projects/fastapi
uv sync --all-extras
uv run ruff check .       # should succeed with no files yet
uv run pytest tests       # should report "no tests ran"
```

If any of these error out, debug before continuing — the rest of the plan assumes a working dev environment.

- [ ] **Step 1.7: Commit**

```bash
git add pyproject.toml .gitignore .github/workflows/ci.yml LICENSE tests/__init__.py tests/unit/__init__.py tests/integration/__init__.py
# also `git rm` any .gitkeep files removed in Step 0.1
git commit -m "chore: bootstrap pyproject, tooling, and CI

- pyproject.toml with Python 3.11+ and FastAPI ^0.100/^0.110 targets
- ruff (lint + format) with SIM/UP/RUF rules enabled
- mypy strict
- pytest + pytest-asyncio (asyncio_mode=auto) + pytest-mock
- CI matrix (Py 3.11-3.13 x FastAPI 0.100/0.110) with auto-skip on
  missing config — repo green from day one"
```

---

## Task 2: Settings — `PoliPageSettings(BaseSettings)`

**Files:**
- Create: `src/poli_page_fastapi/__init__.py`
- Create: `src/poli_page_fastapi/_version.py`
- Create: `src/poli_page_fastapi/py.typed`
- Create: `src/poli_page_fastapi/settings.py`
- Create: `tests/conftest.py`
- Create: `tests/unit/conftest.py`
- Create: `tests/unit/test_settings.py`

**Goal:** `PoliPageSettings()` reads `POLI_PAGE_*` env vars per spec §6. Field validators reject bad-prefix keys and out-of-range numerics. No client yet — just the env reader.

- [ ] **Step 2.1: Write failing `tests/unit/test_settings.py`**

```python
"""Tests for poli_page_fastapi.settings.PoliPageSettings."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from poli_page_fastapi.settings import PoliPageSettings


def test_minimal_valid_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POLI_PAGE_API_KEY", "pp_test_valid")
    settings = PoliPageSettings()
    assert settings.api_key == "pp_test_valid"
    assert settings.base_url is None
    assert settings.timeout is None
    assert settings.max_retries is None
    assert settings.retry_delay is None


def test_pp_live_prefix_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POLI_PAGE_API_KEY", "pp_live_prod")
    settings = PoliPageSettings()
    assert settings.api_key == "pp_live_prod"


def test_missing_api_key_yields_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("POLI_PAGE_API_KEY", raising=False)
    settings = PoliPageSettings()
    assert settings.api_key is None


@pytest.mark.parametrize("bad_key", ["abc", "sk_test_x", "pp_abc", "pp_prod_x"])
def test_bad_prefix_api_key_raises(monkeypatch: pytest.MonkeyPatch, bad_key: str) -> None:
    monkeypatch.setenv("POLI_PAGE_API_KEY", bad_key)
    with pytest.raises(ValidationError, match="pp_test_ or pp_live_"):
        PoliPageSettings()


def test_base_url_read(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POLI_PAGE_API_KEY", "pp_test_x")
    monkeypatch.setenv("POLI_PAGE_BASE_URL", "https://api-develop.poli.page")
    settings = PoliPageSettings()
    assert settings.base_url == "https://api-develop.poli.page"


@pytest.mark.parametrize("bad_timeout", [0, -1, 601, 1000])
def test_timeout_out_of_range_raises(monkeypatch: pytest.MonkeyPatch, bad_timeout: float) -> None:
    monkeypatch.setenv("POLI_PAGE_API_KEY", "pp_test_x")
    monkeypatch.setenv("POLI_PAGE_TIMEOUT", str(bad_timeout))
    with pytest.raises(ValidationError, match="TIMEOUT"):
        PoliPageSettings()


@pytest.mark.parametrize("bad_retries", [-1, 11, 100])
def test_max_retries_out_of_range_raises(monkeypatch: pytest.MonkeyPatch, bad_retries: int) -> None:
    monkeypatch.setenv("POLI_PAGE_API_KEY", "pp_test_x")
    monkeypatch.setenv("POLI_PAGE_MAX_RETRIES", str(bad_retries))
    with pytest.raises(ValidationError, match="MAX_RETRIES"):
        PoliPageSettings()


@pytest.mark.parametrize("bad_delay", [-0.1, 31, 100])
def test_retry_delay_out_of_range_raises(monkeypatch: pytest.MonkeyPatch, bad_delay: float) -> None:
    monkeypatch.setenv("POLI_PAGE_API_KEY", "pp_test_x")
    monkeypatch.setenv("POLI_PAGE_RETRY_DELAY", str(bad_delay))
    with pytest.raises(ValidationError, match="RETRY_DELAY"):
        PoliPageSettings()


def test_all_options_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POLI_PAGE_API_KEY", "pp_test_x")
    monkeypatch.setenv("POLI_PAGE_BASE_URL", "https://api-develop.poli.page")
    monkeypatch.setenv("POLI_PAGE_TIMEOUT", "45")
    monkeypatch.setenv("POLI_PAGE_MAX_RETRIES", "5")
    monkeypatch.setenv("POLI_PAGE_RETRY_DELAY", "0.25")
    settings = PoliPageSettings()
    assert settings.api_key == "pp_test_x"
    assert settings.base_url == "https://api-develop.poli.page"
    assert settings.timeout == 45.0
    assert settings.max_retries == 5
    assert settings.retry_delay == 0.25
```

- [ ] **Step 2.2: Write root `tests/conftest.py` — repo-root `.env` loader**

```python
"""Root pytest conftest — loads the workspace-root .env once at collection time.

Single source of truth (INTEGRATIONS_PLAN.md §"Cross-cutting DX patterns" §2):
no per-app .env.local. Real shell exports always win.
"""

from __future__ import annotations

import os
from pathlib import Path


def _load_root_env() -> None:
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        os.environ.setdefault(key, val)


_load_root_env()
```

- [ ] **Step 2.3: Write `tests/unit/conftest.py` — autouse handler/task snapshot fixture**

```python
"""Unit-test autouse fixtures.

Snapshots SIGINT handler and asyncio pending tasks per test, restores in
teardown. Pattern carried from symfony-bundle's RestoresGlobalHandlers and
django/tests/conftest.py. See CLAUDE.md §10.3.
"""

from __future__ import annotations

import asyncio
import signal
from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True)
def restore_signal_handlers() -> Iterator[None]:
    """Snapshot and restore the SIGINT handler around each test."""
    saved = signal.getsignal(signal.SIGINT)
    try:
        yield
    finally:
        signal.signal(signal.SIGINT, saved)


@pytest.fixture(autouse=True)
def check_no_pending_tasks() -> Iterator[None]:
    """Assert no orphan asyncio tasks survive a test using a running loop."""
    yield
    try:
        loop = asyncio.get_event_loop_policy().get_event_loop()
    except RuntimeError:
        return
    if not loop.is_running():
        return
    leftover = [t for t in asyncio.all_tasks(loop) if not t.done()]
    # Exclude the current task itself (the pytest-asyncio runner).
    try:
        current = asyncio.current_task(loop)
        leftover = [t for t in leftover if t is not current]
    except RuntimeError:
        pass
    assert not leftover, f"Pending asyncio tasks leaked: {leftover}"
```

- [ ] **Step 2.4: Run tests to verify failure**

```bash
cd /Users/mickael/Projects/fastapi
uv run pytest tests/unit/test_settings.py -v
```

Expected: tests FAIL because `poli_page_fastapi.settings` does not exist.

- [ ] **Step 2.5: Write `_version.py` + `py.typed`**

Create `/Users/mickael/Projects/fastapi/src/poli_page_fastapi/_version.py`:

```python
__version__ = "0.1.0"
```

Create empty file `/Users/mickael/Projects/fastapi/src/poli_page_fastapi/py.typed` (PEP 561 marker — zero bytes is fine).

- [ ] **Step 2.6: Write `__init__.py` (initial)**

```python
"""FastAPI integration for the Poli Page PDF rendering SDK."""

from __future__ import annotations

from poli_page_fastapi._version import __version__
from poli_page_fastapi.settings import PoliPageSettings

__all__ = [
    "PoliPageSettings",
    "__version__",
]
```

The remaining exports (`get_poli_page_client`, response classes, exception handler, lifespan) land in later tasks. Keep the `__all__` updated as those land.

- [ ] **Step 2.7: Write `settings.py`**

Create `/Users/mickael/Projects/fastapi/src/poli_page_fastapi/settings.py`:

```python
"""Pydantic-settings reader for POLI_PAGE_* env vars."""

from __future__ import annotations

import re

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
        env_file=None,
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

- [ ] **Step 2.8: Run until green**

```bash
uv run pytest tests/unit/test_settings.py -v
uv run ruff check .
uv run mypy src tests
```

All three must pass before Task 3. If `ruff format --check` complains, run `uv run ruff format .`.

- [ ] **Step 2.9: Commit**

```bash
git add src/poli_page_fastapi/__init__.py src/poli_page_fastapi/_version.py src/poli_page_fastapi/py.typed src/poli_page_fastapi/settings.py tests/conftest.py tests/unit/conftest.py tests/unit/test_settings.py
git commit -m "feat: PoliPageSettings(BaseSettings) for POLI_PAGE_* env

Reads POLI_PAGE_API_KEY / POLI_PAGE_BASE_URL / POLI_PAGE_TIMEOUT /
POLI_PAGE_MAX_RETRIES / POLI_PAGE_RETRY_DELAY via pydantic-settings.
Field validators reject:
- api_key not matching ^pp_(test|live)_
- timeout outside (0, 600] seconds
- max_retries outside [0, 10]
- retry_delay outside [0, 30] seconds

Missing POLI_PAGE_API_KEY leaves api_key=None so the SDK's own
env-var fallback can pick it up (see spec §6.3).

Also lands the root tests/conftest.py (.env loader) and
tests/unit/conftest.py (autouse signal-handler + asyncio-task
snapshot fixtures, per CLAUDE.md §10.3)."
```

---

## Task 3: RFC 5987 header helper — `_headers.py`

**Files:**
- Create: `src/poli_page_fastapi/_headers.py`
- Create: `tests/unit/test_headers.py`

**Goal:** `build_content_disposition(filename, *, inline=False)` returns the correct header string for ASCII and non-ASCII filenames. Port the tests character-for-character from `symfony-bundle/tests/Unit/Http/PoliPageResponseFactoryTest.php`.

- [ ] **Step 3.1: Write failing `tests/unit/test_headers.py`**

```python
"""Tests for poli_page_fastapi._headers.build_content_disposition."""

from __future__ import annotations

import pytest

from poli_page_fastapi._headers import build_content_disposition


def test_ascii_filename_attachment() -> None:
    assert build_content_disposition("invoice.pdf") == 'attachment; filename="invoice.pdf"'


def test_ascii_filename_inline() -> None:
    assert build_content_disposition("invoice.pdf", inline=True) == 'inline; filename="invoice.pdf"'


def test_non_ascii_filename_attachment() -> None:
    # Note: encode("ascii", "replace") yields "?" for unencodable chars.
    result = build_content_disposition("naïve.pdf")
    assert result.startswith('attachment; filename="na?ve.pdf"; filename*=UTF-8\'\'')
    assert "na%C3%AFve.pdf" in result


def test_non_ascii_filename_inline() -> None:
    result = build_content_disposition("résumé.pdf", inline=True)
    assert result.startswith('inline; filename="r?sum?.pdf"; filename*=UTF-8\'\'')
    assert "r%C3%A9sum%C3%A9.pdf" in result


@pytest.mark.parametrize(
    "filename,expected_encoded",
    [
        ("über.pdf", "%C3%BCber.pdf"),
        ("é.pdf", "%C3%A9.pdf"),
        ("naïve résumé.pdf", "na%C3%AFve%20r%C3%A9sum%C3%A9.pdf"),
        ("漢字.pdf", "%E6%BC%A2%E5%AD%97.pdf"),
        ("emoji 🎉.pdf", "emoji%20%F0%9F%8E%89.pdf"),
    ],
)
def test_rfc5987_encoding(filename: str, expected_encoded: str) -> None:
    result = build_content_disposition(filename)
    assert expected_encoded in result


def test_filename_with_quotes_escaped() -> None:
    # Edge case: filename with an embedded double quote.
    # The bundle's implementation does NOT escape quotes inside the ASCII
    # fallback (RFC 6266 leaves this ambiguous in practice). Match its
    # behaviour exactly — the *= form is the authoritative one anyway.
    result = build_content_disposition('he"llo.pdf')
    # ASCII-safe path is taken.
    assert result == 'attachment; filename="he"llo.pdf"'
```

- [ ] **Step 3.2: Run to verify failure**

```bash
uv run pytest tests/unit/test_headers.py -v
```

- [ ] **Step 3.3: Write `_headers.py`**

```python
"""Internal: RFC 5987 / RFC 6266 Content-Disposition encoding.

Ported character-for-character from symfony-bundle's PoliPageResponseFactory
and nextjs's headers.ts. The bundle's unit tests are the canonical reference.
"""

from __future__ import annotations

from urllib.parse import quote


def build_content_disposition(filename: str, *, inline: bool = False) -> str:
    """Return a Content-Disposition header value with correct filename encoding.

    ASCII-safe filenames: `attachment; filename="..."`.
    Non-ASCII filenames: dual form — `attachment; filename="<ascii-fallback>"; filename*=UTF-8''...`.
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

- [ ] **Step 3.4: Run to green**

```bash
uv run pytest tests/unit/test_headers.py -v
uv run ruff check . && uv run mypy src tests
```

- [ ] **Step 3.5: Commit**

```bash
git add src/poli_page_fastapi/_headers.py tests/unit/test_headers.py
git commit -m "feat: RFC 5987 Content-Disposition encoding helper

build_content_disposition(filename, *, inline=False) returns the
correct header string. ASCII-safe filenames take the simple form;
non-ASCII filenames produce dual filename= / filename*= notation
per RFC 6266.

Ported character-for-character from symfony-bundle's
PoliPageResponseFactory."
```

---

## Task 4: Response classes — `responses.py`

**Files:**
- Edit: `src/poli_page_fastapi/__init__.py` (add exports)
- Create: `src/poli_page_fastapi/responses.py`
- Create: `tests/unit/test_responses.py`

**Goal:** `PdfResponse`, `PdfStreamResponse`, `PreviewResponse`, `DocumentRedirectResponse` set correct headers per spec §8.

- [ ] **Step 4.1: Write failing `tests/unit/test_responses.py`**

```python
"""Tests for poli_page_fastapi.responses."""

from __future__ import annotations

import pytest

from poli_page_fastapi.responses import (
    DocumentRedirectResponse,
    PdfResponse,
    PdfStreamResponse,
    PreviewResponse,
)


def test_pdf_response_default_headers() -> None:
    resp = PdfResponse(b"%PDF-1.4\n...", filename="invoice.pdf")
    assert resp.status_code == 200
    assert resp.media_type == "application/pdf"
    assert resp.headers["content-type"].startswith("application/pdf")
    assert resp.headers["content-disposition"] == 'attachment; filename="invoice.pdf"'
    assert resp.headers["cache-control"] == "no-store, private"
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.body == b"%PDF-1.4\n..."


def test_pdf_response_inline_flips_disposition() -> None:
    resp = PdfResponse(b"%PDF", filename="x.pdf", inline=True)
    assert resp.headers["content-disposition"] == 'inline; filename="x.pdf"'


def test_pdf_response_non_ascii_filename() -> None:
    resp = PdfResponse(b"%PDF", filename="résumé.pdf")
    disp = resp.headers["content-disposition"]
    assert disp.startswith('attachment; filename="r?sum?.pdf"; filename*=UTF-8\'\'')
    assert "r%C3%A9sum%C3%A9.pdf" in disp


def test_pdf_response_user_headers_merged() -> None:
    resp = PdfResponse(b"%PDF", filename="x.pdf", headers={"X-Custom": "yes"})
    assert resp.headers["x-custom"] == "yes"
    # Default headers still present.
    assert resp.headers["cache-control"] == "no-store, private"


def test_pdf_response_user_can_override_cache_control() -> None:
    resp = PdfResponse(b"%PDF", filename="x.pdf", headers={"Cache-Control": "public, max-age=60"})
    assert resp.headers["cache-control"] == "public, max-age=60"


def test_pdf_stream_response_headers() -> None:
    def gen() -> "iter[bytes]":
        yield b"%PDF-1.4\n"
        yield b"...\n"

    resp = PdfStreamResponse(gen(), filename="big.pdf")
    assert resp.media_type == "application/pdf"
    assert resp.headers["content-disposition"] == 'attachment; filename="big.pdf"'
    assert resp.headers["cache-control"] == "no-store, private"
    assert resp.headers["x-content-type-options"] == "nosniff"


def test_preview_response_headers() -> None:
    resp = PreviewResponse("<p>Hello</p>")
    assert resp.status_code == 200
    assert resp.media_type.startswith("text/html")
    assert "charset=utf-8" in resp.headers["content-type"]
    assert resp.headers["cache-control"] == "no-store, private"
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.body == b"<p>Hello</p>"


def test_document_redirect_response_default() -> None:
    resp = DocumentRedirectResponse("https://s3.example.com/doc.pdf?sig=abc")
    assert resp.status_code == 302
    assert resp.headers["location"] == "https://s3.example.com/doc.pdf?sig=abc"
    assert resp.headers["cache-control"] == "no-store, private"


def test_document_redirect_response_permanent() -> None:
    resp = DocumentRedirectResponse("https://s3.example.com/doc.pdf", permanent=True)
    assert resp.status_code == 308
```

- [ ] **Step 4.2: Run to verify failure**

```bash
uv run pytest tests/unit/test_responses.py -v
```

- [ ] **Step 4.3: Write `responses.py`**

```python
"""Response helpers — Starlette response subclasses with the right headers."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

from starlette.background import BackgroundTask
from starlette.responses import Response, StreamingResponse

from poli_page_fastapi._headers import build_content_disposition

_PDF_DEFAULT_HEADERS = {
    "Cache-Control": "no-store, private",
    "X-Content-Type-Options": "nosniff",
}


class PdfResponse(Response):
    """A PDF response with correct Content-Type, Content-Disposition, Cache-Control."""

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
        for k, v in _PDF_DEFAULT_HEADERS.items():
            merged.setdefault(k, v)
        super().__init__(
            content=content,
            media_type="application/pdf",
            headers=merged,
            background=background,
        )


class PdfStreamResponse(StreamingResponse):
    """A streamed PDF response for client.render.pdf_stream(...) iterators."""

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
        for k, v in _PDF_DEFAULT_HEADERS.items():
            merged.setdefault(k, v)
        super().__init__(
            content=content,
            media_type="application/pdf",
            headers=merged,
            background=background,
        )


class PreviewResponse(Response):
    """An HTML preview response — text/html; charset=utf-8."""

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
        super().__init__(
            content=b"",
            status_code=status_code,
            headers=merged,
            background=background,
        )
```

- [ ] **Step 4.4: Update `__init__.py` exports**

```python
"""FastAPI integration for the Poli Page PDF rendering SDK."""

from __future__ import annotations

from poli_page_fastapi._version import __version__
from poli_page_fastapi.responses import (
    DocumentRedirectResponse,
    PdfResponse,
    PdfStreamResponse,
    PreviewResponse,
)
from poli_page_fastapi.settings import PoliPageSettings

__all__ = [
    "DocumentRedirectResponse",
    "PdfResponse",
    "PdfStreamResponse",
    "PoliPageSettings",
    "PreviewResponse",
    "__version__",
]
```

- [ ] **Step 4.5: Run until green**

```bash
uv run pytest tests/unit/test_responses.py -v
uv run ruff check . && uv run mypy src tests
```

- [ ] **Step 4.6: Commit**

```bash
git add src/poli_page_fastapi/responses.py src/poli_page_fastapi/__init__.py tests/unit/test_responses.py
git commit -m "feat: response helpers (PdfResponse, PdfStreamResponse, PreviewResponse, DocumentRedirectResponse)

Subclasses of Starlette's Response / StreamingResponse with:
- Content-Type: application/pdf (PdfResponse, PdfStreamResponse)
              text/html; charset=utf-8 (PreviewResponse)
- Content-Disposition: RFC 5987-encoded filename (ASCII fallback + UTF-8 form)
- Cache-Control: no-store, private (defaults; user-overridable)
- X-Content-Type-Options: nosniff
- inline=True flips disposition to inline

DocumentRedirectResponse issues 302 by default, 308 when permanent=True.
All helpers compose with FastAPI's response_class= argument."
```

---

## Task 5: Dependency factory + class — `dependencies.py`

**Files:**
- Edit: `src/poli_page_fastapi/__init__.py`
- Create: `src/poli_page_fastapi/dependencies.py`
- Create: `tests/unit/test_dependencies.py`

**Goal:** `get_poli_page_client()` returns a memoised `PoliPage`. `PoliPageDependency` class supports per-instance overrides.

- [ ] **Step 5.1: Write failing `tests/unit/test_dependencies.py`**

```python
"""Tests for poli_page_fastapi.dependencies."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from poli_page_fastapi.dependencies import PoliPageDependency, get_poli_page_client
from poli_page_fastapi.settings import PoliPageSettings


@pytest.fixture(autouse=True)
def _clear_factory_cache() -> None:
    """Reset the lru_cache between tests so each test sees a fresh factory."""
    get_poli_page_client.cache_clear()


def test_get_poli_page_client_builds_with_env(
    monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
) -> None:
    monkeypatch.setenv("POLI_PAGE_API_KEY", "pp_test_x")
    monkeypatch.setenv("POLI_PAGE_TIMEOUT", "42")
    mock_cls = mocker.patch("poli_page_fastapi.dependencies.PoliPage")
    get_poli_page_client()
    mock_cls.assert_called_once_with(api_key="pp_test_x", timeout=42.0)


def test_get_poli_page_client_memoises(
    monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
) -> None:
    monkeypatch.setenv("POLI_PAGE_API_KEY", "pp_test_x")
    mock_cls = mocker.patch("poli_page_fastapi.dependencies.PoliPage")
    a = get_poli_page_client()
    b = get_poli_page_client()
    assert a is b
    assert mock_cls.call_count == 1


def test_get_poli_page_client_omits_unset_kwargs(
    monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
) -> None:
    monkeypatch.setenv("POLI_PAGE_API_KEY", "pp_test_x")
    monkeypatch.delenv("POLI_PAGE_TIMEOUT", raising=False)
    monkeypatch.delenv("POLI_PAGE_BASE_URL", raising=False)
    mock_cls = mocker.patch("poli_page_fastapi.dependencies.PoliPage")
    get_poli_page_client()
    # Only api_key passed; timeout/base_url/etc. omitted so SDK defaults apply.
    mock_cls.assert_called_once_with(api_key="pp_test_x")


def test_poli_page_dependency_with_explicit_client() -> None:
    mock_client = MagicMock()
    dep = PoliPageDependency(client=mock_client)
    assert dep() is mock_client


def test_poli_page_dependency_with_settings(mocker: MockerFixture) -> None:
    settings = PoliPageSettings(POLI_PAGE_API_KEY="pp_test_y", POLI_PAGE_TIMEOUT=30)  # type: ignore[call-arg]
    mock_cls = mocker.patch("poli_page_fastapi.dependencies.PoliPage")
    mock_cls.return_value = MagicMock()
    dep = PoliPageDependency(settings=settings)
    client_a = dep()
    client_b = dep()
    # Per-instance memo: same client returned on second call.
    assert client_a is client_b
    mock_cls.assert_called_once_with(api_key="pp_test_y", timeout=30.0)


def test_poli_page_dependency_close_calls_sdk_close() -> None:
    mock_client = MagicMock()
    dep = PoliPageDependency(client=mock_client)
    dep()  # materialise
    dep.close()
    # When client was passed in, close() does NOT close it
    # (caller-owned lifecycle). Verify behaviour matches.
    # Adjust to spec if needed — let the spec call this out.
    # Per spec §7.2: close() calls close() and clears the cache.
    # We assert close() is called and cache is cleared.
    mock_client.close.assert_called_once()
    assert dep._cached_client is None


def test_poli_page_dependency_independent_from_global(
    monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
) -> None:
    monkeypatch.setenv("POLI_PAGE_API_KEY", "pp_test_global")
    mock_cls = mocker.patch("poli_page_fastapi.dependencies.PoliPage")
    global_client = get_poli_page_client()

    settings = PoliPageSettings(POLI_PAGE_API_KEY="pp_test_other")  # type: ignore[call-arg]
    dep = PoliPageDependency(settings=settings)
    dep_client = dep()
    # The PoliPage class is mocked — both calls return MagicMock instances,
    # but they're distinct objects since each call creates a new mock.
    # The point is the dependency does NOT touch the global memo.
    assert mock_cls.call_count == 2
```

A note about `test_poli_page_dependency_close_calls_sdk_close`: the spec is ambiguous about whether `close()` on an explicit-client dependency calls `client.close()` (caller-owned) or not. **Default:** call `close()` since the dependency's `close()` is an explicit user action. Update the spec §7.2 wording to match if needed.

- [ ] **Step 5.2: Run to verify failure**

```bash
uv run pytest tests/unit/test_dependencies.py -v
```

- [ ] **Step 5.3: Write `dependencies.py`**

```python
"""FastAPI dependency factory and class for the Poli Page SDK client."""

from __future__ import annotations

from functools import lru_cache

from poli_page import PoliPage

from poli_page_fastapi.settings import PoliPageSettings


def _settings_to_kwargs(settings: PoliPageSettings) -> dict[str, object]:
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
    return kwargs


@lru_cache(maxsize=1)
def get_poli_page_client() -> PoliPage:
    """Return the process-wide memoised PoliPage client.

    Used as `Depends(get_poli_page_client)` in route signatures. The lru_cache
    decorator guarantees one instance per process; to inject a mock in tests,
    use `app.dependency_overrides[get_poli_page_client] = lambda: mock`.
    """
    settings = PoliPageSettings()
    return PoliPage(**_settings_to_kwargs(settings))


class PoliPageDependency:
    """Callable dependency that builds a per-instance client.

    Use when you want explicit settings or a per-router client distinct
    from the global memo:

        custom = PoliPageDependency(settings=PoliPageSettings(POLI_PAGE_API_KEY="pp_test_b"))

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
        self._cached_client: PoliPage | None = client

    def __call__(self) -> PoliPage:
        if self._cached_client is not None:
            return self._cached_client
        settings = self._settings or PoliPageSettings()
        self._cached_client = PoliPage(**_settings_to_kwargs(settings))
        return self._cached_client

    def close(self) -> None:
        """Close the underlying SDK client and clear the cache."""
        if self._cached_client is not None:
            self._cached_client.close()
            self._cached_client = None
```

- [ ] **Step 5.4: Update `__init__.py`**

```python
from poli_page_fastapi.dependencies import PoliPageDependency, get_poli_page_client
```

Add `PoliPageDependency` and `get_poli_page_client` to `__all__`.

- [ ] **Step 5.5: Run until green**

```bash
uv run pytest tests/unit/ -v
uv run ruff check . && uv run mypy src tests
```

- [ ] **Step 5.6: Commit**

```bash
git add src/poli_page_fastapi/dependencies.py src/poli_page_fastapi/__init__.py tests/unit/test_dependencies.py
git commit -m "feat: get_poli_page_client + PoliPageDependency

- get_poli_page_client() — lru_cache(maxsize=1) memoised module-level
  factory; canonical Depends(...) access path
- PoliPageDependency — class-based dependency for per-instance overrides
  (per-router clients, sandbox-vs-prod split, explicit client injection)

Tests use app.dependency_overrides for mock injection — the idiomatic
FastAPI mechanism. lru_cache is reset between tests via an autouse
fixture so each test sees a fresh factory."
```

---

## Task 6: Exception handler — `exceptions.py`

**Files:**
- Edit: `src/poli_page_fastapi/__init__.py`
- Create: `src/poli_page_fastapi/exceptions.py`
- Create: `tests/unit/test_exceptions.py`

**Goal:** `poli_page_exception_handler(request, exc)` maps each `PoliPageError` subclass to a `JSONResponse` with the documented body shape (spec §10.1).

- [ ] **Step 6.1: Write failing `tests/unit/test_exceptions.py`**

```python
"""Tests for poli_page_fastapi.exceptions.poli_page_exception_handler."""

from __future__ import annotations

import json
from typing import Any

import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse

from poli_page import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    ConflictError,
    GoneError,
    InternalServerError,
    NotFoundError,
    PermissionDeniedError,
    PoliPageError,
    RateLimitError,
    UnprocessableEntityError,
)
from poli_page_fastapi.exceptions import poli_page_exception_handler


def _fake_request() -> Request:
    """Construct a minimal Starlette Request for handler tests."""
    scope: dict[str, Any] = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "query_string": b"",
    }
    return Request(scope)


def _body(resp: JSONResponse) -> dict[str, Any]:
    return json.loads(bytes(resp.body))


@pytest.mark.parametrize(
    "exc_cls,status",
    [
        (BadRequestError, 400),
        (AuthenticationError, 401),
        (PermissionDeniedError, 403),
        (NotFoundError, 404),
        (ConflictError, 409),
        (GoneError, 410),
        (UnprocessableEntityError, 422),
        (RateLimitError, 429),
        (InternalServerError, 500),
    ],
)
def test_api_status_error_maps_to_same_status(exc_cls: type[PoliPageError], status: int) -> None:
    exc = exc_cls(
        message="failure",
        code="TEST_CODE",
        status=status,
        request_id="req_abc",
    )
    resp = poli_page_exception_handler(_fake_request(), exc)
    assert isinstance(resp, JSONResponse)
    assert resp.status_code == status
    body = _body(resp)
    assert body == {"code": "TEST_CODE", "message": "failure", "request_id": "req_abc"}


def test_api_connection_error_maps_to_502() -> None:
    exc = APIConnectionError("connection refused", code="network_error")
    resp = poli_page_exception_handler(_fake_request(), exc)
    assert resp.status_code == 502
    body = _body(resp)
    assert body == {"code": "network_error", "message": "connection refused", "request_id": None}


def test_api_timeout_error_maps_to_502() -> None:
    exc = APITimeoutError("deadline exceeded", code="timeout")
    resp = poli_page_exception_handler(_fake_request(), exc)
    assert resp.status_code == 502
    body = _body(resp)
    assert body["code"] == "timeout"


def test_base_poli_page_error_maps_to_500() -> None:
    exc = PoliPageError("bad config", code="invalid_options")
    resp = poli_page_exception_handler(_fake_request(), exc)
    assert resp.status_code == 500
    body = _body(resp)
    assert body == {"code": "invalid_options", "message": "bad config", "request_id": None}


def test_non_poli_page_error_returns_500() -> None:
    exc = ValueError("not a poli page error")
    resp = poli_page_exception_handler(_fake_request(), exc)
    assert resp.status_code == 500
    body = _body(resp)
    assert body["code"] == "UNKNOWN"


def test_response_has_no_store_cache_header() -> None:
    exc = BadRequestError("x", code="X", status=400)
    resp = poli_page_exception_handler(_fake_request(), exc)
    assert resp.headers["cache-control"] == "no-store, private"


def test_request_id_optional() -> None:
    exc = BadRequestError("x", code="X", status=400)  # no request_id
    resp = poli_page_exception_handler(_fake_request(), exc)
    body = _body(resp)
    assert body["request_id"] is None
```

- [ ] **Step 6.2: Run to verify failure**

```bash
uv run pytest tests/unit/test_exceptions.py -v
```

- [ ] **Step 6.3: Write `exceptions.py`**

```python
"""Opt-in exception handler bridging PoliPageError to FastAPI JSON responses.

Register via:

    from poli_page import PoliPageError
    from poli_page_fastapi import poli_page_exception_handler

    app.add_exception_handler(PoliPageError, poli_page_exception_handler)
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from poli_page import APIConnectionError, APIStatusError, PoliPageError


def poli_page_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Map any PoliPageError to a typed JSON response.

    Status code: matches exc.status for APIStatusError; 502 for
    APIConnectionError / APITimeoutError; 500 for the base PoliPageError
    (validation / programming errors). Body shape mirrors the SDK's own
    error structure, plus request_id (null when absent).
    """
    if not isinstance(exc, PoliPageError):
        return JSONResponse(
            status_code=500,
            content={"code": "UNKNOWN", "message": str(exc), "request_id": None},
            headers={"Cache-Control": "no-store, private"},
        )

    if isinstance(exc, APIStatusError) and exc.status is not None:
        status_code = exc.status
    elif isinstance(exc, APIConnectionError):
        status_code = 502
    else:
        status_code = 500

    return JSONResponse(
        status_code=status_code,
        content={
            "code": exc.code,
            "message": exc.message,
            "request_id": exc.request_id,
        },
        headers={"Cache-Control": "no-store, private"},
    )
```

- [ ] **Step 6.4: Update `__init__.py`**

```python
from poli_page_fastapi.exceptions import poli_page_exception_handler
```

Add `poli_page_exception_handler` to `__all__`.

- [ ] **Step 6.5: Run until green**

```bash
uv run pytest tests/unit/ -v
uv run ruff check . && uv run mypy src tests
```

- [ ] **Step 6.6: Commit**

```bash
git add src/poli_page_fastapi/exceptions.py src/poli_page_fastapi/__init__.py tests/unit/test_exceptions.py
git commit -m "feat: poli_page_exception_handler — opt-in PoliPageError → JSON

Maps each PoliPageError subclass to a JSONResponse:
- APIStatusError (4xx/5xx) → same status, body {code, message, request_id}
- APIConnectionError / APITimeoutError → 502 with the underlying code/message
- Bare PoliPageError → 500

Registered explicitly via app.add_exception_handler(PoliPageError, ...).
Same opt-in philosophy as @poli-page/nestjs's PoliPageExceptionFilter
(spec §10.2). Response includes Cache-Control: no-store, private."
```

---

## Task 7: Lifespan helper — `lifespan.py`

**Files:**
- Edit: `src/poli_page_fastapi/__init__.py`
- Create: `src/poli_page_fastapi/lifespan.py`
- Create: `tests/unit/test_lifespan.py`

**Goal:** `poli_page_lifespan(app)` is an async context manager. Entering builds the client (warming the memo); exiting calls `client.close()`.

- [ ] **Step 7.1: Write failing `tests/unit/test_lifespan.py`**

```python
"""Tests for poli_page_fastapi.lifespan.poli_page_lifespan."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture

from poli_page_fastapi.dependencies import get_poli_page_client
from poli_page_fastapi.lifespan import poli_page_lifespan


@pytest.fixture(autouse=True)
def _clear_factory_cache() -> None:
    get_poli_page_client.cache_clear()


def test_lifespan_warms_and_closes_client(
    monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
) -> None:
    monkeypatch.setenv("POLI_PAGE_API_KEY", "pp_test_x")
    mock_client = MagicMock()
    mock_cls = mocker.patch("poli_page_fastapi.dependencies.PoliPage", return_value=mock_client)

    app = FastAPI(lifespan=poli_page_lifespan)

    @app.get("/ping")
    def ping() -> dict[str, str]:
        return {"ok": "true"}

    # TestClient as a context manager triggers startup / shutdown.
    with TestClient(app) as client:
        # Client was built during startup.
        assert mock_cls.call_count == 1
        response = client.get("/ping")
        assert response.status_code == 200
    # On shutdown, close() was called.
    mock_client.close.assert_called_once()


def test_lifespan_no_warmup_without_context_manager(
    monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
) -> None:
    """Bare TestClient(app).get(...) without `with` skips lifespan.

    Documented in CLAUDE.md §10.2. This test PROVES the gotcha: the
    factory is NOT called when the lifespan doesn't fire.
    """
    monkeypatch.setenv("POLI_PAGE_API_KEY", "pp_test_x")
    mock_cls = mocker.patch("poli_page_fastapi.dependencies.PoliPage")

    app = FastAPI(lifespan=poli_page_lifespan)

    @app.get("/ping")
    def ping() -> dict[str, str]:
        return {"ok": "true"}

    client = TestClient(app)
    client.get("/ping")
    # Lifespan did NOT fire — startup hook didn't run.
    assert mock_cls.call_count == 0
```

- [ ] **Step 7.2: Run to verify failure**

```bash
uv run pytest tests/unit/test_lifespan.py -v
```

- [ ] **Step 7.3: Write `lifespan.py`**

```python
"""ASGI lifespan helper: warm the client at startup, close at shutdown."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from poli_page_fastapi.dependencies import get_poli_page_client


@asynccontextmanager
async def poli_page_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """ASGI lifespan that builds the Poli Page client on startup,
    closes it on shutdown.

    Usage:

        app = FastAPI(lifespan=poli_page_lifespan)
    """
    client = get_poli_page_client()
    try:
        yield
    finally:
        client.close()
        get_poli_page_client.cache_clear()
```

- [ ] **Step 7.4: Update `__init__.py`**

```python
from poli_page_fastapi.lifespan import poli_page_lifespan
```

Add `poli_page_lifespan` to `__all__`.

- [ ] **Step 7.5: Run until green**

```bash
uv run pytest tests/unit/ -v
uv run ruff check . && uv run mypy src tests
```

- [ ] **Step 7.6: Commit**

```bash
git add src/poli_page_fastapi/lifespan.py src/poli_page_fastapi/__init__.py tests/unit/test_lifespan.py
git commit -m "feat: poli_page_lifespan(app) — startup/shutdown integration

Async context manager users pass to FastAPI(lifespan=...). On startup,
calls get_poli_page_client() to warm the memo. On shutdown, calls
client.close() and clears the cache so the next app start gets a fresh
client (important for tests).

TestClient must be used as a context manager (`with TestClient(app)`)
for the lifespan to fire — bare TestClient(app).get(...) skips it.
Documented in CLAUDE.md §10.2 and verified by a test."
```

---

## Task 8: Integration test against develop API

**Files:**
- Create: `tests/integration/test_render_against_develop_api.py`

**Goal:** one happy-path test against `api-develop.poli.page`. Skipped when `POLI_PAGE_API_KEY` is unset; refuses to run with `pp_live_*` keys.

- [ ] **Step 8.1: Write the test**

Create `/Users/mickael/Projects/fastapi/tests/integration/test_render_against_develop_api.py`:

```python
"""One end-to-end test against api-develop.poli.page.

Skipped automatically when POLI_PAGE_API_KEY is unset. Refuses to run with
a pp_live_* key. See spec §14.1.
"""

from __future__ import annotations

import os

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from poli_page import PoliPage
from poli_page_fastapi import (
    PdfResponse,
    PoliPageDependency,
    PoliPageSettings,
    poli_page_lifespan,
)

pytestmark = pytest.mark.skipif(
    os.environ.get("POLI_PAGE_API_KEY") is None,
    reason="POLI_PAGE_API_KEY env var not set",
)


def _check_test_key() -> str:
    key = os.environ["POLI_PAGE_API_KEY"]
    if key.startswith("pp_live_"):
        pytest.fail("Integration test refuses to run with a pp_live_* key.")
    return key


@pytest.mark.integration
def test_render_pdf_against_develop_api() -> None:
    api_key = _check_test_key()
    settings = PoliPageSettings.model_construct(
        api_key=api_key,
        base_url="https://api-develop.poli.page",
    )
    dep = PoliPageDependency(settings=settings)

    app = FastAPI(lifespan=poli_page_lifespan)

    @app.get("/render", response_class=PdfResponse)
    def render(client: PoliPage = Depends(dep)) -> PdfResponse:
        pdf = client.render.pdf({
            "project": "getting-started",
            "template": "welcome",
            "version": "1.0.0",
            "data": {"name": "fastapi integration test"},
        })
        return PdfResponse(pdf, filename="welcome.pdf")

    with TestClient(app) as client:
        response = client.get("/render")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content[:5] == b"%PDF-"
    assert len(response.content) > 1000  # sanity: a real PDF, not a stub
```

- [ ] **Step 8.2: Run the test (when an API key is available)**

```bash
POLI_PAGE_API_KEY=pp_test_xxx uv run pytest tests/integration -v
```

In CI it runs gated on the `POLI_PAGE_DEVELOP_API_KEY` secret. Locally without a key, the test is `SKIPPED`.

- [ ] **Step 8.3: Commit**

```bash
git add tests/integration/test_render_against_develop_api.py
git commit -m "test: integration test against api-develop.poli.page

One happy-path test rendering getting-started/welcome via the full
TestClient + lifespan + PoliPageDependency stack. Asserts response is
200, Content-Type is application/pdf, body starts with %PDF-, length
is non-trivial.

Skipped automatically when POLI_PAGE_API_KEY is unset; refuses to run
with a pp_live_* key (safety belt — integration tests never hit
production)."
```

---

## Task 9: `example-app/` — FastAPI demo project with interactive dashboard

**Files:**
- Create: `example-app/main.py`
- Create: `example-app/pyproject.toml`
- Create: `example-app/README.md`

**Goal:** A self-contained FastAPI app at `example-app/main.py` that mirrors `sdk-python/demo/sync_demo.py` 1:1. Single-page interactive dashboard at `GET /`. Uses `poli_page_lifespan` + `poli_page_exception_handler` + all response helpers + `Depends(get_poli_page_client)`.

- [ ] **Step 9.1: Inspect the SDK demo**

```bash
less /Users/mickael/Projects/sdk-python/demo/sync_demo.py
less /Users/mickael/Projects/sdk-python/demo/_shared.py
```

Note the 10 steps. Each becomes one route in our app.

- [ ] **Step 9.2: Inspect the Symfony reference dashboard**

```bash
less /Users/mickael/Projects/symfony-bundle/example-app/templates/demo.html
```

Copy the CSS variables (`--bg`, `--ink`, `--brand`, font stacks). Copy the JS state machine for document lifecycle. The HTML structure is one button per SDK feature; gate `documents.get` / `.thumbnails` / `.preview` / `.delete` on `documents.create` having returned an ID.

- [ ] **Step 9.3: Write `example-app/pyproject.toml`**

```toml
[project]
name = "poli-page-fastapi-example"
version = "0.1.0"
description = "Interactive demo of poli-page-fastapi against api-develop.poli.page"
requires-python = ">=3.11"
dependencies = [
    "poli-page-fastapi @ file://${PROJECT_ROOT}/..",
    "uvicorn[standard]>=0.27",
    "python-dotenv>=1.0",
]
```

(The `file://${PROJECT_ROOT}/..` syntax is uv-flavored — adjust to `tool.uv.sources` if uv is required.)

- [ ] **Step 9.4: Write `example-app/main.py` — scaffolding (lifespan + handler + first route)**

```python
"""Interactive demo app for poli-page-fastapi.

Mirrors sdk-python/demo/sync_demo.py step-for-step. The home page (GET /)
serves a single-page interactive dashboard exercising all 10 SDK demos.

Run: uvicorn main:app --reload --port 8000
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Single root .env — see INTEGRATIONS_PLAN.md §"Cross-cutting DX patterns" §2.
_ROOT_ENV = Path(__file__).resolve().parent.parent.parent / ".env"
if _ROOT_ENV.exists():
    load_dotenv(_ROOT_ENV, override=False)

from fastapi import Depends, FastAPI, HTTPException  # noqa: E402 — load env first
from fastapi.responses import HTMLResponse, JSONResponse, Response  # noqa: E402

from poli_page import PoliPage, PoliPageError, fs  # noqa: E402
from poli_page_fastapi import (  # noqa: E402
    DocumentRedirectResponse,
    PdfResponse,
    PdfStreamResponse,
    PreviewResponse,
    get_poli_page_client,
    poli_page_exception_handler,
    poli_page_lifespan,
)

logger = logging.getLogger("example-app")
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="poli-page-fastapi demo",
    description="Interactive demo of every SDK feature against api-develop.poli.page",
    lifespan=poli_page_lifespan,
)
app.add_exception_handler(PoliPageError, poli_page_exception_handler)

DASHBOARD_HTML = """<!doctype html>
<!-- The dashboard HTML lives below; see Step 9.6. -->
"""

DEMO_PROJECT = "getting-started"
DEMO_TEMPLATE = "welcome"
DEMO_VERSION = "1.0.0"
DEMO_DATA = {"name": "FastAPI demo"}


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def dashboard() -> str:
    return DASHBOARD_HTML
```

- [ ] **Step 9.5: Add the 10 demo routes**

Append to `main.py`:

```python
# ----- 1. render.pdf
@app.get("/render/pdf", response_class=PdfResponse, tags=["render"])
def render_pdf(client: PoliPage = Depends(get_poli_page_client)) -> PdfResponse:
    pdf = client.render.pdf({
        "project": DEMO_PROJECT,
        "template": DEMO_TEMPLATE,
        "version": DEMO_VERSION,
        "data": DEMO_DATA,
    })
    return PdfResponse(pdf, filename="welcome.pdf", inline=True)


# ----- 2. render.pdf_stream
@app.get("/render/stream", response_class=PdfStreamResponse, tags=["render"])
def render_stream(client: PoliPage = Depends(get_poli_page_client)) -> PdfStreamResponse:
    # render.pdf_stream returns a context manager yielding an Iterator[bytes].
    # For demo purposes, we materialise into a single generator the response
    # consumes; production code can hand the iterator to PdfStreamResponse
    # directly and rely on the body iterator's lifecycle.
    def gen() -> Any:
        with client.render.pdf_stream({
            "project": DEMO_PROJECT,
            "template": DEMO_TEMPLATE,
            "version": DEMO_VERSION,
            "data": DEMO_DATA,
        }) as chunks:
            yield from chunks
    return PdfStreamResponse(gen(), filename="welcome-stream.pdf", inline=True)


# ----- 3. render_to_file
@app.post("/render/file", tags=["render"])
def render_to_file(client: PoliPage = Depends(get_poli_page_client)) -> dict[str, str]:
    output = Path(__file__).resolve().parent / "output" / "welcome.pdf"
    output.parent.mkdir(exist_ok=True)
    fs.render_to_file(
        client,
        {
            "project": DEMO_PROJECT,
            "template": DEMO_TEMPLATE,
            "version": DEMO_VERSION,
            "data": DEMO_DATA,
        },
        path=str(output),
    )
    return {"path": str(output), "size_bytes": str(output.stat().st_size)}


# ----- 4. render.preview
@app.get("/render/preview", response_class=PreviewResponse, tags=["render"])
def render_preview(client: PoliPage = Depends(get_poli_page_client)) -> PreviewResponse:
    preview = client.render.preview({
        "project": DEMO_PROJECT,
        "template": DEMO_TEMPLATE,
        "version": DEMO_VERSION,
        "data": DEMO_DATA,
    })
    return PreviewResponse(preview.html)


# ----- 5. render.document
@app.post("/documents", tags=["documents"])
def document_create(client: PoliPage = Depends(get_poli_page_client)) -> dict[str, Any]:
    descriptor = client.render.document({
        "project": DEMO_PROJECT,
        "template": DEMO_TEMPLATE,
        "version": DEMO_VERSION,
        "data": DEMO_DATA,
    })
    return {
        "document_id": descriptor.document_id,
        "presigned_pdf_url": descriptor.presigned_pdf_url,
        "expires_at": descriptor.expires_at,
        "page_count": descriptor.page_count,
        "size_bytes": descriptor.size_bytes,
    }


# ----- 6. documents.get
@app.get("/documents/{document_id}", tags=["documents"])
def document_get(
    document_id: str, client: PoliPage = Depends(get_poli_page_client)
) -> DocumentRedirectResponse:
    descriptor = client.documents.get(document_id)
    return DocumentRedirectResponse(descriptor.presigned_pdf_url)


# ----- 7. documents.thumbnails
@app.get("/documents/{document_id}/thumbnails", tags=["documents"])
def document_thumbnails(
    document_id: str, client: PoliPage = Depends(get_poli_page_client)
) -> dict[str, list[dict[str, Any]]]:
    thumbnails = client.documents.thumbnails(document_id, {"width": 320, "format": "png"})
    return {
        "thumbnails": [
            {
                "page": t.page,
                "width": t.width,
                "height": t.height,
                "content_type": t.content_type,
                "data": t.data,  # already base64
            }
            for t in thumbnails
        ],
    }


# ----- 8. documents.preview
@app.get("/documents/{document_id}/preview", response_class=PreviewResponse, tags=["documents"])
def document_preview(
    document_id: str, client: PoliPage = Depends(get_poli_page_client)
) -> PreviewResponse:
    preview = client.documents.preview(document_id)
    return PreviewResponse(preview.html)


# ----- 9. documents.delete
@app.delete("/documents/{document_id}", status_code=204, tags=["documents"])
def document_delete(
    document_id: str, client: PoliPage = Depends(get_poli_page_client)
) -> Response:
    client.documents.delete(document_id)
    return Response(status_code=204)


# ----- 10. Error handling: deliberately trigger an INVALID_VERSION_FORMAT
@app.get("/errors/bad-version", tags=["errors"])
def error_bad_version(client: PoliPage = Depends(get_poli_page_client)) -> JSONResponse:
    # Calling with a clearly malformed version surfaces a BadRequestError
    # with code='INVALID_VERSION_FORMAT'. The global exception handler maps
    # it to a typed JSON response — we let it bubble.
    client.render.pdf({
        "project": DEMO_PROJECT,
        "template": DEMO_TEMPLATE,
        "version": "not.a.version",
        "data": DEMO_DATA,
    })
    # Should never reach here.
    raise HTTPException(status_code=500, detail="Expected SDK to raise; did not.")
```

- [ ] **Step 9.6: Write `DASHBOARD_HTML`**

Replace the placeholder string with a full single-file HTML document mirroring the symfony-bundle's `templates/demo.html`. Structure:

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>poli-page-fastapi — interactive demo</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;700&family=IBM+Plex+Sans:wght@400;500&family=JetBrains+Mono:wght@400;500&display=swap" />
  <style>
    :root {
      --bg: #ffffff;
      --ink: #1d1d1f;
      --muted: #6b7280;
      --brand: #4f5d99;
      --brand-soft: #eef0f9;
      --line: #e6e6ea;
      --danger: #b3261e;
      --ok: #1f6f3a;
      --code: #f5f5f7;
    }
    body { font-family: 'IBM Plex Sans', system-ui, sans-serif; color: var(--ink); margin: 0; background: var(--bg); }
    /* ... full CSS, copied character-for-character from
       symfony-bundle/example-app/templates/demo.html ... */
  </style>
</head>
<body>
  <header>
    <h1 style="font-family: Manrope, sans-serif">poli-page-fastapi</h1>
    <p>Interactive demo of every SDK feature. Buttons call the FastAPI routes;
       responses render inline.</p>
  </header>

  <main>
    <!-- 1. render.pdf -->
    <section data-step="render-pdf">
      <h2>1. render.pdf — buffered PDF</h2>
      <button data-action="render-pdf">Render PDF</button>
      <iframe data-target="render-pdf-iframe" style="display:none"></iframe>
    </section>

    <!-- 2. render.pdf_stream -->
    <!-- 3. render_to_file -->
    <!-- 4. render.preview -->
    <!-- 5. documents.create -->
    <!-- 6. documents.get -->
    <!-- 7. documents.thumbnails -->
    <!-- 8. documents.preview -->
    <!-- 9. documents.delete -->
    <!-- 10. errors -->
    <!-- ... -->
  </main>

  <script>
    // Vanilla JS — no framework. State machine for the document lifecycle:
    let currentDocumentId = null;
    function setDocumentId(id) {
      currentDocumentId = id;
      document.querySelectorAll('[data-requires-document]').forEach(el => {
        el.disabled = !id;
      });
    }
    setDocumentId(null);

    document.querySelector('[data-action="render-pdf"]').addEventListener('click', async () => {
      const iframe = document.querySelector('[data-target="render-pdf-iframe"]');
      iframe.src = '/render/pdf';
      iframe.style.display = 'block';
    });

    // ... handlers for steps 2-10 ...
  </script>
</body>
</html>
```

**Implementation note:** porting the full CSS + JS from `symfony-bundle/example-app/templates/demo.html` is the bulk of this step. Read that file in full and copy the styling and JS, adapting any URL paths to the FastAPI route shapes above. The end result is a single self-contained HTML string ~440 lines.

- [ ] **Step 9.7: Write `example-app/README.md`**

```markdown
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

Set `POLI_PAGE_API_KEY=pp_test_...` in the workspace-root `.env` (one level
up from `example-app/`). Real shell exports always win.

## Routes

| Path | Method | SDK feature |
|---|---|---|
| `/` | GET | Interactive dashboard |
| `/render/pdf` | GET | `client.render.pdf` |
| `/render/stream` | GET | `client.render.pdf_stream` |
| `/render/file` | POST | `poli_page.fs.render_to_file` |
| `/render/preview` | GET | `client.render.preview` |
| `/documents` | POST | `client.render.document` |
| `/documents/{id}` | GET | `client.documents.get` (302) |
| `/documents/{id}/thumbnails` | GET | `client.documents.thumbnails` |
| `/documents/{id}/preview` | GET | `client.documents.preview` |
| `/documents/{id}` | DELETE | `client.documents.delete` |
| `/errors/bad-version` | GET | Triggers `BadRequestError` |
```

- [ ] **Step 9.8: Smoke test**

```bash
cd /Users/mickael/Projects/fastapi/example-app
uv sync
POLI_PAGE_API_KEY=pp_test_... uv run uvicorn main:app --reload --port 8000
```

Open <http://localhost:8000> and click each button. All 10 should succeed against `api-develop.poli.page`. If they don't, **debug the example app, not the package** — the package's unit tests are already green; any failure is wiring.

- [ ] **Step 9.9: Commit**

```bash
git add example-app/
git commit -m "feat(example-app): FastAPI app covering all 10 SDK demo steps

Single-file FastAPI app (main.py) with:
- poli_page_lifespan for startup/shutdown
- poli_page_exception_handler for uniform error JSON
- One @app.get / @app.post per SDK feature (10 total)
- GET / serves an interactive HTML dashboard (~440 lines, no build step)
- Reads the workspace-root .env via python-dotenv (no .env.local)

Aesthetic copied from symfony-bundle's templates/demo.html: white
surface, indigo #4f5d99, Manrope + IBM Plex Sans + JetBrains Mono.
Cross-cutting requirement per INTEGRATIONS_PLAN.md §1."
```

---

## Task 10: README

**Files:**
- Create / replace: `README.md`

**Goal:** ~250-line README focused on the "how does this look in FastAPI specifically" angle, NOT a re-doc of the SDK.

- [ ] **Step 10.1: Write `README.md`**

Sections to cover (one short example each):

1. **Install** — `pip install poli-page-fastapi`.
2. **First PDF render** — 10-line snippet: `FastAPI(lifespan=...)`, register handler, one `@app.get` route returning `PdfResponse`.
3. **Settings (env vars)** — table of `POLI_PAGE_*` vars and the matching SDK kwarg.
4. **Dependency injection** — `Depends(get_poli_page_client)` for the simple case; `PoliPageDependency(settings=...)` for per-router overrides.
5. **Response helpers** — `PdfResponse`, `PdfStreamResponse`, `PreviewResponse`, `DocumentRedirectResponse`. One-line each.
6. **Error handling** — register `poli_page_exception_handler` globally, OR per-endpoint `try/except`. Show both.
7. **Async endpoints** — the SDK is sync; FastAPI runs sync routes in a threadpool automatically. For `async def` endpoints, use `await run_in_threadpool(client.render.pdf, ...)`.
8. **Testing with dependency overrides** — `app.dependency_overrides[get_poli_page_client] = lambda: mock`.
9. **Lifespan** — `FastAPI(lifespan=poli_page_lifespan)` for explicit warmup / cleanup. Optional.
10. **Pointer to `example-app/`** — interactive demo dashboard.

Aim for ~250 lines. The SDK's README is the deep-dive surface.

- [ ] **Step 10.2: Write `CHANGELOG.md`**

Keep-a-Changelog format. v0.1.0 entry summarising the surface above.

- [ ] **Step 10.3: Commit**

```bash
git add README.md CHANGELOG.md
git commit -m "docs: README and CHANGELOG for v0.1.0

README covers install, first-PDF snippet, settings table, dependency
patterns (factory + class), response helpers, error handling
(global handler vs per-endpoint try/except), async-endpoint recipe,
testing with dependency_overrides, lifespan opt-in, and pointer to
example-app/.

CHANGELOG seeded with the v0.1.0 row in Keep a Changelog format."
```

---

## Task 11: Replace inherited `CLAUDE.md` (already done as part of this PR if writing it ahead)

**Files:**
- Replace: `CLAUDE.md`

**Goal:** the inherited SDK-flavored CLAUDE.md is replaced by an integration-flavored version. This is typically done in a separate PR before the rest of the work, but if it wasn't, do it now.

- [ ] **Step 11.1: If `CLAUDE.md` still has the SDK template, replace it with the integration-flavored version**

The replacement is in `docs/spec/fastapi-package-specification.md` §2's required-reading list. The full content lives at `/Users/mickael/Projects/fastapi/CLAUDE.md` after this plan's setup (it was authored alongside the spec).

Verify by `grep`:

```bash
grep -c "Every public method of the client class" CLAUDE.md && \
  echo "FAIL: inherited template still present" || \
  echo "OK: integration-flavored CLAUDE.md in place"
```

- [ ] **Step 11.2: Commit (only if a replacement was needed)**

```bash
git add CLAUDE.md
git commit -m "docs: replace SDK-flavored CLAUDE.md with integration-specific version

The inherited template told agents to test SDK behaviour (transport,
retries, 4xx mapping, etc.) — already exhaustively covered in
sdk-python/tests. This integration's job is wiring, not behaviour.
Replacement focuses on:
- FastAPI dependency injection conventions
- Pydantic-settings + opt-in exception handler
- TestClient context-manager discipline (lifespan firing)
- Signal-handler / asyncio-task leak hygiene
- Single root .env workflow

Mirrors django/CLAUDE.md §10 and nextjs/CLAUDE.md §10 — the
'Known gotchas' section captures battle-tested cross-integration
lessons."
```

---

## Task 12: Final verification

**Goal:** every test green, every lint green, every type-check green, example app boots, integration test passes against `api-develop.poli.page`.

- [ ] **Step 12.1: Full local check**

```bash
cd /Users/mickael/Projects/fastapi
uv sync --all-extras
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
uv run pytest tests/unit -v
POLI_PAGE_API_KEY=pp_test_xxx uv run pytest tests/integration -v
```

Every command MUST exit 0. If any fail, fix and re-run.

- [ ] **Step 12.2: Example-app smoke test**

```bash
cd example-app
uv sync
POLI_PAGE_API_KEY=pp_test_xxx uv run uvicorn main:app --port 8000 &
SERVER=$!
sleep 2
curl -sf http://localhost:8000/ -o /dev/null && echo "dashboard OK" || echo "dashboard FAIL"
curl -sf http://localhost:8000/render/preview -o /dev/null && echo "preview OK" || echo "preview FAIL"
kill $SERVER
```

Manual verification: open <http://localhost:8000> in a browser and click each of the 10 buttons. Every one should produce the expected inline preview / JSON / file response.

- [ ] **Step 12.3: CI verification**

Push to a feature branch:

```bash
git push -u origin feat/v0.1.0-final
```

Open a PR. Verify all 6 matrix cells go green. The `integration` job is gated on `github.ref == 'refs/heads/main'` so it won't run on the branch; merge to `main` triggers it.

- [ ] **Step 12.4: Tag v0.1.0**

After merge to main and the integration job is green:

```bash
git checkout main
git pull
git tag v0.1.0
git push --tags
```

A PyPI release workflow (`.github/workflows/publish.yml`) is set up at first release time; this plan doesn't ship one (PyPI registration is a one-off chore done manually after tagging).

---

## Task 13: Release prep (post-launch admin)

- [ ] **Step 13.1: Register on PyPI**

```bash
uv build
uv pip install twine
twine upload dist/*
```

(One-time. After this, the publish workflow handles future tags.)

- [ ] **Step 13.2: Update `INTEGRATIONS_PLAN.md`**

Mark FastAPI's row in the verdict table from "Probably skip → recipe" to "Yes — full package, shipped v0.1.0 on 2026-05-27" and link the published PyPI page. This re-classification is the canonical record of why we built it.

- [ ] **Step 13.3: Optional launch blog post**

Coordinate with Mickael — short post on poli.page/blog announcing the FastAPI package, the inline demo, and a 6-line code snippet showing how to wire it in. Link the GitHub repo and the example-app.

---

## Definition of done (recap)

- All §5 spec files exist in `src/poli_page_fastapi/`.
- `pytest tests/unit` green; `mypy src tests` green; `ruff check .` + `ruff format --check .` green.
- Integration test passes against `api-develop.poli.page` with a `pp_test_*` key.
- `example-app/main.py` boots with `uvicorn main:app --reload`; all 10 demo buttons work in the browser.
- README + CHANGELOG match v0.1.0.
- Replacement integration-flavored `CLAUDE.md` is in place.
- CI matrix green across the 6 cells defined in spec §15.
- Tag `v0.1.0` pushed; PyPI release published.

If any of those are red, the plan is not done — finish the failing item before claiming the milestone.
