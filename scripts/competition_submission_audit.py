#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
IMAGE_SIZE_LIMIT_BYTES = 10_000_000_000
MANIFEST_ACCEPT = ", ".join(
    [
        "application/vnd.oci.image.index.v1+json",
        "application/vnd.docker.distribution.manifest.list.v2+json",
        "application/vnd.oci.image.manifest.v1+json",
        "application/vnd.docker.distribution.manifest.v2+json",
    ]
)

REQUIRED_FILES = (
    "README.md",
    "SUBMISSION.md",
    "Dockerfile",
    ".github/workflows/ci.yml",
    ".github/workflows/release.yml",
    ".github/workflows/public-image-audit.yml",
    "router/adapters/official/lablab_track1.py",
    "scripts/offline_release_check.sh",
    "scripts/docker_resource_gate.sh",
    "scripts/track1_deterministic_coverage.py",
)


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    message: str
    evidence: dict[str, object]
    severity: str = "error"

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "ok": self.ok,
            "severity": self.severity,
            "message": self.message,
            "evidence": self.evidence,
        }


@dataclass(frozen=True)
class AuditReport:
    ok: bool
    checks: list[Check]
    metrics: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "errors": [check.to_dict() for check in self.checks if not check.ok and check.severity == "error"],
            "warnings": [check.to_dict() for check in self.checks if not check.ok and check.severity == "warning"],
            "checks": [check.to_dict() for check in self.checks],
            "metrics": self.metrics,
        }


@dataclass(frozen=True)
class ImageRef:
    registry: str
    repository: str
    reference: str


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit ACT II Track 1 submission readiness from the evaluator's point of view."
    )
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--image", help="Optional public GHCR image ref, for example ghcr.io/owner/repo:tag.")
    parser.add_argument("--expected-revision", help="Optional expected OCI revision label, usually the release commit SHA.")
    parser.add_argument("--expected-version", help="Optional expected OCI version label, usually the release tag.")
    parser.add_argument("--skip-network", action="store_true", help="Skip remote registry checks even when --image is set.")
    parser.add_argument("--skip-gates", action="store_true", help="Skip subprocess smoke gates; useful for fast unit tests.")
    parser.add_argument("--report", type=Path, default=Path("reports/generated/competition-submission-audit.md"))
    parser.add_argument("--json", action="store_true", help="Print the full JSON audit payload.")
    args = parser.parse_args()

    report = run_audit(
        args.root,
        image=args.image,
        expected_revision=args.expected_revision,
        expected_version=args.expected_version,
        skip_network=args.skip_network,
        run_gates=not args.skip_gates,
    )
    write_markdown_report(args.root / args.report if not args.report.is_absolute() else args.report, report)
    payload = report.to_dict() if args.json else _summary_payload(report, args.report)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if report.ok else 1


def run_audit(
    root: Path = ROOT,
    *,
    image: str | None = None,
    expected_revision: str | None = None,
    expected_version: str | None = None,
    skip_network: bool = False,
    run_gates: bool = True,
) -> AuditReport:
    root = root.resolve()
    checks: list[Check] = []
    metrics: dict[str, object] = {
        "root": str(root),
        "image": image or "",
        "expected_revision": expected_revision or "",
        "expected_version": expected_version or "",
        "image_size_limit_bytes": IMAGE_SIZE_LIMIT_BYTES,
    }

    checks.extend(_check_required_files(root))
    checks.append(_check_dockerfile_contract(root / "Dockerfile"))
    checks.append(_check_release_workflow(root / ".github/workflows/release.yml"))
    checks.append(_check_readme_contract(root / "README.md"))

    if run_gates:
        checks.append(_check_official_submit_smoke(root))
        checks.append(_check_deterministic_coverage_gate(root))

    if image and not skip_network:
        checks.append(
            _check_public_ghcr_image(
                image,
                expected_revision=expected_revision,
                expected_version=expected_version,
            )
        )
    elif not image:
        checks.append(
            Check(
                "public_ghcr_image",
                False,
                "No --image was provided; run with the final GHCR tag before submission.",
                {"example": "ghcr.io/rvbernucci/track1-token-router:offline-rc-YYYYMMDD-HHMM"},
                severity="warning",
            )
        )
    elif skip_network:
        checks.append(
            Check(
                "public_ghcr_image",
                False,
                "Remote GHCR inspection skipped by --skip-network.",
                {"image": image},
                severity="warning",
            )
        )

    ok = not any(not check.ok and check.severity == "error" for check in checks)
    return AuditReport(ok=ok, checks=checks, metrics=metrics)


