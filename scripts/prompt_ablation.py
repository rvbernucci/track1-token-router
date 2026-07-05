#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from router.evals.prompt_ablation import (
    analyze_prompt_manifest,
    write_prompt_ablation_json,
    write_prompt_ablation_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze versioned prompts without calling a model.")
    parser.add_argument("--manifest", type=Path, default=Path("prompts/manifest.json"))
    parser.add_argument("--out-json", type=Path, default=Path("reports/generated/prompt-ablation.json"))
    parser.add_argument("--report", type=Path, default=Path("reports/generated/prompt-ablation.md"))
    parser.add_argument("--check", action="store_true", help="Return non-zero when manifest errors are found.")
    args = parser.parse_args()

    analysis = analyze_prompt_manifest(args.manifest)
    write_prompt_ablation_json(args.out_json, analysis)
    write_prompt_ablation_report(args.report, analysis)
    print(json.dumps({"errors": analysis["errors"], "versions": list(analysis["versions"])}, sort_keys=True))
    if args.check and analysis["errors"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
