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
