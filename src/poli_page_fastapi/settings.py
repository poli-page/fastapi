"""Pydantic-settings reader for POLI_PAGE_* env vars."""

from __future__ import annotations

import logging
import os
import re

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# pp_{environment}_{32 lowercase hex}, the SDK contract's full-key format. It only
# drives a startup warning: the API is the authority on keys, so a mismatch never
# stops the client.
_ENVIRONMENT_PREFIX = r"pp_(?=[a-z][a-z0-9-]{0,19}_)[a-z][a-z0-9]*(?:-[a-z0-9]+)*_"
_ENVIRONMENT_PREFIX_RE = re.compile(_ENVIRONMENT_PREFIX)
_API_KEY_RE = re.compile(_ENVIRONMENT_PREFIX + r"[0-9a-f]{32}")


def _warn_if_malformed(key: str) -> None:
    if not _API_KEY_RE.fullmatch(key):
        # Only the pp_{environment}_ part may reach the log, never the secret.
        shown = _ENVIRONMENT_PREFIX_RE.match(key)
        logger.warning(
            "POLI_PAGE_API_KEY%s does not match the key format "
            "pp_{environment}_{32 lowercase hex}; starting anyway, "
            "the Poli Page API decides whether the key is valid.",
            f" ({shown.group()}…)" if shown else "",
        )


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
        populate_by_name=True,
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
        _warn_if_malformed(v)
        return v

    @model_validator(mode="after")
    def _validate_env_fallback_key(self) -> PoliPageSettings:
        # With no api_key (e.g. an explicit None or "" that overrides the env var),
        # the client is built without one and the SDK reads POLI_PAGE_API_KEY itself.
        if self.api_key is None:
            env_key = os.environ.get("POLI_PAGE_API_KEY")
            if env_key:
                _warn_if_malformed(env_key)
        return self

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