def write_markdown_report(path: Path, report: AuditReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Competition Submission Audit",
        "",
        f"- ok: `{report.ok}`",
        f"- root: `{report.metrics['root']}`",
        f"- image: `{report.metrics['image'] or 'not provided'}`",
        f"- expected_revision: `{report.metrics['expected_revision'] or 'not provided'}`",
        f"- expected_version: `{report.metrics['expected_version'] or 'not provided'}`",
        f"- image_size_limit_bytes: `{report.metrics['image_size_limit_bytes']}`",
        "",
        "## Checks",
        "",
        "| check | severity | ok | message |",
        "|---|---|---:|---|",
    ]
    for check in report.checks:
        lines.append(f"| {check.name} | {check.severity} | `{check.ok}` | {check.message} |")
    lines.extend(["", "## Evidence", ""])
    for check in report.checks:
        evidence = json.dumps(check.evidence, ensure_ascii=False, sort_keys=True)
        lines.append(f"- `{check.name}`: `{evidence}`")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_image_ref(image: str) -> ImageRef:
    if not image.startswith("ghcr.io/"):
        raise ValueError("Only ghcr.io image refs are supported by this audit.")
    without_registry = image[len("ghcr.io/") :]
    if "@" in without_registry:
        repository, reference = without_registry.split("@", 1)
    else:
        slash = without_registry.rfind("/")
        colon = without_registry.rfind(":")
        if colon <= slash:
            raise ValueError("Image ref must include an explicit tag or digest.")
        repository = without_registry[:colon]
        reference = without_registry[colon + 1 :]
    if not repository or not reference:
        raise ValueError("Image ref must include repository and reference.")
    return ImageRef(registry="ghcr.io", repository=repository, reference=reference)


def inspect_manifest_index(index: dict[str, Any]) -> dict[str, object]:
    media_type = str(index.get("mediaType") or "")
    if _is_image_manifest(media_type):
        return {
            "linux_amd64": True,
            "digest": "",
            "manifest_size_bytes": _manifest_size(index),
            "media_type": media_type,
        }
    manifests = index.get("manifests")
    if not isinstance(manifests, list):
        raise ValueError("Registry response is neither an OCI index nor an image manifest.")
    for manifest in manifests:
        if not isinstance(manifest, dict):
            continue
        platform = manifest.get("platform") or {}
        if platform.get("os") == "linux" and platform.get("architecture") == "amd64":
            return {
                "linux_amd64": True,
                "digest": str(manifest.get("digest") or ""),
                "manifest_size_bytes": int(manifest.get("size") or 0),
                "media_type": str(manifest.get("mediaType") or ""),
            }
    return {
        "linux_amd64": False,
        "digest": "",
        "manifest_size_bytes": 0,
        "media_type": media_type,
    }


def inspect_image_manifest(manifest: dict[str, Any]) -> dict[str, object]:
    size = _manifest_size(manifest)
    config = manifest.get("config")
    return {
        "compressed_size_bytes": size,
        "under_10gb": size <= IMAGE_SIZE_LIMIT_BYTES,
        "layers": len(manifest.get("layers") or []),
        "config_digest": str(config.get("digest") or "") if isinstance(config, dict) else "",
    }


def inspect_image_config(config: dict[str, Any]) -> dict[str, object]:
    image_config = config.get("config") if isinstance(config.get("config"), dict) else {}
    raw_labels = image_config.get("Labels") if isinstance(image_config, dict) else {}
    labels = {
        str(key): str(value)
        for key, value in (raw_labels or {}).items()
        if value is not None
    } if isinstance(raw_labels, dict) else {}
    return {
        "labels": labels,
        "source": labels.get("org.opencontainers.image.source", ""),
        "revision": labels.get("org.opencontainers.image.revision", ""),
        "version": labels.get("org.opencontainers.image.version", ""),
    }


def _check_required_files(root: Path) -> list[Check]:
    checks: list[Check] = []
    for relative in REQUIRED_FILES:
        path = root / relative
        checks.append(
            Check(
                f"required_file:{relative}",
                path.exists(),
                f"{relative} exists" if path.exists() else f"{relative} is missing",
                {"path": str(path)},
            )
        )
    return checks


