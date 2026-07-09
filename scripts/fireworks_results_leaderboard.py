from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_RESULTS = (
    Path("reports/generated/fireworks-track1-category-20260709-results.jsonl"),
    Path("reports/generated/fireworks-hidden-variant-results.jsonl"),
    Path("reports/generated/fireworks-championship-results.jsonl"),
    Path("reports/generated/fireworks-frontier-20260709-results.jsonl"),
)
DEFAULT_REPORT = Path("reports/generated/fireworks-results-leaderboard.md")


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate paid Fireworks JSONL results without making API calls.")
    parser.add_argument("--results", action="append", type=Path, help="Result JSONL path. Can be repeated.")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--json", action="store_true", help="Print the full leaderboard JSON.")
    args = parser.parse_args()

    paths = tuple(args.results or [path for path in DEFAULT_RESULTS if path.exists()])
    rows = load_results(paths)
    leaderboard = build_leaderboard(rows, paths)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(render_markdown(leaderboard), encoding="utf-8")
    payload = leaderboard if args.json else {
        "ok": True,
        "rows": leaderboard["summary"]["rows"],
        "models": leaderboard["summary"]["models"],
        "domains": leaderboard["summary"]["domains"],
        "valid_rate": leaderboard["summary"]["valid_rate"],
        "estimated_cost_usd": leaderboard["summary"]["estimated_cost_usd"],
        "report": str(args.report),
    }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


