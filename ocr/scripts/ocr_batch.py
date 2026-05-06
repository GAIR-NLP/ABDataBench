#!/usr/bin/env python3
"""
MinerU official token API batch OCR script.

This replaces the previous self-hosted MinerU HTTP backend flow and keeps the
same output layout expected by the rest of the repository.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from mineru_official_api import (
    BACKEND_OFFICIAL_API,
    BACKEND_SELF_HOSTED,
    DEFAULT_BACKEND,
    DEFAULT_API_BASE_URL,
    DEFAULT_LANGUAGE,
    DEFAULT_SELF_HOSTED_MODEL,
    DEFAULT_TASK_TIMEOUT,
    normalize_self_hosted_url,
    resolve_backend,
    normalize_api_base_url,
    run_ocr,
)


SUPPORTED_EXTENSIONS = {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".jpg", ".jpeg", ".png"}
CONVERTIBLE_EXTENSIONS = {".doc", ".docx", ".ppt", ".pptx"}


def collect_files(input_path: str) -> list[str]:
    input_path = os.path.abspath(input_path)

    if os.path.isfile(input_path):
        ext = Path(input_path).suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            print(f"[WARN] Unsupported file: {input_path} (supported: {SUPPORTED_EXTENSIONS})")
            return []
        return [input_path]

    if os.path.isdir(input_path):
        files = []
        for root, _, filenames in os.walk(input_path):
            for fname in sorted(filenames):
                if Path(fname).suffix.lower() in SUPPORTED_EXTENSIONS:
                    files.append(os.path.join(root, fname))
        return files

    print(f"[ERROR] Path not found: {input_path}")
    return []


def convert_to_pdf_in_temp(file_path: str, temp_dir: str) -> str:
    src = Path(file_path)
    work_input = Path(temp_dir) / src.name
    shutil.copy2(src, work_input)

    result = subprocess.run(
        [
            "libreoffice",
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            temp_dir,
            str(work_input),
        ],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    if result.returncode != 0:
        details = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"LibreOffice conversion failed for {file_path}: {details[:800]}")

    pdf_path = Path(temp_dir) / f"{src.stem}.pdf"
    if not pdf_path.is_file():
        raise RuntimeError(f"LibreOffice conversion finished but PDF is missing: {pdf_path}")
    return str(pdf_path)


def process_single_file(args_tuple) -> dict:
    (
        file_path,
        output_dir,
        backend,
        api_base_url,
        api_token,
        model_name,
        language,
        task_timeout,
        page_concurrency,
    ) = args_tuple
    try:
        resolved_backend = resolve_backend(backend)
        with tempfile.TemporaryDirectory(prefix="mineru_self_hosted_") as temp_dir:
            ocr_input = file_path
            if resolved_backend == BACKEND_SELF_HOSTED and Path(file_path).suffix.lower() in CONVERTIBLE_EXTENSIONS:
                print(f"[CONVERT] {file_path} -> PDF (self-hosted backend)")
                ocr_input = convert_to_pdf_in_temp(file_path, temp_dir)

            print(f"[OCR START] {file_path} [{resolved_backend}]")
            result = run_ocr(
                ocr_input,
                output_dir,
                backend=resolved_backend,
                api_base_url=api_base_url,
                api_token=api_token,
                model_name=model_name,
                language=language,
                task_timeout_sec=task_timeout,
                page_concurrency=page_concurrency,
            )
        result["file"] = file_path
        print(
            f"[OCR DONE] {file_path} -> {result['markdown_path']} "
            f"({result['elapsed']:.1f}s, backend={resolved_backend})"
        )
        return result
    except Exception as exc:
        return {
            "file": file_path,
            "success": False,
            "error": str(exc),
            "elapsed": 0,
            "markdown_path": None,
        }


def merge_markdowns(results: list[dict], output_file: str) -> None:
    successful = [item for item in results if item["success"] and item["markdown_path"]]

    with open(output_file, "w", encoding="utf-8") as out:
        for index, result in enumerate(successful):
            base_name = Path(result["file"]).stem
            content = Path(result["markdown_path"]).read_text(encoding="utf-8")
            out.write(f"# {base_name}\n\n")
            out.write(content)
            if index < len(successful) - 1:
                out.write("\n\n---\n\n")

    print(f"\n[MERGED] {len(successful)} files -> {output_file}")


def main() -> None:
    parser = argparse.ArgumentParser(description="MinerU official token API batch OCR")
    parser.add_argument("--input", required=True, help="Input file or directory")
    parser.add_argument("--output", default=None, help="Output directory (default: same as input)")
    parser.add_argument(
        "--backend",
        default=DEFAULT_BACKEND,
        choices=[BACKEND_OFFICIAL_API, BACKEND_SELF_HOSTED],
        help="OCR backend: official-api or self-hosted (default: official-api)",
    )
    parser.add_argument("--concurrency", type=int, default=4, help="File-level concurrency (default: 4)")
    parser.add_argument(
        "--page-concurrency",
        type=int,
        default=100,
        help="MinerU page-level concurrency for self-hosted mode; ignored for official-api",
    )
    parser.add_argument(
        "--server-url",
        default=None,
        help=(
            "Official API base URL override in official-api mode, or the self-hosted MinerU "
            "HTTP endpoint in self-hosted mode"
        ),
    )
    parser.add_argument("--api-base-url", default=None, help="Alias of --server-url")
    parser.add_argument("--api-key", default=None, help="MinerU API token (official or self-hosted)")
    parser.add_argument("--api-token", default=None, help="Alias of --api-key")
    parser.add_argument(
        "--model-name",
        default=None,
        help=f"Self-hosted model name label (default: {DEFAULT_SELF_HOSTED_MODEL})",
    )
    parser.add_argument("--language", default=DEFAULT_LANGUAGE, help="MinerU language setting (default: ch)")
    parser.add_argument("--task-timeout", type=int, default=DEFAULT_TASK_TIMEOUT, help="Per-file timeout in seconds")
    parser.add_argument("--merge", default=None, help="Merge all outputs into a single markdown file")
    args = parser.parse_args()

    backend = resolve_backend(args.backend)
    raw_api_base_url = args.api_base_url or args.server_url
    api_base_url = (
        normalize_api_base_url(raw_api_base_url)
        if backend == BACKEND_OFFICIAL_API
        else (normalize_self_hosted_url(raw_api_base_url) if raw_api_base_url else None)
    )
    api_token = args.api_token or args.api_key

    files = collect_files(args.input)
    if not files:
        print("[ERROR] No supported files found.")
        sys.exit(1)

    print(f"[INFO] Found {len(files)} file(s) to process")
    print(f"[INFO] Backend: {backend}")
    print(f"[INFO] File concurrency: {args.concurrency}")
    print(f"[INFO] MinerU API base: {api_base_url}")
    if backend == BACKEND_SELF_HOSTED:
        print(f"[INFO] Self-hosted model name: {args.model_name or DEFAULT_SELF_HOSTED_MODEL}")

    input_path = os.path.abspath(args.input)
    if args.output:
        output_dir = os.path.abspath(args.output)
    elif os.path.isdir(input_path):
        output_dir = input_path
    else:
        output_dir = os.path.dirname(input_path)
    os.makedirs(output_dir, exist_ok=True)

    total_start = time.time()
    task_args = [
        (
            file_path,
            output_dir,
            backend,
            api_base_url,
            api_token,
            args.model_name,
            args.language,
            args.task_timeout,
            args.page_concurrency,
        )
        for file_path in files
    ]
    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        results = list(executor.map(process_single_file, task_args))

    total_elapsed = time.time() - total_start
    success_count = sum(1 for item in results if item["success"])
    fail_count = sum(1 for item in results if not item["success"])

    print(f"\n{'=' * 60}")
    print("OCR processing complete")
    print(f"{'=' * 60}")
    print(f"Total files: {len(files)}")
    print(f"Successful: {success_count}")
    print(f"Failed: {fail_count}")
    print(f"Elapsed: {total_elapsed:.1f}s")
    print()

    for result in results:
        status = "OK" if result["success"] else "FAIL"
        name = os.path.basename(result["file"])
        if result["success"]:
            size_kb = result.get("markdown_size", 0) / 1024
            print(f"  [{status}] {name} -> {result['markdown_path']} ({size_kb:.1f}KB, {result['elapsed']:.1f}s)")
        else:
            print(f"  [{status}] {name}: {(result.get('error') or 'Unknown')[:200]}")

    if args.merge and success_count > 0:
        merge_markdowns(results, os.path.abspath(args.merge))

    sys.exit(0 if fail_count == 0 else 1)


if __name__ == "__main__":
    main()
