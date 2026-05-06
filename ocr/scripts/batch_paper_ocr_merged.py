#!/usr/bin/env python3
"""Batch runner for the paper-level merged stage-1 OCR flow."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import subprocess
import sys
import time
from pathlib import Path

from mineru_official_api import (
    BACKEND_OFFICIAL_API,
    BACKEND_SELF_HOSTED,
    DEFAULT_BACKEND,
    DEFAULT_SELF_HOSTED_MODEL,
)


RUN_PAPER_OCR = str(Path(__file__).resolve().parent / "run_paper_ocr_merged.py")


def discover_papers(root: Path) -> list[Path]:
    return sorted(p for p in root.iterdir() if p.is_dir())


def run_one(
    paper_dir: Path,
    output_root: Path,
    image_concurrency: int,
    page_concurrency: int,
    backend: str,
    api_base_url: str | None,
    api_token: str | None,
    model_name: str | None,
) -> dict:
    paper_name = paper_dir.name
    output_dir = output_root / paper_name
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / "ocr_run.log"
    started_at = time.time()

    cmd = [
        sys.executable,
        RUN_PAPER_OCR,
        "--input",
        str(paper_dir),
        "--output",
        str(output_dir),
        "--concurrency",
        str(image_concurrency),
        "--page-concurrency",
        str(page_concurrency),
        "--backend",
        backend,
        *(["--api-base-url", api_base_url] if api_base_url else []),
        *(["--api-token", api_token] if api_token else []),
        *(["--model-name", model_name] if model_name else []),
    ]
    proc = subprocess.run(cmd, text=True, capture_output=True)
    log_path.write_text(proc.stdout + proc.stderr, encoding="utf-8")

    base_md = output_dir / f"{paper_name}.md"
    image_count = sum(1 for _ in (output_dir / "images").glob("*")) if (output_dir / "images").is_dir() else 0
    status = "OK" if proc.returncode == 0 and base_md.is_file() else "FAIL"

    return {
        "paper": paper_name,
        "returncode": proc.returncode,
        "status": status,
        "duration_sec": round(time.time() - started_at, 2),
        "base_md": str(base_md) if base_md.is_file() else "",
        "merged_md": str(base_md) if base_md.is_file() else "",
        "image_count": image_count,
        "log_path": str(log_path),
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }


def write_summary(output_root: Path, results: list[dict]) -> None:
    summary_tsv = output_root / "ocr_merged_summary.tsv"
    master_log = output_root / "ocr_merged_master.log"
    status_json = output_root / "ocr_merged_status.json"

    with summary_tsv.open("w", encoding="utf-8") as f:
        f.write("paper\tstatus\trc\tbase_md\tmerged_md\timage_count\tlog_path\n")
        for result in sorted(results, key=lambda item: item["paper"]):
            f.write(
                "\t".join(
                    [
                        result["paper"],
                        result["status"],
                        str(result["returncode"]),
                        result["base_md"],
                        result["merged_md"],
                        str(result["image_count"]),
                        result["log_path"],
                    ]
                )
                + "\n"
            )

    with master_log.open("w", encoding="utf-8") as f:
        for result in sorted(results, key=lambda item: item["paper"]):
            f.write(
                f"[{result['status']}] {result['paper']} rc={result['returncode']} "
                f"images={result['image_count']} {result['duration_sec']}s\n"
            )

    status_json.write_text(
        json.dumps(
            {
                "output_root": str(output_root),
                "results": sorted(results, key=lambda item: item["paper"]),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch paper-level merged stage-1 OCR runner.")
    parser.add_argument("--input-root", required=True, help="Root directory containing one subdirectory per paper")
    parser.add_argument("--output-root", required=True, help="Root directory for OCR outputs")
    parser.add_argument(
        "--paper-concurrency",
        type=int,
        default=10,
        help="How many papers to process in parallel (default: 10)",
    )
    parser.add_argument(
        "--image-concurrency",
        type=int,
        default=30,
        help="Image/file OCR concurrency used inside each paper (default: 30)",
    )
    parser.add_argument(
        "--page-concurrency",
        type=int,
        default=100,
        help="MinerU page-level concurrency (default: 100)",
    )
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
    parser.add_argument("--force", action="store_true", help="Re-run even if <paper>.md already exists")
    args = parser.parse_args()

    api_base_url = args.api_base_url or args.server_url
    api_token = args.api_token or args.api_key

    input_root = Path(args.input_root).resolve()
    output_root = Path(args.output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    if not input_root.is_dir():
        raise SystemExit(f"Input root not found: {input_root}")

    papers = discover_papers(input_root)
    pending = [
        paper_dir
        for paper_dir in papers
        if args.force or not (output_root / paper_dir.name / f"{paper_dir.name}.md").is_file()
    ]
    print(f"Discovered {len(papers)} papers; pending {len(pending)}", flush=True)

    results: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.paper_concurrency) as executor:
        future_to_paper = {
            executor.submit(
                run_one,
                paper_dir,
                output_root,
                args.image_concurrency,
                args.page_concurrency,
                args.backend,
                api_base_url,
                api_token,
                args.model_name,
            ): paper_dir.name
            for paper_dir in pending
        }
        for future in concurrent.futures.as_completed(future_to_paper):
            result = future.result()
            results.append(result)
            print(
                f"[{result['status']}] {result['paper']} rc={result['returncode']} "
                f"images={result['image_count']} {result['duration_sec']}s",
                flush=True,
            )
            write_summary(output_root, results)

    failures = [result for result in results if result["status"] != "OK"]
    print(
        f"Completed {len(results)} papers | success={len(results) - len(failures)} | fail={len(failures)}",
        flush=True,
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
