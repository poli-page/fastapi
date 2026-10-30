"""The example app against the Poli Page API contract (https://github.com/poli-page/api-contract).

CI copies the pinned `contract.json` with the `poli-page/api-contract` action and sets
`POLI_CONTRACT` to its path. Each `kind: "impl"` case runs against this example app:

- a local HTTP server on 127.0.0.1 answers the case's `responses` in order and records each
  request;
- the app's SDK is pointed at it through the integration's own settings
  (`POLI_PAGE_BASE_URL`, with a sandbox test key in `POLI_PAGE_API_KEY`), read by
  `PoliPageSettings` when the app's lifespan builds the client;
- the case's `request` goes through FastAPI's `TestClient` (lifespan on, redirects not
  followed), and the app's answer (status, `Location`, media type, JSON body) and the
  SDK's recorded requests are compared with `expect`.

The SDK keeps its default retry settings: the cases count its attempts. `kind: "sdk"` cases
are the SDK's own and are ignored here. The answer's JSON is the error handler's
`to_payload()` body, compared as is: no `policy.normalizations` entry applies to it.

`contract-skip.json` maps the case ids allowed to fail to the reason. A listed case that
passes, or a listed id that is not an `impl` case of the contract, fails the run.

Locally, from `example-app/`: `POLI_CONTRACT=/path/to/contract.json uv run pytest`. Without
it the module is skipped, except in CI, where a missing contract is an error.
"""

from __future__ import annotations

import base64
import contextlib
import email.utils
import json
import os
import re
import socket
import threading
import time
from collections.abc import Mapping, Sequence
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from main import app

from poli_page_fastapi import get_poli_page_client

KNOWN_FORMAT_VERSION = 1

#: The app's key in every case: a well-formed sandbox key (`pp_sandbox_` + 32 hex).
TEST_API_KEY = "pp_sandbox_0123456789abcdef0123456789abcdef"

SKIP_LIST_PATH = Path(__file__).with_name("contract-skip.json")


class ContractError(Exception):
    """The contract file, or the skip list, is not something this test can run."""


def _load_contract(path: str) -> dict[str, Any]:
    try:
        parsed: object = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ContractError(f"POLI_CONTRACT={path} cannot be read as JSON: {exc}") from exc
    if not isinstance(parsed, dict) or "formatVersion" not in parsed:
        raise ContractError(f"{path} is not a contract.json: it has no formatVersion")
    contract = cast(dict[str, Any], parsed)
    if contract["formatVersion"] != KNOWN_FORMAT_VERSION:
        raise ContractError(
            f"contract.json formatVersion {contract['formatVersion']!r} is not supported "
            f"(this test reads format {KNOWN_FORMAT_VERSION}): update tests/test_contract.py"
        )
    return contract


