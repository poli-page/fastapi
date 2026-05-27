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
