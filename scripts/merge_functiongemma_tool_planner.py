#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("configs/functiongemma-tool-planner-v1.json"))
    parser.add_argument("--adapter", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    config = json.loads(args.config.read_text())
    model_config = config["model"]
    base = AutoModelForCausalLM.from_pretrained(
        model_config["id"], revision=model_config["revision"],
        dtype=torch.bfloat16, device_map="cpu", low_cpu_mem_usage=True, attn_implementation="eager",
    )
    merged = PeftModel.from_pretrained(base, args.adapter).merge_and_unload(safe_merge=True)
    args.output.mkdir(parents=True, exist_ok=True)
    merged.save_pretrained(args.output, safe_serialization=True)
    AutoTokenizer.from_pretrained(args.adapter).save_pretrained(args.output)
    files = {path.name: _sha(path) for path in sorted(args.output.iterdir()) if path.is_file()}
    manifest = {
        "schema_version": "functiongemma-tool-planner-merged-v1",
        "base_model": model_config, "adapter": str(args.adapter), "files": files,
    }
    (args.output / "merge-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, sort_keys=True))
    return 0


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