def _check_dockerfile_contract(path: Path) -> Check:
    content = _read_if_exists(path)
    required_tokens = [
        "ENTRYPOINT [\"router\"]",
        "CMD [\"submit-track1\"]",
        "ROUTER_MODE=fireworks",
        "ENABLE_GUARDRAILS=1",
        "ENABLE_ORCHESTRATOR=1",
    ]
    missing = [token for token in required_tokens if token not in content]
    return Check(
        "dockerfile_official_contract",
        not missing,
        "Dockerfile defaults to the official Track 1 file contract." if not missing else "Dockerfile is missing official contract defaults.",
        {"path": str(path), "missing": missing},
    )


def _check_release_workflow(path: Path) -> Check:
    content = _read_if_exists(path)
    required_tokens = [
        "docker/setup-buildx-action@v3",
        "docker/build-push-action@v6",
        "platforms: linux/amd64",
        "push: true",
        "packages: write",
        "ghcr.io/${{ github.repository }}",
        "org.opencontainers.image.source",
        "org.opencontainers.image.revision",
        "org.opencontainers.image.version",
        "Gate the exact published image under evaluator limits",
        "competition_submission_audit.py",
    ]
    missing = [token for token in required_tokens if token not in content]
    return Check(
        "release_workflow_linux_amd64_ghcr",
        not missing,
        "Release workflow publishes a linux/amd64 GHCR image." if not missing else "Release workflow is missing GHCR/linux-amd64 safeguards.",
        {"path": str(path), "missing": missing},
    )


def _check_readme_contract(path: Path) -> Check:
    content = _read_if_exists(path)
    required_tokens = [
        "submit-track1",
        "ROUTER_MODE=fireworks",
        "ROUTER_MODE=three_route",
        "ALLOWED_MODELS",
        "ghcr.io/rvbernucci/track1-token-router",
    ]
    missing = [token for token in required_tokens if token not in content]
    return Check(
        "readme_submission_instructions",
        not missing,
        "README documents official, three-route and GHCR submission paths." if not missing else "README is missing submission-critical instructions.",
        {"path": str(path), "missing": missing},
    )


