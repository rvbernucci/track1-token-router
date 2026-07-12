#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute a command in an existing AMD Jupyter terminal.")
    parser.add_argument("command")
    parser.add_argument("--base-url", default=os.getenv("AMD_JUPYTER_BASE_URL"))
    parser.add_argument("--terminal", default=os.getenv("AMD_JUPYTER_TERMINAL", "1"))
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()
    token = os.getenv("AMD_JUPYTER_TOKEN")
    if not args.base_url or not token:
        raise SystemExit("AMD_JUPYTER_BASE_URL and AMD_JUPYTER_TOKEN are required")

    try:
        import websocket
    except ImportError as exc:
        raise SystemExit("Install websocket-client in an isolated environment") from exc

    nonce = time.time_ns()
    start_marker = f"__CODEX_COMMAND_START_{nonce}__"
    marker = f"__CODEX_COMMAND_DONE_{nonce}__"
    command = f"printf '{start_marker}\\n'\n{args.command}\nprintf '{marker}:%s\\n' $?\n"
    base = args.base_url.rstrip("/")
    ws_base = base.replace("https://", "wss://", 1).replace("http://", "ws://", 1)
    origin = base.split("/instances/", 1)[0]
    url = f"{ws_base}/terminals/websocket/{args.terminal}?token={token}"
    connection = websocket.create_connection(url, origin=origin, timeout=min(args.timeout, 30.0))
    connection.send(json.dumps(["stdin", command]))
    deadline = time.monotonic() + args.timeout
    exit_code: int | None = None
    started = False
    try:
        while time.monotonic() < deadline:
            connection.settimeout(max(0.1, min(5.0, deadline - time.monotonic())))
            try:
                message = json.loads(connection.recv())
            except TimeoutError:
                continue
            if not isinstance(message, list) or len(message) < 2 or message[0] != "stdout":
                continue
            text = str(message[1])
            if not started:
                if start_marker not in text:
                    continue
                _, _, text = text.partition(start_marker)
                text = text.lstrip("\r\n")
                started = True
            if marker in text:
                before, _, suffix = text.partition(marker + ":")
                sys.stdout.write(before)
                try:
                    exit_code = int(suffix.splitlines()[0])
                except (ValueError, IndexError):
                    exit_code = 1
                break
            sys.stdout.write(text)
            sys.stdout.flush()
    finally:
        connection.close()
    if exit_code is None:
        raise SystemExit(f"command timed out after {args.timeout:.1f}s")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
