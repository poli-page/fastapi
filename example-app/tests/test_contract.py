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

import json
import os
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from main import app
from mock_api import ContractError, MockServer, RecordedRequest, substitute

from poli_page_fastapi import get_poli_page_client

KNOWN_FORMAT_VERSION = 1

#: The app's key in every case: a well-formed sandbox key (`pp_sandbox_` + 32 hex).
TEST_API_KEY = "pp_sandbox_0123456789abcdef0123456789abcdef"

SKIP_LIST_PATH = Path(__file__).with_name("contract-skip.json")


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
    substitute(case, "http://127.0.0.1")  # an unknown placeholder fails before any request
    server = MockServer(cast(list[Mapping[str, Any]], case["responses"]))
    try:
        request = cast(Mapping[str, Any], substitute(case["request"], server.origin))
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

    expect = cast(dict[str, Any], substitute(case["expect"], server.origin))
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
