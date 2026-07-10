from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Sequence

from router.dataset_forge.adjudication import adjudicate, apply_manual_reviews
from router.dataset_forge.contracts import GoldAssessment
from router.dataset_forge.metrics import build_report
from router.dataset_forge.hidden_seed import import_hidden_seed
from router.dataset_forge.pipeline import ForgePaths, deduplicate_validated, generate, rate, rate_target_contract, validate
from router.dataset_forge.planner import build_generation_targets, target_summary
from router.dataset_forge.providers import ProviderError, provider_from_env
from router.dataset_forge.split import build_splits
from router.dataset_forge.storage import AppendOnlyJsonl


DEFAULT_ROOT = Path("data/dataset-forge/work")
DEFAULT_ENV_FILES = (Path(".env.dataset-forge.local"), Path(".env.fireworks.local"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dataset-forge", description="Resumable FunctionGemma assessment dataset forge.")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--env-file", action="append", type=Path)
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan_parser = subparsers.add_parser("plan")
    _target_args(plan_parser)
    plan_parser.add_argument("--providers", default="claude,agy")

    generate_parser = subparsers.add_parser("generate")
    _target_args(generate_parser)
    _network_args(generate_parser)
    generate_parser.add_argument("--providers", default="claude,agy")
    generate_parser.add_argument("--fallback-provider", choices=["claude", "agy", "fireworks"])
    generate_parser.add_argument("--batch-size", type=int, default=10)
    generate_parser.add_argument("--max-workers", type=int, default=2)
    generate_parser.add_argument("--fireworks-budget-usd", type=float, default=0.0)

    subparsers.add_parser("validate")
    subparsers.add_parser("deduplicate")

    rate_parser = subparsers.add_parser("rate")
    _network_args(rate_parser)
    rate_parser.add_argument("--providers", default="claude,agy")
    rate_parser.add_argument("--batch-size", type=int, default=10)
    rate_parser.add_argument("--max-workers", type=int, default=2)
    rate_parser.add_argument("--fireworks-budget-usd", type=float, default=0.0)
    rate_parser.add_argument("--scope", choices=["all", "needs-review"], default="all")
    subparsers.add_parser("rate-contract")

    subparsers.add_parser("adjudicate")
    review_parser = subparsers.add_parser("review")
    review_parser.add_argument("--input", type=Path, required=True)
    hidden_parser = subparsers.add_parser("import-hidden")
    hidden_parser.add_argument("--input", type=Path, required=True)
    subparsers.add_parser("split")
    report_parser = subparsers.add_parser("report")
    report_parser.add_argument("--json-out", type=Path)
    report_parser.add_argument("--markdown-out", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _load_env_files(tuple(args.env_file or DEFAULT_ENV_FILES))
    paths = ForgePaths(args.root)
    try:
        if args.command == "plan":
            return _print_json(_plan(args))
        if args.command == "generate":
            plan = _plan(args)
            if not args.execute:
                return _print_json({**plan, "dry_run": True, "network_calls": 0})
            primary_provider_names = tuple(_provider_names(args.providers))
            providers = _providers(args.providers, role="generator")
            if args.fallback_provider and args.fallback_provider not in providers:
                providers[args.fallback_provider] = provider_from_env(args.fallback_provider, role="generator")
            summary = generate(
                targets=build_generation_targets(args.count, seed=args.seed),
                providers=providers,
                paths=paths,
                batch_size=args.batch_size,
                max_workers=args.max_workers,
                fireworks_budget_usd=args.fireworks_budget_usd,
                fallback_provider=args.fallback_provider,
                provider_order=primary_provider_names,
            )
            return _print_json(summary)
        if args.command == "validate":
            return _print_json(validate(paths))
        if args.command == "deduplicate":
            return _print_json(deduplicate_validated(paths))
        if args.command == "rate":
            provider_names = _provider_names(args.providers)
            if not args.execute:
                return _print_json(
                    {
                        "dry_run": True,
                        "network_calls": 0,
                        "providers": provider_names,
                        "batch_size": args.batch_size,
                        "root": str(args.root),
                    }
                )
            providers = _providers(args.providers, role="rater")
            example_ids = _needs_review_ids(paths) if args.scope == "needs-review" else None
            with ThreadPoolExecutor(max_workers=min(args.max_workers, len(providers))) as executor:
                futures = {
                    name: executor.submit(
                        rate,
                        provider_name=name,
                        provider=provider,
                        paths=paths,
                        batch_size=args.batch_size,
                        fireworks_budget_usd=args.fireworks_budget_usd,
                        example_ids=example_ids,
                    )
                    for name, provider in providers.items()
                }
                summaries = {name: future.result() for name, future in futures.items()}
            return _print_json({"providers": summaries})
        if args.command == "rate-contract":
            return _print_json(rate_target_contract(paths))
        if args.command == "adjudicate":
            return _print_json(adjudicate(paths))
        if args.command == "review":
            return _print_json(apply_manual_reviews(paths, args.input))
        if args.command == "import-hidden":
            return _print_json(import_hidden_seed(paths, args.input))
        if args.command == "split":
            return _print_json(build_splits(paths))
        if args.command == "report":
            report = build_report(paths)
            if args.json_out:
                _write_json(args.json_out, report)
            if args.markdown_out:
                args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
                args.markdown_out.write_text(_render_markdown(report), encoding="utf-8")
            return _print_json(report)
    except (ProviderError, ValueError) as exc:
        print(f"dataset-forge error: {exc}", file=sys.stderr)
        return 2
    return 2


def _plan(args: argparse.Namespace) -> dict[str, object]:
    targets = build_generation_targets(args.count, seed=args.seed)
    providers = _provider_names(args.providers)
    batch_size = getattr(args, "batch_size", 10)
    return {
        "dry_run": True,
        "network_calls": 0,
        "root": str(args.root),
        "seed": args.seed,
        "providers": providers,
        "batch_size": batch_size,
        "planned_batches": (len(targets) + batch_size - 1) // batch_size,
        "targets": target_summary(targets),
    }


def _providers(raw: str, *, role: str) -> dict[str, object]:
    return {name: provider_from_env(name, role=role) for name in _provider_names(raw)}


def _provider_names(raw: str) -> list[str]:
    names = [item.strip().lower() for item in raw.split(",") if item.strip()]
    if not names or len(names) != len(set(names)):
        raise ValueError("Provider list must be non-empty and unique.")
    allowed = {"claude", "agy", "fireworks"}
    unknown = sorted(set(names) - allowed)
    if unknown:
        raise ValueError(f"Unknown providers: {unknown}.")
    return names


def _target_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--count", type=int, default=120)
    parser.add_argument("--seed", type=int, default=46)


def _network_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--execute", action="store_true", help="Allow external model calls. Default is dry-run.")


def _load_env_files(paths: tuple[Path, ...]) -> None:
    for path in paths:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _needs_review_ids(paths: ForgePaths) -> set[str]:
    history = [
        GoldAssessment.from_mapping(payload)
        for payload in AppendOnlyJsonl(paths.root / "adjudicated" / "gold.jsonl").read_all()
    ]
    latest: dict[str, GoldAssessment] = {}
    for item in history:
        current = latest.get(item.example_id)
        if current is None or item.revision > current.revision:
            latest[item.example_id] = item
    return {
        example_id
        for example_id, item in latest.items()
        if item.adjudication_status == "needs_review"
    }


def _render_markdown(report: dict[str, object]) -> str:
    agreement = report.get("agreement") if isinstance(report.get("agreement"), dict) else {}
    return "\n".join(
        [
            "# Dataset Forge Report",
            "",
            f"- generated: {report.get('generated', 0)}",
            f"- validated: {report.get('validated', 0)}",
            f"- deduplicated: {report.get('deduplicated', 0)}",
            f"- duplicate rate: {float(report.get('duplicate_rate') or 0):.4f}",
            f"- ratings: {report.get('ratings', 0)}",
            f"- accepted gold: {report.get('gold_accepted', 0)}",
            f"- needs review: {report.get('gold_needs_review', 0)}",
            f"- Fireworks billable USD: {float(report.get('fireworks_billable_usd') or 0):.8f}",
            f"- rater pair count: {agreement.get('pair_count', 0)}",
            f"- intent agreement: {agreement.get('intent_exact')}",
            f"- sub-intent agreement: {agreement.get('sub_intent_exact')}",
            "",
        ]
    )


def _print_json(payload: dict[str, object]) -> int:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
