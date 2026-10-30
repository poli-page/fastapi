"""Tests for poli_page_fastapi.exceptions.poli_page_exception_handler."""

from __future__ import annotations

import json
from typing import Any, cast

import pytest
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
from starlette.requests import Request
from starlette.responses import JSONResponse

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
    return cast(dict[str, Any], json.loads(bytes(resp.body)))


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
    assert body == {
        "code": "TEST_CODE",
        "message": "failure",
        "status": status,
        "requestId": "req_abc",
    }


def test_api_connection_error_maps_to_503() -> None:
    exc = APIConnectionError("connection refused", code="network_error")
    resp = poli_page_exception_handler(_fake_request(), exc)
    assert resp.status_code == 503
    body = _body(resp)
    assert body == {
        "code": "network_error",
        "message": "connection refused",
        "status": 503,
        "requestId": None,
    }


def test_api_timeout_error_maps_to_504() -> None:
    exc = APITimeoutError("deadline exceeded", code="timeout")
    resp = poli_page_exception_handler(_fake_request(), exc)
    assert resp.status_code == 504
    body = _body(resp)
    assert body == {
        "code": "timeout",
        "message": "deadline exceeded",
        "status": 504,
        "requestId": None,
    }


def test_error_without_status_answers_500_with_null_status() -> None:
    exc = PoliPageError("apiKey is required", code="invalid_options")
    resp = poli_page_exception_handler(_fake_request(), exc)
    assert resp.status_code == 500
    body = _body(resp)
    # The body is to_payload() as is: its status stays null.
    assert body == {
        "code": "invalid_options",
        "message": "apiKey is required",
        "status": None,
        "requestId": None,
    }


@pytest.mark.parametrize(
    "exc",
    [
        NotFoundError("missing", code="TEMPLATE_NOT_FOUND", status=404, request_id="req_1"),
        APIConnectionError("Network request failed", code="network_error"),
        APITimeoutError("Request timed out after 60000ms", code="timeout"),
        PoliPageError("apiKey is required", code="invalid_options"),
    ],
    ids=["api", "network_error", "timeout", "no-status"],
)
def test_body_is_exactly_to_payload(exc: PoliPageError) -> None:
    resp = poli_page_exception_handler(_fake_request(), exc)
    assert _body(resp) == exc.to_payload()
    assert resp.headers["content-type"] == "application/json"


def test_non_poli_page_error_is_reraised() -> None:
    exc = ValueError("not a poli page error")
    with pytest.raises(ValueError, match="not a poli page error"):
        poli_page_exception_handler(_fake_request(), exc)


def test_response_has_no_store_cache_header() -> None:
    exc = BadRequestError("x", code="X", status=400)
    resp = poli_page_exception_handler(_fake_request(), exc)
    assert resp.headers["cache-control"] == "no-store, private"


def test_request_id_is_camel_case_on_wire() -> None:
    exc = BadRequestError("x", code="X", status=400)
    resp = poli_page_exception_handler(_fake_request(), exc)
    body = _body(resp)
    assert "request_id" not in body
    assert body["requestId"] is None