def load_results(paths: tuple[Path, ...]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = line.strip()
            if not stripped:
                continue
            payload = json.loads(stripped)
            payload.setdefault("_source", str(path))
            payload.setdefault("_line", line_number)
            rows.append(payload)
    return rows


def build_leaderboard(rows: list[dict[str, Any]], paths: tuple[Path, ...] = ()) -> dict[str, Any]:
    by_model = _aggregate(rows, keys=("model",))
    by_domain_model = _aggregate(rows, keys=("domain", "model"))
    domains = sorted({str(row.get("domain") or "unknown") for row in rows})
    model_rows = sorted(by_model.values(), key=_leaderboard_sort_key)
    domain_tables: dict[str, list[dict[str, Any]]] = {}
    domain_winners: dict[str, dict[str, Any]] = {}
    domain_frontiers: dict[str, list[dict[str, Any]]] = {}
    for domain in domains:
        table = sorted(
            [row for key, row in by_domain_model.items() if key[0] == domain],
            key=_leaderboard_sort_key,
        )
        domain_tables[domain] = table
        if table:
            domain_winners[domain] = table[0]
            domain_frontiers[domain] = _pareto_frontier(table)
    valid = sum(1 for row in rows if row.get("valid"))
    total_cost = sum(float(row.get("estimated_cost_usd") or 0.0) for row in rows)
    total_tokens = sum(_usage_total(row) for row in rows)
    return {
        "summary": {
            "paths": [str(path) for path in paths],
            "rows": len(rows),
            "models": len({str(row.get("model") or "unknown") for row in rows}),
            "domains": len(domains),
            "valid": valid,
            "valid_rate": _rate(valid, len(rows)),
            "estimated_cost_usd": round(total_cost, 8),
            "tokens": total_tokens,
        },
        "models": model_rows,
        "domains": domain_tables,
        "domain_winners": domain_winners,
        "domain_pareto_frontiers": domain_frontiers,
        "failures": _failure_rows(rows),
    }


def render_markdown(leaderboard: dict[str, Any]) -> str:
    summary = leaderboard["summary"]
    lines = [
        "# Fireworks Results Leaderboard",
        "",
        f"- rows: `{summary['rows']}`",
        f"- models: `{summary['models']}`",
        f"- domains: `{summary['domains']}`",
        f"- valid_rate: `{summary['valid_rate']:.3f}`",
        f"- estimated_cost_usd: `{summary['estimated_cost_usd']:.8f}`",
        f"- tokens: `{summary['tokens']}`",
        "",
        "## Model Leaderboard",
        "",
        "| Model | Calls | Valid Rate | OK Rate | Avg Tokens | Cost USD | Avg Latency ms | Errors |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in leaderboard["models"]:
        lines.append(_table_row(row, include_model=True))
    lines.extend(["", "## Domain Winners", ""])
    lines.append("| Domain | Winner | Calls | Valid Rate | Avg Tokens | Cost USD | Avg Latency ms |")
    lines.append("| --- | --- | ---: | ---: | ---: | ---: | ---: |")
    for domain, row in sorted(leaderboard["domain_winners"].items()):
        lines.append(
            f"| `{domain}` | `{row['model']}` | {row['calls']} | {row['valid_rate']:.2f} "
            f"| {row['avg_tokens']:.0f} | {row['cost']:.8f} | {row['avg_latency_ms']:.0f} |"
        )
    lines.extend(["", "## Domain Pareto Frontiers", ""])
    for domain, rows in sorted(leaderboard["domain_pareto_frontiers"].items()):
        models = ", ".join(f"`{row['model']}`" for row in rows)
        lines.append(f"- `{domain}`: {models}")
    lines.extend(["", "## Failures", ""])
    if leaderboard["failures"]:
        for row in leaderboard["failures"][:40]:
            reason = row.get("validation_reason") or row.get("error") or "invalid"
            lines.append(f"- `{row.get('id')}` / `{row.get('domain')}` / `{row.get('model')}`: {reason}")
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def _aggregate(rows: list[dict[str, Any]], *, keys: tuple[str, ...]) -> dict[tuple[str, ...], dict[str, Any]]:
    groups: dict[tuple[str, ...], dict[str, Any]] = {}
    for item in rows:
        key = tuple(str(item.get(name) or "unknown") for name in keys)
        row = groups.setdefault(
            key,
            {
                **{name: key[index] for index, name in enumerate(keys)},
                "calls": 0,
                "ok": 0,
                "valid": 0,
                "tokens": 0,
                "cost": 0.0,
                "latency_ms": 0.0,
                "errors": 0,
            },
        )
        row["calls"] += 1
        row["ok"] += 1 if item.get("ok") else 0
        row["valid"] += 1 if item.get("valid") else 0
        row["tokens"] += _usage_total(item)
        row["cost"] += float(item.get("estimated_cost_usd") or 0.0)
        row["latency_ms"] += float(item.get("latency_ms") or 0.0)
        row["errors"] += 0 if item.get("ok") else 1
    for row in groups.values():
        calls = max(int(row["calls"]), 1)
        row["valid_rate"] = _rate(int(row["valid"]), calls)
        row["ok_rate"] = _rate(int(row["ok"]), calls)
        row["avg_tokens"] = float(row["tokens"]) / calls
        row["avg_cost"] = float(row["cost"]) / calls
        row["avg_latency_ms"] = float(row["latency_ms"]) / calls
        row["cost"] = round(float(row["cost"]), 8)
    return groups


def _pareto_frontier(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    frontier = []
    for row in rows:
        if not any(_dominates(other, row) for other in rows if other is not row):
            frontier.append(row)
    return sorted(frontier, key=_leaderboard_sort_key)


def _dominates(left: dict[str, Any], right: dict[str, Any]) -> bool:
    comparisons = [
        (float(left["valid_rate"]), float(right["valid_rate"]), True),
        (float(left["ok_rate"]), float(right["ok_rate"]), True),
        (float(left["avg_tokens"]), float(right["avg_tokens"]), False),
        (float(left["avg_cost"]), float(right["avg_cost"]), False),
        (float(left["avg_latency_ms"]), float(right["avg_latency_ms"]), False),
    ]
    weakly_better = all(a >= b if higher else a <= b for a, b, higher in comparisons)
    strictly_better = any(a > b if higher else a < b for a, b, higher in comparisons)
    return weakly_better and strictly_better


def _leaderboard_sort_key(row: dict[str, Any]) -> tuple[float, float, float, float, str]:
    return (
        -float(row["valid_rate"]),
        -float(row["ok_rate"]),
        float(row["avg_tokens"]),
        float(row["avg_cost"]),
        str(row.get("model") or ""),
    )


def _failure_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if not row.get("valid") or not row.get("ok")
    ]


def _table_row(row: dict[str, Any], *, include_model: bool) -> str:
    prefix = f"| `{row['model']}` " if include_model else "| "
    return (
        f"{prefix}| {row['calls']} | {row['valid_rate']:.2f} | {row['ok_rate']:.2f} "
        f"| {row['avg_tokens']:.0f} | {row['cost']:.8f} | {row['avg_latency_ms']:.0f} | {row['errors']} |"
    )


def _usage_total(row: dict[str, Any]) -> int:
    usage = row.get("usage")
    if not isinstance(usage, dict):
        return 0
    return int(usage.get("total") or 0)


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


if __name__ == "__main__":
    raise SystemExit(main())