def _load_skip_list() -> dict[str, str]:
    parsed: object = json.loads(SKIP_LIST_PATH.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise ContractError("tests/contract-skip.json must be an object of case id to reason")
    skip: dict[str, str] = {}
    for case_id, reason in cast(dict[str, object], parsed).items():
        if not isinstance(reason, str) or not reason.strip():
            raise ContractError(f'tests/contract-skip.json: "{case_id}" needs a reason')
        skip[case_id] = reason
    return skip


# ---------------------------------------------------------------------------
# Placeholders: {{mock}}, {{httpDate+N}}
# ---------------------------------------------------------------------------

_PLACEHOLDER = re.compile(r"\{\{([^}]*)\}\}")
_HTTP_DATE = re.compile(r"^httpDate\+(\d+)$")


def _substitute(value: Any, mock: str) -> Any:
    if isinstance(value, str):

        def replace(match: re.Match[str]) -> str:
            name = match.group(1)
            if name == "mock":
                return mock
            date = _HTTP_DATE.match(name)
            if date:
                # An HTTP-date has whole seconds: round to the nearest one.
                return email.utils.formatdate(round(time.time() + int(date.group(1))), usegmt=True)
            raise ContractError(f"Unknown contract placeholder {{{{{name}}}}}")

        return _PLACEHOLDER.sub(replace, value)
    if isinstance(value, list):
        return [_substitute(item, mock) for item in value]
    if isinstance(value, dict):
        return {key: _substitute(item, mock) for key, item in cast(dict[str, Any], value).items()}
    return value


# ---------------------------------------------------------------------------
# Mock API server
# ---------------------------------------------------------------------------


class RecordedRequest:
    __slots__ = ("headers", "method", "path")

    def __init__(self, method: str, path: str, headers: Mapping[str, str]) -> None:
        self.method = method
        self.path = path
        #: Lowercased header names.
        self.headers = headers


class MockServer:
    """Answers the case's `responses` in order on 127.0.0.1 and records every request."""

    def __init__(self, steps: Sequence[Mapping[str, Any]]) -> None:
        self.steps = steps
        self.requests: list[RecordedRequest] = []
        #: Errors raised while answering (a bad case step); `_run_case` re-raises the first.
        self.errors: list[Exception] = []
        self._lock = threading.Lock()
        self._release = threading.Event()
        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), self._handler_class())
        self._httpd.daemon_threads = True
        port = self._httpd.server_address[1]
        self.origin = f"http://127.0.0.1:{port}"
        # A short poll interval keeps `shutdown()` quick: it waits for the next poll.
        self._thread = threading.Thread(
            target=self._httpd.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
        )
        self._thread.start()

    def close(self) -> None:
        self._release.set()  # ends every `hang`
        self._httpd.shutdown()
        self._httpd.server_close()
        self._thread.join()

    def _record(self, request: RecordedRequest) -> Mapping[str, Any] | None:
        with self._lock:
            self.requests.append(request)
            index = len(self.requests) - 1
        return self.steps[index] if index < len(self.steps) else None

    def _handler_class(self) -> type[BaseHTTPRequestHandler]:
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: Any) -> None:
                pass

            def _handle(self) -> None:
                try:
                    self._handle_step()
                except Exception as exc:
                    server.errors.append(exc)
                    self.close_connection = True

            def _handle_step(self) -> None:
                length = int(self.headers.get("Content-Length") or 0)
                if length:
                    self.rfile.read(length)
                headers = {name.lower(): value for name, value in self.headers.items()}
                step = server._record(RecordedRequest(self.command, self.path, headers))
                if step is None:
                    # More requests than the case has answers: make it visible in the diff.
                    self._answer({"status": 599, "json": {"error": "MOCK_EXHAUSTED"}})
                elif step.get("fault") == "drop":
                    self.close_connection = True
                    with contextlib.suppress(OSError):
                        self.connection.shutdown(socket.SHUT_RDWR)
                elif step.get("fault") == "hang":
                    server._release.wait()
                    self.close_connection = True
                elif "fault" in step:
                    raise ContractError(f"Unknown fault {step['fault']!r}")
                else:
                    self._answer(step)

            def _answer(self, step: Mapping[str, Any]) -> None:
                headers = cast(dict[str, str], _substitute(step.get("headers", {}), server.origin))
                has_type = any(name.lower() == "content-type" for name in headers)
                body: bytes | None = None
                if "json" in step:
                    body = json.dumps(_substitute(step["json"], server.origin)).encode()
                    if not has_type:
                        headers["Content-Type"] = "application/json"
                elif "text" in step:
                    body = cast(str, step["text"]).encode()
                elif "base64" in step:
                    body = base64.b64decode(cast(str, step["base64"]))
                self.send_response(cast(int, step["status"]))
                for name, value in headers.items():
                    self.send_header(name, value)
                if body is not None:
                    self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if body is not None:
                    self.wfile.write(body)

            do_GET = _handle
            do_POST = _handle
            do_DELETE = _handle

        return Handler


# ---------------------------------------------------------------------------
# Comparing one case
# ---------------------------------------------------------------------------

_UUID_V4 = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")


def _describe_requests(recorded: Sequence[RecordedRequest]) -> list[dict[str, str]]:
    """The recorded requests in the shape of `expect.requests`.

    A field that breaks the expectation keeps the observed value, so the diff shows it.
    """
    first_key: str | None = None
    out: list[dict[str, str]] = []
    for req in recorded:
        authorization = req.headers.get("authorization")
        if authorization is None:
            auth = "none"
        elif authorization == f"Bearer {TEST_API_KEY}":
            auth = "bearer"
        else:
            auth = f"unexpected Authorization: {authorization}"
        key = req.headers.get("idempotency-key")
        if key is None:
            idempotency_key = "absent"
        elif not _UUID_V4.match(key):
            idempotency_key = f"not a lowercase UUID v4: {key}"
        else:
            first_key = first_key or key
            idempotency_key = "stable" if key == first_key else f"changed: {first_key} then {key}"
        out.append(
            {
                "method": req.method,
                "path": req.path,
                "auth": auth,
                "idempotencyKey": idempotency_key,
            }
        )
    return out