def _check_official_submit_smoke(root: Path) -> Check:
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "results.json"
        command = [
            sys.executable,
            "-m",
            "router",
            "submit-track1",
            "--input",
            "fixtures/official/lablab_track1_tasks.json",
            "--output",
            str(output),
        ]
        result = _run(command, root, env={"ROUTER_MODE": "mock"})
        evidence: dict[str, object] = {
            "command": command,
            "returncode": result.returncode,
            "stderr": _preview(result.stderr),
        }
        if result.returncode != 0:
            return Check("official_submit_smoke", False, "Official adapter smoke command failed.", evidence)
        try:
            payload = json.loads(output.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            evidence["parse_error"] = str(exc)
            return Check("official_submit_smoke", False, "Official adapter smoke output is not valid JSON.", evidence)
        valid = (
            isinstance(payload, list)
            and bool(payload)
            and all(isinstance(item, dict) and item.get("task_id") and "answer" in item for item in payload)
        )
        evidence.update({"tasks": len(payload) if isinstance(payload, list) else 0, "output": str(output)})
        return Check(
            "official_submit_smoke",
            valid,
            "Official adapter reads tasks and writes evaluator-shaped results." if valid else "Official adapter output shape is invalid.",
            evidence,
        )


def _check_deterministic_coverage_gate(root: Path) -> Check:
    command = [sys.executable, "scripts/track1_deterministic_coverage.py", "--check"]
    result = _run(command, root)
    evidence: dict[str, object] = {
        "command": command,
        "returncode": result.returncode,
        "stdout": _preview(result.stdout),
        "stderr": _preview(result.stderr),
    }
    if result.stdout.strip().startswith("{"):
        try:
            evidence["summary"] = json.loads(result.stdout)
        except json.JSONDecodeError:
            pass
    return Check(
        "deterministic_coverage_gate",
        result.returncode == 0,
        "Deterministic zero-token coverage gate passes." if result.returncode == 0 else "Deterministic zero-token coverage gate failed.",
        evidence,
    )


def _check_public_ghcr_image(
    image: str,
    *,
    expected_revision: str | None = None,
    expected_version: str | None = None,
) -> Check:
    try:
        image_ref = parse_image_ref(image)
        token = _ghcr_pull_token(image_ref.repository)
        index = _registry_json(image_ref, token, image_ref.reference, MANIFEST_ACCEPT)
        platform = inspect_manifest_index(index)
        if not platform["linux_amd64"]:
            return Check(
                "public_ghcr_image",
                False,
                "GHCR image is public, but no linux/amd64 manifest was found.",
                {"image": image, "platform": platform},
            )
        digest = str(platform["digest"])
        manifest = _registry_json(image_ref, token, digest or image_ref.reference, MANIFEST_ACCEPT)
        size = inspect_image_manifest(manifest)
        config_digest = str(size.get("config_digest") or "")
        config = inspect_image_config(_registry_blob_json(image_ref, token, config_digest)) if config_digest else {}
        traceability = _validate_traceability(
            config,
            expected_revision=expected_revision,
            expected_version=expected_version,
        )
        ok = bool(size["under_10gb"]) and traceability["ok"]
        evidence = {"image": image, "platform": platform, "size": size, "config": config, "traceability": traceability}
        return Check(
            "public_ghcr_image",
            ok,
            "GHCR image is public, linux/amd64, under 10GB and traceable." if ok else "GHCR image failed size or OCI traceability checks.",
            evidence,
        )
    except Exception as exc:
        return Check(
            "public_ghcr_image",
            False,
            "Could not verify public GHCR image pullability.",
            {"image": image, "error": str(exc)},
        )


def _ghcr_pull_token(repository: str) -> str:
    query = urllib.parse.urlencode(
        {
            "service": "ghcr.io",
            "scope": f"repository:{repository}:pull",
        }
    )
    payload = _http_json(f"https://ghcr.io/token?{query}", headers={})
    token = payload.get("token")
    if not isinstance(token, str) or not token:
        raise ValueError("GHCR token response did not include a bearer token.")
    return token


def _registry_json(image: ImageRef, token: str, reference: str, accept: str) -> dict[str, Any]:
    url = f"https://{image.registry}/v2/{image.repository}/manifests/{reference}"
    return _http_json(url, headers={"Authorization": f"Bearer {token}", "Accept": accept})


def _registry_blob_json(image: ImageRef, token: str, digest: str) -> dict[str, Any]:
    url = f"https://{image.registry}/v2/{image.repository}/blobs/{digest}"
    return _http_json(url, headers={"Authorization": f"Bearer {token}"})


def _validate_traceability(
    config: dict[str, object],
    *,
    expected_revision: str | None,
    expected_version: str | None,
) -> dict[str, object]:
    errors: list[str] = []
    revision = str(config.get("revision") or "")
    version = str(config.get("version") or "")
    source = str(config.get("source") or "")
    if expected_revision and revision != expected_revision:
        errors.append("revision_mismatch")
    if expected_version and version != expected_version:
        errors.append("version_mismatch")
    return {
        "ok": not errors,
        "errors": errors,
        "source": source,
        "revision": revision,
        "version": version,
        "expected_revision": expected_revision or "",
        "expected_version": expected_version or "",
    }


def _http_json(url: str, *, headers: dict[str, str]) -> dict[str, Any]:
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise ValueError(f"HTTP {exc.code} for {url}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object from {url}")
    return payload


def _run(command: list[str], root: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run(
        command,
        cwd=root,
        env=merged_env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def _summary_payload(report: AuditReport, report_path: Path) -> dict[str, object]:
    return {
        "ok": report.ok,
        "errors": len([check for check in report.checks if not check.ok and check.severity == "error"]),
        "warnings": len([check for check in report.checks if not check.ok and check.severity == "warning"]),
        "checks": len(report.checks),
        "report": str(report_path),
    }


def _manifest_size(manifest: dict[str, Any]) -> int:
    config = manifest.get("config")
    total = int(config.get("size") or 0) if isinstance(config, dict) else 0
    layers = manifest.get("layers") or []
    if isinstance(layers, list):
        total += sum(int(layer.get("size") or 0) for layer in layers if isinstance(layer, dict))
    return total


def _is_image_manifest(media_type: str) -> bool:
    return media_type in {
        "application/vnd.oci.image.manifest.v1+json",
        "application/vnd.docker.distribution.manifest.v2+json",
    }


def _read_if_exists(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _preview(value: str, *, limit: int = 800) -> str:
    collapsed = " ".join(value.split())
    return collapsed[:limit]


if __name__ == "__main__":
    raise SystemExit(main())
