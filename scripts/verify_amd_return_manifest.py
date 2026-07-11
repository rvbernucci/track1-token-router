#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
REVISION_RE = re.compile(r"^[0-9a-f]{40,64}$")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify the hash-pinned AMD return handoff.")
    parser.add_argument(
        "command",
        choices=("source", "prepare-return", "verify-return"),
        nargs="?",
        default="source",
    )
    parser.add_argument("--manifest", type=Path, default=Path("configs/amd-return-manifest-v1.json"))
    parser.add_argument("--write-checksums", action="store_true")
    args = parser.parse_args(argv)

    manifest_path = _absolute(args.manifest, ROOT)
    try:
        manifest = load_manifest(manifest_path)
        if args.command == "source":
            result = verify_source_bundle(manifest, root=ROOT)
            if args.write_checksums:
                output = _absolute(Path(manifest["upload"]["checksum_path"]), ROOT)
                entries = [(manifest_path, _sha256(manifest_path))]
                entries.extend(
                    (_safe_path(ROOT, row["path"]), str(row["sha256"]))
                    for row in manifest["source_bundle"]
                )
                write_checksum_file(output, entries, root=ROOT)
                result["checksum_path"] = str(output.relative_to(ROOT))
        elif args.command == "prepare-return":
            result = prepare_return_checksums(manifest, root=ROOT)
        else:
            result = verify_return_bundle(manifest, root=ROOT)
    except (KeyError, OSError, TypeError, ValueError) as exc:
        print(json.dumps({"passed": False, "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 1

    print(json.dumps(result, sort_keys=True))
    return 0


def load_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "amd-return-manifest-v1":
        raise ValueError("AMD return manifest schema is invalid.")
    if not isinstance(payload.get("source_bundle"), list) or not payload["source_bundle"]:
        raise ValueError("AMD return source bundle is empty.")
    if not isinstance(payload.get("download", {}).get("expected_paths"), list):
        raise ValueError("AMD return expected path list is invalid.")
    return payload


def verify_source_bundle(manifest: Mapping[str, Any], *, root: Path) -> dict[str, Any]:
    root = root.resolve()
    checked: list[str] = []
    seen: set[str] = set()
    for row in manifest["source_bundle"]:
        if not isinstance(row, Mapping):
            raise ValueError("Source bundle entries must be objects.")
        relative = _required_string(row, "path")
        expected = _required_sha256(row.get("sha256"), f"source_bundle[{relative}].sha256")
        if relative in seen:
            raise ValueError(f"Duplicate source bundle path: {relative}")
        seen.add(relative)
        path = _safe_path(root, relative)
        if not path.is_file():
            raise ValueError(f"Source bundle artifact is missing: {relative}")
        actual = _sha256(path)
        if actual != expected:
            raise ValueError(f"Source bundle SHA-256 mismatch: {relative}")
        checked.append(relative)

    _validate_model_pins(manifest["model_pins"])
    _validate_thresholds(manifest["release_thresholds"])
    return {"passed": True, "phase": "source", "checked": len(checked), "paths": checked}


def prepare_return_checksums(manifest: Mapping[str, Any], *, root: Path) -> dict[str, Any]:
    root = root.resolve()
    expected_paths = _expected_return_paths(manifest, root=root)
    missing = [str(path.relative_to(root)) for path in expected_paths if not path.is_file()]
    if missing:
        raise ValueError("AMD return artifacts are missing: " + ", ".join(missing))
    for path in expected_paths:
        _validate_return_file(path, root=root)
    checksum_path = _return_checksum_path(manifest, root=root)
    write_checksum_file(checksum_path, [(path, _sha256(path)) for path in expected_paths], root=root)
    return {
        "passed": True,
        "phase": "prepare-return",
        "checked": len(expected_paths),
        "checksum_path": str(checksum_path.relative_to(root)),
    }


def verify_return_bundle(manifest: Mapping[str, Any], *, root: Path) -> dict[str, Any]:
    root = root.resolve()
    expected_paths = _expected_return_paths(manifest, root=root)
    expected_relatives = {str(path.relative_to(root)) for path in expected_paths}
    checksum_path = _return_checksum_path(manifest, root=root)
    if not checksum_path.is_file():
        raise ValueError(f"AMD return checksum file is missing: {checksum_path.relative_to(root)}")
    checksums = read_checksum_file(checksum_path, root=root)
    if set(checksums) != expected_relatives:
        missing = sorted(expected_relatives - set(checksums))
        unexpected = sorted(set(checksums) - expected_relatives)
        raise ValueError(f"AMD return checksum coverage mismatch; missing={missing}, unexpected={unexpected}")
    for path in expected_paths:
        relative = str(path.relative_to(root))
        if not path.is_file():
            raise ValueError(f"AMD return artifact is missing: {relative}")
        if _sha256(path) != checksums[relative]:
            raise ValueError(f"AMD return SHA-256 mismatch: {relative}")
        _validate_return_file(path, root=root)
    return {"passed": True, "phase": "verify-return", "checked": len(expected_paths)}


def write_checksum_file(path: Path, entries: Sequence[tuple[Path, str]], *, root: Path) -> None:
    root = root.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    seen: set[str] = set()
    for artifact, digest in entries:
        resolved = artifact.resolve()
        try:
            relative = str(resolved.relative_to(root.resolve()))
        except ValueError as exc:
            raise ValueError(f"Checksum artifact escapes repository root: {artifact}") from exc
        if relative in seen:
            raise ValueError(f"Duplicate checksum artifact: {relative}")
        seen.add(relative)
        lines.append(f"{_required_sha256(digest, relative)}  {relative}")
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text("\n".join(lines) + "\n", encoding="utf-8")
    temporary.replace(path)


def read_checksum_file(path: Path, *, root: Path) -> dict[str, str]:
    root = root.resolve()
    checksums: dict[str, str] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        parts = line.split("  ", 1)
        if len(parts) != 2:
            raise ValueError(f"Malformed checksum line {line_number}: {path}")
        digest = _required_sha256(parts[0], f"checksum line {line_number}")
        relative = parts[1].strip()
        _safe_path(root, relative)
        if relative in checksums:
            raise ValueError(f"Duplicate checksum path: {relative}")
        checksums[relative] = digest
    if not checksums:
        raise ValueError(f"Checksum file is empty: {path}")
    return checksums


def _validate_model_pins(payload: Mapping[str, Any]) -> None:
    base = payload["functiongemma_base"]
    if _required_string(base, "id") != "google/functiongemma-270m-it":
        raise ValueError("Unexpected FunctionGemma base model.")
    _required_revision(base.get("revision"), "functiongemma_base.revision")
    _required_sha256(payload["functiongemma_q8"].get("sha256"), "functiongemma_q8.sha256")
    _required_revision(payload["llama_cpp"].get("commit"), "llama_cpp.commit")
    e2b = payload["gemma_e2b"]
    if e2b.get("status") != "must-rerun-on-amd" or e2b.get("release_blocked_without_new_artifact_hash") is not True:
        raise ValueError("Gemma E2B must remain blocked until the AMD artifact is hash-pinned.")


def _validate_thresholds(payload: Mapping[str, Any]) -> None:
    bounded = (
        "functiongemma_schema_validity",
        "functiongemma_intent_accuracy",
        "local_precision",
        "local_wilson_lower_95",
        "probability_perturbation_flip_rate",
    )
    for name in bounded:
        value = payload.get(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= float(value) <= 1:
            raise ValueError(f"Release threshold {name} must be between zero and one.")
    if payload.get("docker_platform") != "linux/amd64":
        raise ValueError("AMD return Docker platform must be linux/amd64.")
    if int(payload.get("combined_peak_rss_mb", 0)) > 3584:
        raise ValueError("Combined peak RSS threshold exceeds the declared safety envelope.")
    if int(payload.get("batch_runtime_seconds", 0)) > 570:
        raise ValueError("Batch runtime threshold removes the evaluator reserve.")
    if int(payload.get("docker_compressed_size_bytes", 0)) > 10_000_000_000:
        raise ValueError("Docker compressed size threshold exceeds the official limit.")


def _validate_return_file(path: Path, *, root: Path) -> None:
    if path.suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, (dict, list)):
            raise ValueError(f"Return JSON must contain an object or array: {path}")
    elif path.suffix == ".jsonl":
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if not lines:
            raise ValueError(f"Return JSONL is empty: {path}")
        for line_number, line in enumerate(lines, start=1):
            try:
                json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Malformed JSONL line {line_number}: {path}") from exc
    elif path.name.endswith(".sha256"):
        checksums = read_checksum_file(path, root=root)
        for relative, expected in checksums.items():
            artifact = _safe_path(root, relative)
            if not artifact.is_file():
                raise ValueError(f"Model artifact is missing: {relative}")
            if _sha256(artifact) != expected:
                raise ValueError(f"Model artifact SHA-256 mismatch: {relative}")


def _expected_return_paths(manifest: Mapping[str, Any], *, root: Path) -> list[Path]:
    relatives = manifest["download"]["expected_paths"]
    if not relatives or len(relatives) != len(set(relatives)):
        raise ValueError("AMD return expected paths must be non-empty and unique.")
    return [_safe_path(root, str(relative)) for relative in relatives]


def _return_checksum_path(manifest: Mapping[str, Any], *, root: Path) -> Path:
    return _safe_path(root, _required_string(manifest["download"], "checksum_path"))


def _safe_path(root: Path, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute():
        raise ValueError(f"Manifest path must be relative: {relative}")
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"Manifest path escapes repository root: {relative}") from exc
    return resolved


def _required_string(payload: Mapping[str, Any], name: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string.")
    return value.strip()


def _required_sha256(value: Any, name: str) -> str:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest.")
    return value


def _required_revision(value: Any, name: str) -> str:
    if not isinstance(value, str) or not REVISION_RE.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase 40-64 character revision digest.")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _absolute(path: Path, root: Path) -> Path:
    return path if path.is_absolute() else root / path


if __name__ == "__main__":
    raise SystemExit(main())
