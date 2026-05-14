"""Workflow Integration bridge — CLI side.

Architecture (chosen in v0.2 context decision):
- CLI command launches a short-lived localhost HTTP server (`WIBridge`)
- WI plugin (running inside DaVinci Resolve's embedded CEF) polls `/inbox`
- Plugin executes via DaVinciResolveScript JS API, posts to `/result`
- CLI receives result, shuts down server, returns to caller

The flow is *request-scoped*: each `call()` spawns a server, dispatches a task,
waits for the result with a timeout, then shuts down. No long-lived daemon.
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Optional

from .errors import WIError, WIUnavailable

DEFAULT_PORT = 50420
DEFAULT_TIMEOUT = 30.0       # max seconds a single WI op may take
HANDSHAKE_TIMEOUT = 5.0      # max wait for WI to claim the task (no plugin → fast fail)


@dataclass
class _Task:
    id: str
    method: str
    params: dict[str, Any]

    def to_payload(self) -> dict[str, Any]:
        return {"id": self.id, "method": self.method, "params": self.params}


class _Inbox:
    """Thread-safe single-task queue with done-event signalling."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._task: Optional[_Task] = None
        self._claimed: bool = False
        self._claimed_event = threading.Event()
        self._result: Optional[dict[str, Any]] = None
        self._result_event = threading.Event()

    def submit(self, task: _Task) -> None:
        with self._lock:
            self._task = task

    def take(self) -> Optional[_Task]:
        with self._lock:
            if self._task is not None and not self._claimed:
                self._claimed = True
                self._claimed_event.set()
                return self._task
        return None

    def post_result(self, task_id: str, payload: dict[str, Any]) -> bool:
        with self._lock:
            if self._task is None or self._task.id != task_id:
                return False
            self._result = payload
            self._result_event.set()
            return True

    def wait_claimed(self, timeout: float) -> bool:
        return self._claimed_event.wait(timeout=timeout)

    def wait_result(self, timeout: float) -> Optional[dict[str, Any]]:
        if self._result_event.wait(timeout=timeout):
            return self._result
        return None


def _make_handler(inbox: _Inbox):
    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
            return  # silence access log

        def _send_json(self, code: int, body: dict[str, Any]) -> None:
            data = json.dumps(body).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data)

        def _send_empty(self, code: int) -> None:
            self.send_response(code)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/ping":
                self._send_json(200, {"ok": True})
                return
            if self.path == "/inbox":
                task = inbox.take()
                if task is None:
                    self._send_empty(204)
                else:
                    self._send_json(200, task.to_payload())
                return
            self._send_empty(404)

        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/result":
                self._send_empty(404)
                return
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(length).decode("utf-8") if length else "{}"
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                self._send_json(400, {"error": "invalid json"})
                return
            task_id = payload.get("id", "")
            if inbox.post_result(task_id, payload):
                self._send_json(200, {"ok": True})
            else:
                self._send_json(409, {"error": "no matching task"})

    return _Handler


class WIBridge:
    def __init__(self, port: int = DEFAULT_PORT) -> None:
        self.port = port

    def call(
        self,
        method: str,
        params: Optional[dict[str, Any]] = None,
        *,
        handshake_timeout: float = HANDSHAKE_TIMEOUT,
        result_timeout: float = DEFAULT_TIMEOUT,
    ) -> Any:
        """Synchronously dispatch one operation to the WI plugin.

        Raises:
            WIUnavailable: plugin did not claim the task within `handshake_timeout`
            WIError: plugin returned an `error` field in its result
        """
        inbox = _Inbox()
        task = _Task(id=str(uuid.uuid4()), method=method, params=params or {})
        inbox.submit(task)

        handler_cls = _make_handler(inbox)
        try:
            server = ThreadingHTTPServer(("127.0.0.1", self.port), handler_cls)
        except OSError as exc:
            raise WIUnavailable(f"could not bind localhost:{self.port} ({exc})") from exc

        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            if not inbox.wait_claimed(timeout=handshake_timeout):
                raise WIUnavailable(
                    f"WI plugin did not poll within {handshake_timeout}s — is the plugin loaded?"
                )
            result = inbox.wait_result(timeout=result_timeout)
            if result is None:
                raise WIUnavailable(f"WI plugin claimed task but did not return within {result_timeout}s")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=1.0)

        if "error" in result:
            raise WIError(result["error"], hint=result.get("hint"))
        return result.get("result")

    def ping(self) -> bool:
        """Probe whether a WI plugin is alive *right now*. Non-blocking, cheap.

        Note: this does the same `call` flow — there is no separate ping channel
        because WI plugins only know how to poll /inbox. We use a tiny timeout.
        """
        try:
            self.call("ping", handshake_timeout=1.5, result_timeout=2.0)
            return True
        except WIUnavailable:
            return False
        except WIError:
            return True   # something answered, that's enough for liveness


def default_bridge() -> WIBridge:
    return WIBridge()
