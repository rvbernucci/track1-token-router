#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path
import time


def pss_kb(pid: int) -> int:
    for line in Path(f"/proc/{pid}/smaps_rollup").read_text().splitlines():
        if line.startswith("Pss:"):
            return int(line.split()[1])
    raise ValueError(f"Pss missing for PID {pid}")


def read_pid(path: Path) -> int:
    return int(path.read_text().strip())


def alive(pid: int) -> bool:
    return Path(f"/proc/{pid}").exists()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runner-pid-file", type=Path, required=True)
    parser.add_argument("--e2b-pid-file", type=Path, required=True)
    parser.add_argument("--functiongemma-pid-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--interval-s", type=float, default=2.0)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=("timestamp", "e2b_pss_kb", "functiongemma_pss_kb", "combined_pss_kb"))
        writer.writeheader()
        while alive(read_pid(args.runner_pid_file)):
            e2b = pss_kb(read_pid(args.e2b_pid_file))
            functiongemma = pss_kb(read_pid(args.functiongemma_pid_file))
            writer.writerow({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "e2b_pss_kb": e2b,
                "functiongemma_pss_kb": functiongemma,
                "combined_pss_kb": e2b + functiongemma,
            })
            handle.flush()
            time.sleep(args.interval_s)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
