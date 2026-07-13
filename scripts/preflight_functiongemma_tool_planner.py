#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


TRAINING_SPLITS = ("train", "validation")
EVALUATION_SPLITS = ("calibration", "sealed")


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail-closed FunctionGemma planner training preflight.")
    parser.add_argument("--config", type=Path, default=Path("configs/functiongemma-tool-planner-v1.json"))
    parser.add_argument("--data", type=Path, default=Path("data/functiongemma-tool-planner-v1"))
    parser.add_argument("--tokenizer", default="")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    config = json.loads(args.config.read_text())
    _validate_revision(config)
    report = audit_corpus(args.data)
    report["model"] = config["model"]
    report["max_length"] = int(config["dataset"]["max_length"])
    report["training_splits"] = list(TRAINING_SPLITS)
    report["selection_forbidden_splits"] = list(EVALUATION_SPLITS)

    tokenizer_source = args.tokenizer or config["model"]["id"]
    report["tokenizer_source"] = tokenizer_source
    token_report = audit_token_lengths(
        args.data,
        tokenizer_source,
        config["model"]["revision"] if not args.tokenizer else None,
        report["max_length"],
        args.offline,
    )
    report["gates"].update(token_report.pop("gates"))
    report.update(token_report)
    cuda_report = audit_cuda()
    report["gates"].update(cuda_report.pop("gates"))
    report.update(cuda_report)
    report["passed"] = all(report["gates"].values())
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))
    return 0 if report["passed"] else 1


def audit_corpus(data: Path) -> dict:
    ids: set[str] = set()
    prompts: set[str] = set()
    counts: Counter[str] = Counter()
    hashes: dict[str, str] = {}
    overlap = False
    for split in (*TRAINING_SPLITS, *EVALUATION_SPLITS):
        path = data / f"{split}.jsonl"
        payload = path.read_bytes()
        hashes[split] = hashlib.sha256(payload).hexdigest()
        for line in payload.decode().splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            prompt = row["messages"][1]["content"].strip().casefold()
            if row["id"] in ids or prompt in prompts:
                overlap = True
            ids.add(row["id"])
            prompts.add(prompt)
            counts[split] += 1
    return {
        "schema_version": "functiongemma-tool-planner-preflight-v1",
        "rows": dict(counts),
        "split_sha256": hashes,
        "gates": {
            "all_splits_present": all(counts[split] > 0 for split in (*TRAINING_SPLITS, *EVALUATION_SPLITS)),
            "unique_ids_and_prompts_across_splits": not overlap,
        },
    }


def audit_token_lengths(
    data: Path,
    source: str,
    revision: str | None,
    max_length: int,
    offline: bool,
    tokenizer=None,
) -> dict:
    if tokenizer is None:
        from transformers import AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(source, revision=revision, local_files_only=offline)
    lengths: list[int] = []
    for split in (*TRAINING_SPLITS, *EVALUATION_SPLITS):
        for line in (data / f"{split}.jsonl").read_text().splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            tokens = tokenizer.apply_chat_template(row["messages"], tools=row["tools"], tokenize=True)
            lengths.append(len(tokens))
    maximum = max(lengths)
    result = {
        "token_lengths": {
            "count": len(lengths),
            "minimum": min(lengths),
            "maximum": maximum,
            "margin": max_length - maximum,
        }
    }
    result["gates"] = {"all_examples_fit_context": maximum <= max_length}
    return result


def audit_cuda() -> dict:
    import torch

    available = torch.cuda.is_available()
    result = {
        "cuda": {
            "available": available,
            "torch": torch.__version__,
            "runtime": torch.version.cuda,
        },
        "gates": {"cuda_available": available},
    }
    if available:
        result["cuda"].update({
            "device": torch.cuda.get_device_name(0),
            "memory_mib": torch.cuda.get_device_properties(0).total_memory // 1024**2,
        })
    return result


def _validate_revision(config: dict) -> None:
    revision = config.get("model", {}).get("revision", "")
    if len(revision) != 40 or any(char not in "0123456789abcdef" for char in revision):
        raise ValueError("An immutable FunctionGemma revision is required.")


if __name__ == "__main__":
    raise SystemExit(main())
