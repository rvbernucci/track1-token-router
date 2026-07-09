#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path


DEFAULT_INDEX_URL = "https://docs.fireworks.ai/llms.txt"
DEFAULT_MARKDOWN = Path("docs/FIREWORKS_DOCS_MAP.md")
DEFAULT_JSON = Path("docs/fireworks-docs-index.json")

GROUP_LABELS = {
    "_root": "Root / special pages",
    "accounts": "Accounts, billing, users and access",
    "api-reference": "API reference",
    "deployments": "Dedicated deployments",
    "ecosystem": "Ecosystem integrations",
    "examples": "Examples",
    "faq-new": "FAQ",
    "fine-tuning": "Fine-tuning, LoRA and evaluators",
    "fireworks-for-work": "Fireworks for Work",
    "getting-started": "Getting started",
    "guides": "Guides and optimization",
    "models": "Model library and model-specific docs",
    "serverless": "Serverless inference",
    "structured-responses": "Structured responses",
    "tools-sdks": "Tools, SDKs and protocol compatibility",
}

TRACK1_PRIORITY = {
    "serverless": "critical",
    "models": "critical",
    "api-reference": "high",
    "guides": "high",
    "fine-tuning": "medium",
    "deployments": "medium",
    "tools-sdks": "medium",
    "accounts": "low",
    "ecosystem": "low",
    "getting-started": "high",
}


@dataclass(frozen=True)
class FireworksDocPage:
    title: str
    url: str
    path: str
    group: str
    description: str
    priority: str

    @property
    def markdown_url(self) -> str:
        return self.url

    @property
    def page_url(self) -> str:
        if self.url.endswith(".md"):
            return self.url[:-3]
        return self.url


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a map of all official Fireworks docs pages from llms.txt.")
    parser.add_argument("--index-url", default=DEFAULT_INDEX_URL)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--print-summary", action="store_true")
    args = parser.parse_args()

    index_text = _fetch(args.index_url)
    pages = parse_index(index_text)
    if not pages:
        print("No Fireworks docs pages found in index.", file=sys.stderr)
        return 2

    args.markdown.parent.mkdir(parents=True, exist_ok=True)
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.markdown.write_text(render_markdown(pages, args.index_url), encoding="utf-8")
    args.json.write_text(
        json.dumps(
            {
                "source": args.index_url,
                "generated_at": date.today().isoformat(),
                "pages": [asdict(page) | {"page_url": page.page_url} for page in pages],
                "groups": group_summary(pages),
            },
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    summary = {
        "source": args.index_url,
        "pages": len(pages),
        "groups": len({page.group for page in pages}),
        "markdown": str(args.markdown),
        "json": str(args.json),
    }
    if args.print_summary:
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


def parse_index(text: str) -> list[FireworksDocPage]:
    pattern = re.compile(
        r"^- \[(?P<title>[^\]]+)\]\((?P<url>https://docs\.fireworks\.ai/(?P<path>[^)]+?\.md))\):\s*(?P<desc>.*)$",
        re.MULTILINE,
    )
    pages: list[FireworksDocPage] = []
    seen: set[str] = set()
    for match in pattern.finditer(text):
        path = match.group("path")
        if path in seen:
            continue
        seen.add(path)
        group = path.split("/", 1)[0] if "/" in path else "_root"
        pages.append(
            FireworksDocPage(
                title=_clean(match.group("title")),
                url=match.group("url"),
                path=path,
                group=group,
                description=_clean(match.group("desc")),
                priority=TRACK1_PRIORITY.get(group, "low"),
            )
        )
    return sorted(pages, key=lambda page: (page.group, page.path, page.title))


def render_markdown(pages: list[FireworksDocPage], index_url: str) -> str:
    grouped: dict[str, list[FireworksDocPage]] = defaultdict(list)
    for page in pages:
        grouped[page.group].append(page)

    lines = [
        "# Fireworks Docs Map",
        "",
        f"- official_index: `{index_url}`",
        f"- generated_at: `{date.today().isoformat()}`",
        f"- pages: `{len(pages)}`",
        f"- groups: `{len(grouped)}`",
        "",
        "## Strategic Reading Order",
        "",
        "1. `getting-started` for product surface and mental model.",
        "2. `serverless`, `models`, `api-reference` and `guides` for Track 1 runtime calls.",
        "3. `fine-tuning` for router fine-tuning and LoRA boundaries.",
        "4. `deployments` only if the official harness permits deployment IDs.",
        "5. `tools-sdks`, `ecosystem` and `accounts` for integration and operations.",
        "",
        "## Fireworks Capability Map",
        "",
        "| Capability | Docs groups | Track 1 use |",
        "|---|---|---|",
        "| OpenAI-compatible inference | `serverless`, `api-reference`, `tools-sdks` | Main scored path through `FIREWORKS_BASE_URL` and `ALLOWED_MODELS`. |",
        "| Model routing and selection | `models`, `guides`, `serverless` | Choose cheapest sufficient model after local zero-token gates. |",
        "| Structured outputs and strict formats | `structured-responses`, `api-reference`, `guides` | Reduce invalid JSON/code/number outputs before fallback. |",
        "| Embeddings and reranking | `models`, `api-reference`, `guides` | Useful outside Track 1 unless hidden tasks need retrieval; not default. |",
        "| Fine-tuning and evaluators | `fine-tuning`, `api-reference` | Fine-tune/calibrate router; LoRA responder only if allowed by harness. |",
        "| Dedicated deployments | `deployments`, `fine-tuning` | Useful for product workloads; risky for Track 1 unless `ALLOWED_MODELS` includes deployment IDs. |",
        "| SDK and compatibility layers | `tools-sdks`, `ecosystem` | Make integration easier; keep official Docker path minimal. |",
        "| Billing and governance | `accounts` | Credit control, cost exports, service accounts. |",
        "",
        "## Group Summary",
        "",
        "| Group | Label | Pages | Track 1 Priority |",
        "|---|---|---:|---|",
    ]
    counts = Counter(page.group for page in pages)
    for group in sorted(grouped):
        lines.append(
            f"| `{group}` | {GROUP_LABELS.get(group, group)} | {counts[group]} | {TRACK1_PRIORITY.get(group, 'low')} |"
        )

    lines.extend(
        [
            "",
            "## Complete Page Inventory",
            "",
            "Each link below points to the Fireworks markdown copy-page endpoint for LLM use.",
            "",
        ]
    )
    for group in sorted(grouped):
        lines.extend(
            [
                f"### {GROUP_LABELS.get(group, group)}",
                "",
                "| Title | Path | Priority | Description |",
                "|---|---|---|---|",
            ]
        )
        for page in grouped[group]:
            title = _escape_table(page.title)
            desc = _escape_table(page.description)
            lines.append(
                f"| [{title}]({page.markdown_url}) | `{page.path}` | `{page.priority}` | {desc} |"
            )
        lines.append("")
    return "\n".join(lines)


def group_summary(pages: list[FireworksDocPage]) -> dict[str, dict[str, object]]:
    grouped: dict[str, list[FireworksDocPage]] = defaultdict(list)
    for page in pages:
        grouped[page.group].append(page)
    return {
        group: {
            "label": GROUP_LABELS.get(group, group),
            "pages": len(group_pages),
            "priority": TRACK1_PRIORITY.get(group, "low"),
        }
        for group, group_pages in sorted(grouped.items())
    }


def _fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "track1-token-router-docs-mapper/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def _escape_table(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
