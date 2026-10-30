"""A local stand-in for the Poli Page API, for the example app's tests.

`MockServer` answers a list of contract-style `responses` in order on 127.0.0.1 and
records every request; `substitute` replaces the contract's placeholders.
"""

from __future__ import annotations

import base64
import contextlib
import email.utils
import json
import re
import socket
import threading
import time
from collections.abc import Mapping, Sequence
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, cast


class ContractError(Exception):
    """The contract file, or the skip list, is not something this test can run."""


# ---------------------------------------------------------------------------
# Placeholders: {{mock}}, {{httpDate+N}}
# ---------------------------------------------------------------------------

_PLACEHOLDER = re.compile(r"\{\{([^}]*)\}\}")
_HTTP_DATE = re.compile(r"^httpDate\+(\d+)$")


def substitute(value: Any, mock: str) -> Any:
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
        return [substitute(item, mock) for item in value]
    if isinstance(value, dict):
        return {key: substitute(item, mock) for key, item in cast(dict[str, Any], value).items()}
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
                headers = cast(dict[str, str], substitute(step.get("headers", {}), server.origin))
                has_type = any(name.lower() == "content-type" for name in headers)
                body: bytes | None = None
                if "json" in step:
                    body = json.dumps(substitute(step["json"], server.origin)).encode()
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
