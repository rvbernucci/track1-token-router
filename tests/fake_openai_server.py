from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


class FakeOpenAIServer:
    def __init__(
        self,
        *,
        response_text: str = "local answer",
        responses: list[str] | None = None,
        status: int = 200,
        delay_s: float = 0.0,
    ) -> None:
        self.response_text = response_text
        self.responses = list(responses or [])
        self.status = status
        self.delay_s = delay_s
        self.requests: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler_class())
        self.url = f"http://127.0.0.1:{self._server.server_port}/v1"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def __enter__(self) -> "FakeOpenAIServer":
        self._thread.start()
        return self

    def __exit__(self, *_args: object) -> None:
        self._server.shutdown()
        self._thread.join(timeout=5)

    def _handler_class(self) -> type[BaseHTTPRequestHandler]:
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8")
                payload = json.loads(body)
                outer.requests.append({"path": self.path, "payload": payload})
                if outer.delay_s:
                    time.sleep(outer.delay_s)

                if outer.status >= 400:
                    self.send_response(outer.status)
                    self.end_headers()
                    self.wfile.write(b'{"error":"forced failure"}')
                    return

                response_text = outer._next_response_text()
                response = {
                    "choices": [{"message": {"content": response_text}}],
                    "usage": {
                        "prompt_tokens": 5,
                        "completion_tokens": 2,
                        "total_tokens": 7,
                    },
                }
                encoded = json.dumps(response).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def log_message(self, _format: str, *_args: object) -> None:
                return

        return Handler

    def _next_response_text(self) -> str:
        with self._lock:
            if self.responses:
                return self.responses.pop(0)
            return self.response_text
