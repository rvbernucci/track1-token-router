from __future__ import annotations

import argparse
import json
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


SCENARIO_RESPONSES = {
    "happy": "local answer",
    "empty_or_refusal": "   ",
    "verifier-approve": json.dumps(
        {
            "decision": "approve",
            "confidence": "high",
            "reason": "fake approve",
            "failure_modes": [],
            "should_generate_alternative": False,
        }
    ),
    "verifier-escalate": json.dumps(
        {
            "decision": "escalate",
            "confidence": "medium",
            "reason": "fake escalation",
            "failure_modes": ["fake_risk"],
            "should_generate_alternative": True,
        }
    ),
    "fireworks-approve": json.dumps(
        {
            "decision": "approve",
            "answer": "",
            "reason": "fake remote approval",
        }
    ),
    "fireworks-replace": json.dumps(
        {
            "decision": "replace",
            "answer": "fake replacement",
            "reason": "fake remote replacement",
        }
    ),
    "wrong-answer": "intentionally wrong answer",
    "hallucination_confident": "Dr. Lisa Su stepped down in 2025 and Mark Papermaster is the current CEO of AMD.",
    "format_drift": '```json\n{"answer":"remote"}\n```',
    "verbose_when_strict": "The answer is 2 because the task asks for the low-risk score.",
    "wrong_math_plausible": "8",
}


@dataclass(frozen=True)
class FakeProviderConfig:
    response_text: str = "local answer"
    responses: tuple[str, ...] = ()
    status: int = 200
    delay_s: float = 0.0
    invalid_json: bool = False
    prompt_tokens: int = 5
    completion_tokens: int = 2

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class FakeOpenAIProvider:
    def __init__(
        self,
        *,
        host: str = "127.0.0.1",
        port: int = 0,
        config: FakeProviderConfig | None = None,
    ) -> None:
        self.config = config or FakeProviderConfig()
        self.requests: list[dict[str, Any]] = []
        self._responses = list(self.config.responses)
        self._lock = threading.Lock()
        self._server = ThreadingHTTPServer((host, port), self._handler_class())
        self.url = f"http://{host}:{self._server.server_port}/v1"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def __enter__(self) -> "FakeOpenAIProvider":
        self.start()
        return self

    def __exit__(self, *_args: object) -> None:
        self.stop()

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        self._thread.join(timeout=5)
        self._server.server_close()

    def serve_forever(self) -> None:
        try:
            self._server.serve_forever()
        finally:
            self._server.server_close()

    def _handler_class(self) -> type[BaseHTTPRequestHandler]:
        outer = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_GET(self) -> None:
                if self.path in {"/health", "/v1/health"}:
                    self._write_json({"status": "ok", "url": outer.url})
                    return
                self.send_response(404)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8")
                payload = json.loads(body) if body else {}
                outer.requests.append({"path": self.path, "payload": payload})

                if outer.config.delay_s:
                    time.sleep(outer.config.delay_s)

                if outer.config.status >= 400:
                    self._write_json({"error": "forced failure"}, status=outer.config.status)
                    return

                if outer.config.invalid_json:
                    self._write_raw(b"not-json", content_type="application/json")
                    return

                response_text = outer._next_response_text()
                self._write_json(
                    {
                        "choices": [{"message": {"content": response_text}}],
                        "usage": {
                            "prompt_tokens": outer.config.prompt_tokens,
                            "completion_tokens": outer.config.completion_tokens,
                            "total_tokens": outer.config.total_tokens,
                        },
                    }
                )

            def log_message(self, _format: str, *_args: object) -> None:
                return

            def _write_json(self, payload: dict[str, Any], status: int = 200) -> None:
                encoded = json.dumps(payload).encode("utf-8")
                self._write_raw(encoded, status=status, content_type="application/json")

            def _write_raw(self, body: bytes, *, status: int = 200, content_type: str = "text/plain") -> None:
                try:
                    self.send_response(status)
                    self.send_header("Content-Type", content_type)
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Connection", "close")
                    self.end_headers()
                    self.wfile.write(body)
                except BrokenPipeError:
                    return
                finally:
                    self.close_connection = True

        return Handler

    def _next_response_text(self) -> str:
        with self._lock:
            if self._responses:
                return self._responses.pop(0)
            return self.config.response_text


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a fake OpenAI-compatible provider.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--scenario", choices=sorted(SCENARIO_RESPONSES), default="happy")
    parser.add_argument("--response", help="Override response text.")
    parser.add_argument("--responses-file", type=Path, help="JSONL/text file with one response per line.")
    parser.add_argument("--status", type=int, default=200)
    parser.add_argument("--delay-s", type=float, default=0.0)
    parser.add_argument("--invalid-json", action="store_true")
    parser.add_argument("--prompt-tokens", type=int, default=5)
    parser.add_argument("--completion-tokens", type=int, default=2)
    args = parser.parse_args()

    responses = tuple(_load_responses(args.responses_file)) if args.responses_file else ()
    response_text = args.response or SCENARIO_RESPONSES[args.scenario]
    provider = FakeOpenAIProvider(
        host=args.host,
        port=args.port,
        config=FakeProviderConfig(
            response_text=response_text,
            responses=responses,
            status=args.status,
            delay_s=args.delay_s,
            invalid_json=args.invalid_json,
            prompt_tokens=args.prompt_tokens,
            completion_tokens=args.completion_tokens,
        ),
    )
    print(provider.url, flush=True)
    provider.serve_forever()
    return 0


def _load_responses(path: Path) -> list[str]:
    responses: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped:
            responses.append(stripped)
    return responses


if __name__ == "__main__":
    raise SystemExit(main())
