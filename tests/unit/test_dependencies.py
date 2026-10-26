"""Tests for poli_page_fastapi.dependencies."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest
from poli_page import PoliPage, PoliPageError
from pytest_mock import MockerFixture

from poli_page_fastapi.dependencies import PoliPageDependency, get_poli_page_client
from poli_page_fastapi.settings import PoliPageSettings
from tests.unit.keys import LIVE_KEY, SANDBOX_KEY


@pytest.fixture(autouse=True)
def _clear_factory_cache() -> None:
    """Reset the lru_cache between tests so each test sees a fresh factory."""
    get_poli_page_client.cache_clear()


def test_get_poli_page_client_builds_with_env(
    monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
) -> None:
    monkeypatch.setenv("POLI_PAGE_API_KEY", SANDBOX_KEY)
    monkeypatch.setenv("POLI_PAGE_TIMEOUT", "42")
    mock_cls = mocker.patch("poli_page_fastapi.dependencies.PoliPage")
    get_poli_page_client()
    mock_cls.assert_called_once_with(api_key=SANDBOX_KEY, timeout=42.0)


def test_get_poli_page_client_memoises(
    monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
) -> None:
    monkeypatch.setenv("POLI_PAGE_API_KEY", SANDBOX_KEY)
    mock_cls = mocker.patch("poli_page_fastapi.dependencies.PoliPage")
    a = get_poli_page_client()
    b = get_poli_page_client()
    assert a is b
    assert mock_cls.call_count == 1


def test_get_poli_page_client_omits_unset_kwargs(
    monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
) -> None:
    monkeypatch.setenv("POLI_PAGE_API_KEY", SANDBOX_KEY)
    monkeypatch.delenv("POLI_PAGE_TIMEOUT", raising=False)
    monkeypatch.delenv("POLI_PAGE_BASE_URL", raising=False)
    mock_cls = mocker.patch("poli_page_fastapi.dependencies.PoliPage")
    get_poli_page_client()
    mock_cls.assert_called_once_with(api_key=SANDBOX_KEY)


def test_poli_page_dependency_with_explicit_client() -> None:
    mock_client = MagicMock()
    dep = PoliPageDependency(client=mock_client)
    assert dep() is mock_client


def test_poli_page_dependency_with_settings(mocker: MockerFixture) -> None:
    settings = PoliPageSettings(api_key=SANDBOX_KEY, timeout=30)
    mock_cls = mocker.patch("poli_page_fastapi.dependencies.PoliPage")
    mock_cls.return_value = MagicMock()
    dep = PoliPageDependency(settings=settings)
    client_a = dep()
    client_b = dep()
    assert client_a is client_b
    mock_cls.assert_called_once_with(api_key=SANDBOX_KEY, timeout=30.0)


def test_poli_page_dependency_close_calls_sdk_close() -> None:
    mock_client = MagicMock()
    dep = PoliPageDependency(client=mock_client)
    dep()
    dep.close()
    mock_client.close.assert_called_once()
    assert dep._cached_client is None


def test_poli_page_dependency_independent_from_global(
    monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
) -> None:
    monkeypatch.setenv("POLI_PAGE_API_KEY", SANDBOX_KEY)
    mock_cls = mocker.patch("poli_page_fastapi.dependencies.PoliPage")
    get_poli_page_client()

    settings = PoliPageSettings(api_key=LIVE_KEY)
    dep = PoliPageDependency(settings=settings)
    dep()
    assert mock_cls.call_count == 2


def _settings_warnings(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [
        r
        for r in caplog.records
        if r.name == "poli_page_fastapi.settings" and r.levelno == logging.WARNING
    ]


@pytest.mark.parametrize("value", [None, ""])
def test_get_poli_page_client_without_key_raises(
    monkeypatch: pytest.MonkeyPatch, value: str | None
) -> None:
    if value is None:
        monkeypatch.delenv("POLI_PAGE_API_KEY", raising=False)
    else:
        monkeypatch.setenv("POLI_PAGE_API_KEY", value)
    with pytest.raises(PoliPageError, match="api_key is required"):
        get_poli_page_client()


def test_get_poli_page_client_starts_with_malformed_key(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("POLI_PAGE_API_KEY", "pp_sandbox_not-a-real-secret")
    client = get_poli_page_client()
    try:
        assert isinstance(client, PoliPage)
        assert get_poli_page_client() is client
    finally:
        client.close()
    warnings = _settings_warnings(caplog)
    assert len(warnings) == 1
    assert "not-a-real-secret" not in warnings[0].getMessage()


def test_poli_page_dependency_starts_with_malformed_key(caplog: pytest.LogCaptureFixture) -> None:
    dep = PoliPageDependency(settings=PoliPageSettings(api_key="sk_not_a_poli_page_key"))
    client = dep()
    try:
        assert isinstance(client, PoliPage)
    finally:
        dep.close()
    warnings = _settings_warnings(caplog)
    assert len(warnings) == 1
    assert "sk_not_a_poli_page_key" not in warnings[0].getMessage()
