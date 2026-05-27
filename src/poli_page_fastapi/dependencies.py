"""FastAPI dependency factory and class for the Poli Page SDK client."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from poli_page import PoliPage

from poli_page_fastapi.settings import PoliPageSettings


def _settings_to_kwargs(settings: PoliPageSettings) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
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
    from the global memo. Each instance memoises its own client.
    """

    def __init__(
        self,
        *,
        settings: PoliPageSettings | None = None,
        client: PoliPage | None = None,
    ) -> None:
        self._settings = settings
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
