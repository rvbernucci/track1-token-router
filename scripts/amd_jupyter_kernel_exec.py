#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute Python in an existing Jupyter kernel.")
    parser.add_argument("code")
    parser.add_argument("--base-url", default=os.getenv("AMD_JUPYTER_BASE_URL"))
    parser.add_argument("--kernel", default=os.getenv("AMD_JUPYTER_KERNEL"))
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()
    token = os.getenv("AMD_JUPYTER_TOKEN")
    if not args.base_url or not args.kernel or not token:
        raise SystemExit("AMD_JUPYTER_BASE_URL, AMD_JUPYTER_KERNEL and AMD_JUPYTER_TOKEN are required")
    try:
        import websocket
    except ImportError as exc:
        raise SystemExit("Install websocket-client in an isolated environment") from exc

    session = uuid.uuid4().hex
    message_id = uuid.uuid4().hex
    base = args.base_url.rstrip("/")
    ws_base = base.replace("https://", "wss://", 1).replace("http://", "ws://", 1)
    origin = base.split("/instances/", 1)[0]
    url = f"{ws_base}/api/kernels/{args.kernel}/channels?token={token}"
    connection = websocket.create_connection(url, origin=origin, timeout=min(30.0, args.timeout))
    request = {
        "channel": "shell",
        "header": {
            "date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "msg_id": message_id,
            "msg_type": "execute_request",
            "session": session,
            "username": "codex",
            "version": "5.3",
        },
        "parent_header": {},
        "metadata": {},
        "content": {
            "allow_stdin": False,
            "code": args.code,
            "silent": False,
            "stop_on_error": True,
            "store_history": False,
            "user_expressions": {},
        },
        "buffers": [],
    }
    connection.send(json.dumps(request))
    deadline = time.monotonic() + args.timeout
    exit_code = 0
    try:
        while time.monotonic() < deadline:
            connection.settimeout(max(0.1, min(5.0, deadline - time.monotonic())))
            try:
                raw = connection.recv()
            except (TimeoutError, websocket.WebSocketTimeoutException):
                continue
            if not isinstance(raw, str):
                continue
            message = json.loads(raw)
            parent = message.get("parent_header") or {}
            if parent.get("msg_id") != message_id:
                continue
            message_type = (message.get("header") or {}).get("msg_type")
            content = message.get("content") or {}
            if message_type == "stream":
                sys.stdout.write(str(content.get("text", "")))
                sys.stdout.flush()
            elif message_type == "error":
                exit_code = 1
                sys.stderr.write("\n".join(str(line) for line in content.get("traceback", [])) + "\n")
            elif message_type == "execute_reply" and content.get("status") == "error":
                exit_code = 1
            elif message_type == "status" and content.get("execution_state") == "idle":
                return exit_code
    finally:
        connection.close()
    raise SystemExit(f"kernel execution timed out after {args.timeout:.1f}s")


if __name__ == "__main__":
    raise SystemExit(main())
