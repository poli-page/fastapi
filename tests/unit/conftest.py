"""Unit-test autouse fixtures.

Snapshots SIGINT handler and asyncio pending tasks per test, restores in
teardown. Pattern carried from symfony-bundle's RestoresGlobalHandlers and
django/tests/conftest.py. See CLAUDE.md §10.3.

Also scrubs POLI_PAGE_* env vars before each unit test so the workspace
.env (loaded by tests/conftest.py for the integration suite) does not
leak into unit-level assertions.
"""

from __future__ import annotations

import asyncio
import os
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
def isolate_poli_page_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip POLI_PAGE_* env vars so each unit test starts from a clean slate."""
    for key in [k for k in os.environ if k.startswith("POLI_PAGE_")]:
        monkeypatch.delenv(key, raising=False)


@pytest.fixture(autouse=True)
def check_no_pending_tasks() -> Iterator[None]:
    """Assert no orphan asyncio tasks survive a test using a running loop."""
    yield
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    leftover = [t for t in asyncio.all_tasks(loop) if not t.done()]
    try:
        current = asyncio.current_task(loop)
        leftover = [t for t in leftover if t is not current]
    except RuntimeError:
        pass
    assert not leftover, f"Pending asyncio tasks leaked: {leftover}"
