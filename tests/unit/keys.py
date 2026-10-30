"""API keys and key-warning helpers shared by the unit tests."""

from __future__ import annotations

import logging

import pytest

HEX32 = "0123456789abcdef0123456789abcdef"
SANDBOX_KEY = f"pp_sandbox_{HEX32}"
LIVE_KEY = f"pp_live_{HEX32}"

SETTINGS_LOGGER = "poli_page_fastapi.settings"


def key_warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    """Messages of the WARNING records logged by PoliPageSettings."""
    return [
        r.getMessage()
        for r in caplog.records
        if r.name == SETTINGS_LOGGER and r.levelno == logging.WARNING
    ]
