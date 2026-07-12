#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any, Sequence


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Run LiteRT-LM's OpenAI API with a forced CPU backend.")
    root.add_argument("--host", default="127.0.0.1")
    root.add_argument("--port", type=int, default=9379)
    root.add_argument("--cpu-threads", type=int, default=2)
    root.add_argument("--backend", choices=("cpu", "gpu"), default="cpu")
    root.add_argument("--max-context-tokens", type=int, default=2048)
    root.add_argument("--speculative-decoding", action="store_true")
    return root


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.cpu_threads < 1 or args.max_context_tokens < 1:
        raise SystemExit("CPU threads and context tokens must be positive.")

    import litert_lm
    from litert_lm_cli import model
    from litert_lm_cli.commands import openai_handler, serve, serve_util

    def cpu_engine(server: Any, *, model_id: str):
        selected = model.Model.from_model_id(model_id)
        if not selected.exists():
            raise FileNotFoundError(f"Model {model_id} not found")
        backend = model.parse_backend(
            args.backend,
            model_obj=selected,
            cpu_thread_count=args.cpu_threads,
        )
        print(
            f"Loading model={model_id} backend={args.backend} threads={args.cpu_threads} "
            f"context={args.max_context_tokens}",
            flush=True,
        )
        if server.litert_lm_engine is not None:
            if (
                server.model_id == model_id
                and server.backend == backend
                and server.max_num_tokens == args.max_context_tokens
            ):
                return server.litert_lm_engine
            server.litert_lm_engine.__exit__(None, None, None)
            server.litert_lm_engine = None

        engine = litert_lm.Engine(
            selected.model_path,
            backend=backend,
            max_num_tokens=args.max_context_tokens,
            enable_speculative_decoding=args.speculative_decoding,
        )
        engine.__enter__()
        server.litert_lm_engine = engine
        server.model_id = model_id
        server.backend = backend
        server.max_num_tokens = args.max_context_tokens
        server.vision_backend = None
        server.audio_backend = None
        return engine

    serve_util.get_or_initialize_server_engine = cpu_engine
    print(
        f"Forced LiteRT-LM backend={args.backend} threads={args.cpu_threads} "
        f"context={args.max_context_tokens} speculative={args.speculative_decoding}",
        flush=True,
    )
    serve.run_server(args.host, args.port, openai_handler.OpenAIHandler, "OpenAI CPU", ())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
