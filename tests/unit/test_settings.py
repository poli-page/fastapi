"""Tests for poli_page_fastapi.settings.PoliPageSettings."""

from __future__ import annotations

import logging

import pytest
from pydantic import ValidationError

from poli_page_fastapi.settings import PoliPageSettings
from tests.unit.keys import HEX32, LIVE_KEY, SANDBOX_KEY, key_warnings

_FORMAT = "pp_{environment}_{32 lowercase hex}"
_ENV_20 = "abcdefghijklmnopqrst"
_ENV_21 = "abcdefghijklmnopqrstu"


def _expected_warning(shown: str | None) -> str:
    subject = f"POLI_PAGE_API_KEY ({shown}…)" if shown else "POLI_PAGE_API_KEY"
    return (
        f"{subject} does not match the key format {_FORMAT}; starting anyway, "
        "the Poli Page API decides whether the key is valid."
    )


@pytest.fixture
def debug_caplog(caplog: pytest.LogCaptureFixture) -> pytest.LogCaptureFixture:
    # At the default WARNING level an INFO or DEBUG record carrying the key would be
    # dropped before the leak checks below could see it.
    caplog.set_level(logging.DEBUG)
    return caplog


def _assert_key_not_in_output(
    key: str, caplog: pytest.LogCaptureFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    captured = capsys.readouterr()
    for output in (caplog.text, captured.out, captured.err):
        assert key.strip() not in output
        assert HEX32[:8] not in output


def test_minimal_valid_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POLI_PAGE_API_KEY", SANDBOX_KEY)
    settings = PoliPageSettings()
    assert settings.api_key == SANDBOX_KEY
    assert settings.base_url is None
    assert settings.timeout is None
    assert settings.max_retries is None
    assert settings.retry_delay is None


def test_missing_api_key_yields_none(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.delenv("POLI_PAGE_API_KEY", raising=False)
    settings = PoliPageSettings()
    assert settings.api_key is None
    assert key_warnings(caplog) == []


def test_empty_api_key_yields_none(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("POLI_PAGE_API_KEY", "")
    settings = PoliPageSettings()
    assert settings.api_key is None
    assert key_warnings(caplog) == []


@pytest.mark.parametrize(
    "key",
    [
        SANDBOX_KEY,
        LIVE_KEY,
        f"pp_eu-prod_{HEX32}",
        f"pp_staging_{HEX32}",
        f"pp_a_{HEX32}",
        f"pp_env2_{HEX32}",
        f"pp_a-1-b_{HEX32}",
        f"pp_{_ENV_20}_{HEX32}",
    ],
)
def test_well_formed_key_loads_without_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, key: str
) -> None:
    monkeypatch.setenv("POLI_PAGE_API_KEY", key)
    settings = PoliPageSettings()
    assert settings.api_key == key
    assert key_warnings(caplog) == []


@pytest.mark.parametrize(
    ("key", "shown"),
    [
        # Bad secret: the pp_{environment}_ part is shown, the rest never is.
        ("pp_sandbox_x", "pp_sandbox_"),
        (f"pp_sandbox_{HEX32[:31]}", "pp_sandbox_"),
        (f"pp_sandbox_{HEX32}f", "pp_sandbox_"),
        ("pp_sandbox_0123456789ABCDEF0123456789abcdef", "pp_sandbox_"),
        (f"pp_sandbox_{HEX32}\n", "pp_sandbox_"),
        (f"pp_{_ENV_20}_x", f"pp_{_ENV_20}_"),
        # Bad environment name: nothing of the key is shown.
        (f"pp_Sandbox_{HEX32}", None),
        (f"pp_2fa_{HEX32}", None),
        (f"pp_a--b_{HEX32}", None),
        (f"pp_sandbox-_{HEX32}", None),
        (f"pp__{HEX32}", None),
        (f"pp_{_ENV_21}_{HEX32}", None),
        (f"pp_{_ENV_21}_x", None),
        # Not a pp_ key, or something before pp_.
        (f"sk_live_{HEX32}", None),
        ("abc", None),
        (f"xpp_sandbox_{HEX32}", None),
        (f" pp_sandbox_{HEX32}", None),
    ],
)
def test_malformed_key_loads_with_one_warning_without_the_secret(
    monkeypatch: pytest.MonkeyPatch,
    debug_caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
    key: str,
    shown: str | None,
) -> None:
    monkeypatch.setenv("POLI_PAGE_API_KEY", key)
    settings = PoliPageSettings()
    assert settings.api_key == key
    assert key_warnings(debug_caplog) == [_expected_warning(shown)]
    _assert_key_not_in_output(key, debug_caplog, capsys)


def test_malformed_key_passed_as_kwarg_warns_once(caplog: pytest.LogCaptureFixture) -> None:
    settings = PoliPageSettings(api_key="pp_sandbox_x")
    assert settings.api_key == "pp_sandbox_x"
    assert key_warnings(caplog) == [_expected_warning("pp_sandbox_")]


@pytest.mark.parametrize("explicit", [None, ""])
@pytest.mark.parametrize(
    ("env_key", "shown"),
    [
        ("pp_sandbox_x", "pp_sandbox_"),
        # The SDK sends the env value as is, so surrounding whitespace is not stripped.
        (f" {SANDBOX_KEY} ", None),
    ],
)
def test_explicit_empty_key_checks_the_env_key_the_sdk_falls_back_to(
    monkeypatch: pytest.MonkeyPatch,
    debug_caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
    explicit: str | None,
    env_key: str,
    shown: str | None,
) -> None:
    # The client gets no api_key, so the SDK reads POLI_PAGE_API_KEY itself.
    monkeypatch.setenv("POLI_PAGE_API_KEY", env_key)
    settings = PoliPageSettings(api_key=explicit)
    assert settings.api_key is None
    assert key_warnings(debug_caplog) == [_expected_warning(shown)]
    _assert_key_not_in_output(env_key, debug_caplog, capsys)


@pytest.mark.parametrize("env_key", [None, "", SANDBOX_KEY])
def test_explicit_empty_key_with_no_or_well_formed_env_key_does_not_warn(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, env_key: str | None
) -> None:
    if env_key is None:
        monkeypatch.delenv("POLI_PAGE_API_KEY", raising=False)
    else:
        monkeypatch.setenv("POLI_PAGE_API_KEY", env_key)
    assert PoliPageSettings(api_key=None).api_key is None
    assert key_warnings(caplog) == []


def test_explicit_key_wins_over_a_malformed_env_key(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    # The SDK ignores the env var when it is given a key, so only that key is checked.
    monkeypatch.setenv("POLI_PAGE_API_KEY", "pp_sandbox_x")
    assert PoliPageSettings(api_key=SANDBOX_KEY).api_key == SANDBOX_KEY
    assert key_warnings(caplog) == []


def test_base_url_read(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POLI_PAGE_API_KEY", SANDBOX_KEY)
    monkeypatch.setenv("POLI_PAGE_BASE_URL", "https://api.example.com")
    settings = PoliPageSettings()
    assert settings.base_url == "https://api.example.com"


@pytest.mark.parametrize("bad_timeout", [0, -1, 601, 1000])
def test_timeout_out_of_range_raises(monkeypatch: pytest.MonkeyPatch, bad_timeout: float) -> None:
    monkeypatch.setenv("POLI_PAGE_API_KEY", SANDBOX_KEY)
    monkeypatch.setenv("POLI_PAGE_TIMEOUT", str(bad_timeout))
    with pytest.raises(ValidationError, match="TIMEOUT"):
        PoliPageSettings()


@pytest.mark.parametrize("bad_retries", [-1, 11, 100])
def test_max_retries_out_of_range_raises(monkeypatch: pytest.MonkeyPatch, bad_retries: int) -> None:
    monkeypatch.setenv("POLI_PAGE_API_KEY", SANDBOX_KEY)
    monkeypatch.setenv("POLI_PAGE_MAX_RETRIES", str(bad_retries))
    with pytest.raises(ValidationError, match="MAX_RETRIES"):
        PoliPageSettings()


@pytest.mark.parametrize("bad_delay", [-0.1, 31, 100])
def test_retry_delay_out_of_range_raises(monkeypatch: pytest.MonkeyPatch, bad_delay: float) -> None:
    monkeypatch.setenv("POLI_PAGE_API_KEY", SANDBOX_KEY)
    monkeypatch.setenv("POLI_PAGE_RETRY_DELAY", str(bad_delay))
    with pytest.raises(ValidationError, match="RETRY_DELAY"):
        PoliPageSettings()


def test_all_options_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POLI_PAGE_API_KEY", SANDBOX_KEY)
    monkeypatch.setenv("POLI_PAGE_BASE_URL", "https://api.example.com")
    monkeypatch.setenv("POLI_PAGE_TIMEOUT", "45")
    monkeypatch.setenv("POLI_PAGE_MAX_RETRIES", "5")
    monkeypatch.setenv("POLI_PAGE_RETRY_DELAY", "0.25")
    settings = PoliPageSettings()
    assert settings.api_key == SANDBOX_KEY
    assert settings.base_url == "https://api.example.com"
    assert settings.timeout == 45.0
    assert settings.max_retries == 5
    assert settings.retry_delay == 0.25
