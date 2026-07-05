from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


def analyze_prompt_manifest(manifest_path: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    base = manifest_path.parent
    errors: list[str] = []
    versions: dict[str, Any] = {}

    for version_name, version_payload in sorted((manifest.get("versions") or {}).items()):
        if not isinstance(version_payload, dict):
            errors.append(f"version {version_name} must be an object")
            continue
        prompts = version_payload.get("prompts") or {}
        if not isinstance(prompts, dict) or not prompts:
            errors.append(f"version {version_name} has no prompts")
            continue

        prompt_rows = []
        for prompt_name, relative_path in sorted(prompts.items()):
            prompt_path = base / str(relative_path)
            if not prompt_path.exists():
                errors.append(f"missing prompt file: {prompt_path}")
                continue
            text = prompt_path.read_text(encoding="utf-8")
            if not text.strip():
                errors.append(f"empty prompt file: {prompt_path}")
            prompt_rows.append(_analyze_prompt(version_name, prompt_name, prompt_path, text))

        versions[version_name] = {
            "description": str(version_payload.get("description") or ""),
            "prompts": prompt_rows,
            "totals": _totals(prompt_rows),
        }

    default_version = manifest.get("default_version")
    if default_version not in versions:
        errors.append(f"default_version not found: {default_version}")

    return {
        "manifest": str(manifest_path),
        "default_version": default_version,
        "errors": errors,
        "versions": versions,
    }


def write_prompt_ablation_json(path: Path, analysis: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(analysis, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def write_prompt_ablation_report(path: Path, analysis: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Prompt Ablation Report",
        "",
        f"- default_version: `{analysis.get('default_version')}`",
        f"- errors: `{len(analysis.get('errors') or [])}`",
        "",
        "| version | prompt | approx_tokens | chars | lines | risk_flags |",
        "|---|---|---:|---:|---:|---|",
    ]
    for version_name, version_payload in analysis.get("versions", {}).items():
        for prompt in version_payload.get("prompts", []):
            lines.append(
                "| "
                f"{version_name} | "
                f"{prompt['name']} | "
                f"{prompt['approx_tokens']} | "
                f"{prompt['chars']} | "
                f"{prompt['lines']} | "
                f"`{', '.join(prompt['risk_flags']) or 'none'}` |"
            )

    lines.extend(["", "## Totals", ""])
    lines.append("| version | prompts | approx_tokens | chars |")
    lines.append("|---|---:|---:|---:|")
    for version_name, version_payload in analysis.get("versions", {}).items():
        totals = version_payload.get("totals", {})
        lines.append(
            "| "
            f"{version_name} | "
            f"{totals.get('prompts', 0)} | "
            f"{totals.get('approx_tokens', 0)} | "
            f"{totals.get('chars', 0)} |"
        )

    errors = analysis.get("errors") or []
    if errors:
        lines.extend(["", "## Errors", ""])
        for error in errors:
            lines.append(f"- {error}")

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- `approx_tokens` uses a conservative characters/4 estimate, useful for relative ablation only.",
            "- `strict_json_output` marks prompts that can fail if the model emits prose.",
            "- `freeform_answer` marks prompts whose output should remain natural and user-facing.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _analyze_prompt(version: str, name: str, path: Path, text: str) -> dict[str, Any]:
    return {
        "version": version,
        "name": name,
        "path": str(path),
        "chars": len(text),
        "lines": len(text.splitlines()),
        "approx_tokens": math.ceil(len(text) / 4),
        "risk_flags": _risk_flags(text),
    }


def _risk_flags(text: str) -> list[str]:
    lowered = text.lower()
    flags = []
    if "return only one compact json object" in lowered or "schema:" in lowered:
        flags.append("strict_json_output")
    if "return only the answer" in lowered or "answer the user's task" in lowered:
        flags.append("freeform_answer")
    if "do not mention" in lowered or "do not reveal" in lowered:
        flags.append("internal_guard")
    if "stale knowledge" in lowered or "factuality" in lowered:
        flags.append("knowledge_risk")
    return flags


def _totals(prompt_rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "prompts": len(prompt_rows),
        "chars": sum(int(row["chars"]) for row in prompt_rows),
        "lines": sum(int(row["lines"]) for row in prompt_rows),
        "approx_tokens": sum(int(row["approx_tokens"]) for row in prompt_rows),
    }
