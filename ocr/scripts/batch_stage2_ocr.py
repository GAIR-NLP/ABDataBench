#!/usr/bin/env python3
"""Batch stage-2 OCR for paper directories that already contain <paper>.md and images/."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from mineru_official_api import (
    BACKEND_OFFICIAL_API,
    BACKEND_SELF_HOSTED,
    DEFAULT_BACKEND,
    DEFAULT_SELF_HOSTED_MODEL,
)


SCRIPT_DIR = Path(__file__).resolve().parent


def discover_papers(root: Path) -> list[dict]:
    papers = []
    for paper_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        md_path = paper_dir / f"{paper_dir.name}.md"
        images_dir = paper_dir / "images"
        output_md = paper_dir / "images_ocr_merged.md"
        if not md_path.is_file() or not images_dir.is_dir():
            continue
        image_count = sum(1 for p in images_dir.iterdir() if p.is_file())
        papers.append(
            {
                "paper": paper_dir.name,
                "paper_dir": str(paper_dir),
                "md": str(md_path),
                "images_dir": str(images_dir),
                "output_md": str(output_md),
                "done": output_md.exists(),
                "image_count": image_count,
            }
        )
    return papers


def run_one(
    paper: dict,
    concurrency: int,
    page_concurrency: int,
    backend: str,
    api_base_url: str | None,
    api_token: str | None,
    model_name: str | None,
) -> dict:
    paper_dir = Path(paper["paper_dir"])
    output_md = Path(paper["output_md"])
    ocr_output_dir = paper_dir / "images_ocr"
    started_at = time.time()
    with tempfile.TemporaryDirectory(prefix="ocr_stage2_clean_") as tmp:
        tmpdir = Path(tmp)
        sanitized_md = tmpdir / Path(paper["md"]).name
        sanitize_cmd = [
            sys.executable,
            str(SCRIPT_DIR / "sanitize_markdown.py"),
            "--input",
            paper["md"],
            "--output",
            str(sanitized_md),
        ]
        sanitize_proc = subprocess.run(sanitize_cmd, text=True, capture_output=True)
        if sanitize_proc.returncode != 0:
            proc = sanitize_proc
        else:
            cmd = [
                sys.executable,
                str(SCRIPT_DIR / "ocr_images_postprocess_merged.py"),
                "--md",
                str(sanitized_md),
                "--images-dir",
                paper["images_dir"],
                "--output",
                str(output_md),
                "--ocr-output-dir",
                str(ocr_output_dir),
                "--concurrency",
                str(concurrency),
                "--page-concurrency",
                str(page_concurrency),
                "--backend",
                backend,
                *(["--api-base-url", api_base_url] if api_base_url else []),
                *(["--api-token", api_token] if api_token else []),
                *(["--model-name", model_name] if model_name else []),
            ]
            proc = subprocess.run(cmd, text=True, capture_output=True)
    duration = round(time.time() - started_at, 2)
    return {
        "paper": paper["paper"],
        "returncode": proc.returncode,
        "duration_sec": duration,
        "output_md": str(output_md),
        "ocr_output_dir": str(ocr_output_dir),
        "source_md": paper["md"],
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch stage-2 OCR over per-paper directories.")
    parser.add_argument("--root", required=True, help="Root directory containing one subdirectory per paper")
    parser.add_argument("--concurrency", type=int, default=6, help="Image-level concurrency for stage-2 OCR")
    parser.add_argument("--page-concurrency", type=int, default=100, help="MinerU page-level concurrency")
    parser.add_argument(
        "--backend",
        default=DEFAULT_BACKEND,
        choices=[BACKEND_OFFICIAL_API, BACKEND_SELF_HOSTED],
        help="OCR backend: official-api or self-hosted (default: official-api)",
    )
    parser.add_argument("--server-url", default=None, help="Official API base URL or self-hosted MinerU endpoint URL")
    parser.add_argument("--api-base-url", default=None, help="Alias of --server-url")
    parser.add_argument("--api-key", default=None, help="MinerU API token (official or self-hosted)")
    parser.add_argument("--api-token", default=None, help="Alias of --api-key")
    parser.add_argument(
        "--model-name",
        default=None,
        help=f"Self-hosted model name label (default: {DEFAULT_SELF_HOSTED_MODEL})",
    )
    parser.add_argument("--force", action="store_true", help="Re-run even if images_ocr_merged.md exists")
    parser.add_argument(
        "--status-json",
        default=None,
        help="Optional path to write batch status JSON",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        raise SystemExit(f"Root not found: {root}")

    papers = discover_papers(root)
    pending = [p for p in papers if args.force or not p["done"]]
    print(f"Discovered {len(papers)} papers; pending {len(pending)}", flush=True)

    api_base_url = args.api_base_url or args.server_url
    api_token = args.api_token or args.api_key

    results = []
    for idx, paper in enumerate(pending, start=1):
        print(
            f"[{idx}/{len(pending)}] {paper['paper']} | images={paper['image_count']}",
            flush=True,
        )
        result = run_one(
            paper,
            args.concurrency,
            args.page_concurrency,
            args.backend,
            api_base_url,
            api_token,
            args.model_name,
        )
        results.append(result)
        status = "OK" if result["returncode"] == 0 else "FAIL"
        print(
            f"[{idx}/{len(pending)}] {status} {paper['paper']} | {result['duration_sec']}s",
            flush=True,
        )
        if args.status_json:
            status_path = Path(args.status_json).resolve()
            status_path.parent.mkdir(parents=True, exist_ok=True)
            status_path.write_text(
                json.dumps(
                    {
                        "root": str(root),
                        "papers": papers,
                        "results": results,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

    failures = [r for r in results if r["returncode"] != 0]
    print(
        f"Completed {len(results)} papers | success={len(results) - len(failures)} | fail={len(failures)}",
        flush=True,
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
