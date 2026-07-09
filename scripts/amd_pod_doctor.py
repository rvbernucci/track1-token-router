#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


MIN_PYTHON = (3, 10)
MIN_RECOMMENDED_VRAM_GIB = 32


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose an AMD Developer Cloud notebook/pod for Track 1.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--strict", action="store_true", help="Fail on warnings as well as errors.")
    args = parser.parse_args()

    report = build_report()
    if args.json:
        print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))
    else:
        print(render_report(report))

    has_errors = bool(report["errors"])
    has_warnings = bool(report["warnings"])
    return 1 if has_errors or (args.strict and has_warnings) else 0


def build_report() -> dict[str, Any]:
    commands = {
        name: shutil.which(name)
        for name in ("git", "curl", "wget", "python", "python3", "pip", "pip3", "rocm-smi", "rocminfo")
    }
    python_version = sys.version_info[:3]
    rocm_version = _read_first_existing(
        Path("/opt/rocm/.info/version"),
        Path("/opt/rocm/version"),
    )
    rocm_smi = _run(["rocm-smi", "--showmeminfo", "vram", "--showdriverversion", "--showproductname"])
    rocminfo = _run(["rocminfo"])
    filesystem = _run(["df", "-h", "."])
    memory = _run(["free", "-h"])
    vram_bytes = _parse_vram_total(rocm_smi["stdout"])
    gpu_agents = _parse_gpu_agents(rocminfo["stdout"])
    python_packages = _python_package_probe()

    errors: list[str] = []
    warnings: list[str] = []

    if python_version < MIN_PYTHON:
        errors.append(f"python must be >= {'.'.join(map(str, MIN_PYTHON))}; found {platform.python_version()}")
    for required in ("git", "python3", "pip3"):
        if not commands.get(required):
            errors.append(f"missing required command: {required}")
    if not commands.get("rocm-smi"):
        errors.append("missing rocm-smi; ROCm GPU access is not visible")
    if rocm_smi["returncode"] != 0:
        errors.append("rocm-smi failed; GPU may not be attached to this pod")
    if vram_bytes is None:
        warnings.append("could not parse GPU VRAM from rocm-smi")
    elif vram_bytes < MIN_RECOMMENDED_VRAM_GIB * 1024**3:
        warnings.append(f"GPU VRAM below recommended {MIN_RECOMMENDED_VRAM_GIB} GiB for large Gemma experiments")
    if not rocm_version:
        warnings.append("could not detect ROCm version from /opt/rocm")
    if not gpu_agents:
        warnings.append("rocminfo did not expose a named GPU agent")
    if not Path("pyproject.toml").exists() or not Path("router").exists():
        warnings.append("doctor is not running from the repository root")

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "system": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "cwd": str(Path.cwd()),
            "user": os.getenv("USER") or os.getenv("USERNAME") or "",
        },
        "python": {
            "executable": sys.executable,
            "version": platform.python_version(),
            "packages": python_packages,
        },
        "commands": commands,
        "rocm": {
            "version": rocm_version,
            "rocm_smi_returncode": rocm_smi["returncode"],
            "driver_line": _first_matching_line(rocm_smi["stdout"], "Driver version"),
            "vram_total_bytes": vram_bytes,
            "vram_total_gib": round(vram_bytes / 1024**3, 2) if vram_bytes else None,
            "gpu_agents": gpu_agents,
        },
        "storage": filesystem,
        "memory": memory,
    }


def render_report(report: dict[str, Any]) -> str:
    rocm = report["rocm"]
    lines = [
        "AMD Pod Doctor",
        "==============",
        f"ok: {report['ok']}",
        f"cwd: {report['system']['cwd']}",
        f"python: {report['python']['version']} ({report['python']['executable']})",
        f"rocm: {rocm.get('version') or 'unknown'}",
        f"gpu_agents: {', '.join(rocm.get('gpu_agents') or []) or 'none'}",
        f"vram_total_gib: {rocm.get('vram_total_gib')}",
    ]
    if report["errors"]:
        lines.extend(["", "Errors:", *[f"- {item}" for item in report["errors"]]])
    if report["warnings"]:
        lines.extend(["", "Warnings:", *[f"- {item}" for item in report["warnings"]]])
    lines.extend(["", "Commands:"])
    for name, path in sorted(report["commands"].items()):
        lines.append(f"- {name}: {path or 'missing'}")
    lines.extend(["", "Python packages:"])
    for name, value in sorted(report["python"]["packages"].items()):
        lines.append(f"- {name}: {value}")
    return "\n".join(lines)


def _run(command: list[str]) -> dict[str, Any]:
    if shutil.which(command[0]) is None:
        return {"returncode": 127, "stdout": "", "stderr": f"{command[0]} not found"}
    completed = subprocess.run(command, capture_output=True, text=True, timeout=30)
    return {
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _read_first_existing(*paths: Path) -> str | None:
    for path in paths:
        if path.exists():
            return path.read_text(encoding="utf-8", errors="replace").strip() or None
    return None


def _parse_vram_total(output: str) -> int | None:
    match = re.search(r"VRAM Total Memory \(B\):\s*(\d+)", output)
    return int(match.group(1)) if match else None


def _parse_gpu_agents(output: str) -> list[str]:
    agents: list[str] = []
    current_name = ""
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("Name:"):
            current_name = stripped.split(":", 1)[1].strip()
        if stripped.startswith("Uuid:") and "GPU-" in stripped and current_name:
            agents.append(current_name)
    return agents


def _first_matching_line(text: str, needle: str) -> str | None:
    for line in text.splitlines():
        if needle in line:
            return line.strip()
    return None


def _python_package_probe() -> dict[str, str]:
    packages: dict[str, str] = {}
    for name in ("numpy", "torch", "transformers", "vllm", "sglang"):
        try:
            module = __import__(name)
        except Exception as exc:
            packages[name] = f"not_installed:{type(exc).__name__}"
        else:
            packages[name] = str(getattr(module, "__version__", "installed"))
    return packages


if __name__ == "__main__":
    raise SystemExit(main())