def _media_type(content_type: str | None) -> str | None:
    """The media type of a Content-Type, without parameters such as charset."""
    if content_type is None:
        return None
    return content_type.split(";", 1)[0].strip().lower()


def _run_case(case: Mapping[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    _substitute(case, "http://127.0.0.1")  # an unknown placeholder fails before any request
    server = MockServer(cast(list[Mapping[str, Any]], case["responses"]))
    try:
        request = cast(Mapping[str, Any], _substitute(case["request"], server.origin))
        # Only the key and the base URL: every other option keeps the SDK default.
        for name in [n for n in os.environ if n.upper().startswith("POLI_PAGE_")]:
            monkeypatch.delenv(name)
        monkeypatch.setenv("POLI_PAGE_API_KEY", TEST_API_KEY)
        monkeypatch.setenv("POLI_PAGE_BASE_URL", server.origin)
        get_poli_page_client.cache_clear()
        # The `with` block runs the app's lifespan, which builds the client from the env.
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.request(
                cast(str, request["method"]), cast(str, request["path"]), follow_redirects=False
            )
    finally:
        server.close()
        get_poli_page_client.cache_clear()
    if server.errors:
        raise server.errors[0]

    expect = cast(dict[str, Any], _substitute(case["expect"], server.origin))
    actual: dict[str, Any] = {"status": response.status_code}
    if "location" in expect:
        actual["location"] = response.headers.get("location")
    if "contentType" in expect:
        actual["contentType"] = _media_type(response.headers.get("content-type"))
    if "json" in expect:
        try:
            actual["json"] = response.json()
        except ValueError:
            actual["json"] = f"body is not JSON: {response.content[:200]!r}"
    if "requests" in expect:
        actual["requests"] = _describe_requests(server.requests)
    assert actual == expect


# ---------------------------------------------------------------------------
# Suite
# ---------------------------------------------------------------------------

_CONTRACT_PATH = os.environ.get("POLI_CONTRACT")

if not _CONTRACT_PATH:
    if os.environ.get("CI"):

        def test_poli_contract_is_set() -> None:
            pytest.fail(
                'POLI_CONTRACT is not set: in CI the "API contract" step must provide '
                "contract.json (poli-page/api-contract action, output `path`)"
            )

    else:
        pytest.skip(
            "API contract: set POLI_CONTRACT to a contract.json path to run it",
            allow_module_level=True,
        )

else:
    CONTRACT = _load_contract(_CONTRACT_PATH)
    SKIP = _load_skip_list()
    ALL_CASES = cast(list[dict[str, Any]], CONTRACT["cases"])
    IMPL_CASES = [c for c in ALL_CASES if c.get("kind") == "impl"]

    def test_contract_has_impl_cases_and_known_kinds() -> None:
        assert IMPL_CASES, 'the contract has no kind "impl" case'
        unknown = [c.get("kind") for c in ALL_CASES if c.get("kind") not in ("sdk", "impl")]
        assert unknown == [], 'case kinds other than "sdk" and "impl"'

    def test_skip_list_names_only_impl_cases() -> None:
        unknown = sorted(set(SKIP) - {c["id"] for c in IMPL_CASES})
        assert unknown == [], "not impl cases of the contract: remove them from contract-skip.json"

    @pytest.mark.parametrize("case", [pytest.param(c, id=c["id"]) for c in IMPL_CASES])
    def test_case(case: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
        reason = SKIP.get(case["id"])
        if reason is None:
            _run_case(case, monkeypatch)
            return
        try:
            _run_case(case, monkeypatch)
        except AssertionError:
            pytest.xfail(f"listed in tests/contract-skip.json: {reason}")
        pytest.fail(f"{case['id']} passes now: remove it from tests/contract-skip.json")
