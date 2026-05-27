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
    mock_cls.assert_called_once_with(api_key="pp_test_x")


def test_poli_page_dependency_with_explicit_client() -> None:
    mock_client = MagicMock()
    dep = PoliPageDependency(client=mock_client)
    assert dep() is mock_client


def test_poli_page_dependency_with_settings(mocker: MockerFixture) -> None:
    settings = PoliPageSettings(api_key="pp_test_y", timeout=30)
    mock_cls = mocker.patch("poli_page_fastapi.dependencies.PoliPage")
    mock_cls.return_value = MagicMock()
    dep = PoliPageDependency(settings=settings)
    client_a = dep()
    client_b = dep()
    assert client_a is client_b
    mock_cls.assert_called_once_with(api_key="pp_test_y", timeout=30.0)


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
    monkeypatch.setenv("POLI_PAGE_API_KEY", "pp_test_global")
    mock_cls = mocker.patch("poli_page_fastapi.dependencies.PoliPage")
    get_poli_page_client()

    settings = PoliPageSettings(api_key="pp_test_other")
    dep = PoliPageDependency(settings=settings)
    dep()
    assert mock_cls.call_count == 2
