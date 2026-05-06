#!/usr/bin/env python3
"""
Second-pass image OCR post-processing.

Runs MinerU OCR on the `images/` directory produced by stage 1 and injects the
recognized image text back into the original Markdown file.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
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


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def find_images_in_md(md_path: str) -> list[str]:
    content = Path(md_path).read_text(encoding="utf-8")
    pattern = r"!\[[^\]]*\]\((images/[^)]+)\)"
    return list(set(re.findall(pattern, content)))


def _ocr_single_image(args_tuple) -> dict:
    (
        image_path,
        output_dir,
        backend,
        api_base_url,
        api_token,
        model_name,
        language,
        task_timeout,
        page_concurrency,
    ) = args_tuple
    fname = os.path.basename(image_path)
    stem = Path(image_path).stem
    start = time.time()

    cached_md = os.path.join(output_dir, stem, "vlm", f"{stem}.md")
    if os.path.exists(cached_md):
        content = Path(cached_md).read_text(encoding="utf-8").strip()
        if content:
            return {
                "file": fname,
                "success": True,
                "content": content,
                "elapsed": 0,
                "cached": True,
            }

    try:
        result = run_ocr(
            image_path,
            output_dir,
            backend=backend,
            api_base_url=api_base_url,
            api_token=api_token,
            model_name=model_name,
            language=language,
            task_timeout_sec=task_timeout,
            page_concurrency=page_concurrency,
        )
        md_path = result["markdown_path"]
        if md_path and os.path.exists(md_path):
            content = Path(md_path).read_text(encoding="utf-8").strip()
            if content:
                return {
                    "file": fname,
                    "success": True,
                    "content": content,
                    "elapsed": time.time() - start,
                    "cached": False,
                }
        return {
            "file": fname,
            "success": False,
            "content": None,
            "elapsed": time.time() - start,
            "cached": False,
            "error": f"No markdown output produced for {fname}",
        }
    except Exception as exc:
        return {
            "file": fname,
            "success": False,
            "content": None,
            "elapsed": time.time() - start,
            "cached": False,
            "error": str(exc),
        }


def run_concurrent_ocr(
    image_dir: str,
    output_dir: str,
    backend: str,
    api_base_url: str,
    api_token: str,
    model_name: str | None,
    language: str,
    task_timeout: int,
    page_concurrency: int,
    concurrency: int,
) -> dict[str, str]:
    image_files = []
    for fname in sorted(os.listdir(image_dir)):
        if Path(fname).suffix.lower() in IMAGE_EXTENSIONS:
            image_files.append(os.path.join(image_dir, fname))

    if not image_files:
        return {}

    total = len(image_files)
    print(f"[OCR] {total} images, concurrency={concurrency}")

    task_args = [
        (
            image_path,
            output_dir,
            backend,
            api_base_url,
            api_token,
            model_name,
            language,
            task_timeout,
            page_concurrency,
        )
        for image_path in image_files
    ]

    ocr_results: dict[str, str] = {}
    done = 0
    cached = 0
    failed = 0

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        future_map = {executor.submit(_ocr_single_image, args): args[0] for args in task_args}
        for future in as_completed(future_map):
            done += 1
            result = future.result()
            fname = result["file"]
            if result["success"]:
                ocr_results[fname] = result["content"]
                if result.get("cached"):
                    cached += 1
            else:
                failed += 1
            if done % 20 == 0 or done == total:
                print(f"  [{done}/{total}] success={len(ocr_results)} cached={cached} skipped={failed}")

    return ocr_results


def inject_ocr_into_md(md_path: str, ocr_results: dict[str, str], output_path: str) -> int:
    content = Path(md_path).read_text(encoding="utf-8")
    lines = content.split("\n")
    new_lines = []
    injected_count = 0

    pattern = re.compile(r"!\[[^\]]*\]\((images/([^)]+))\)")

    for line in lines:
        new_lines.append(line)
        match = pattern.search(line)
        if not match:
            continue
        img_filename = match.group(2)
        if img_filename not in ocr_results:
            continue
        ocr_text = ocr_results[img_filename]
        ocr_lines = [
            current
            for current in ocr_text.split("\n")
            if not re.match(r"\s*!\[[^\]]*\]\([^)]+\)\s*$", current)
        ]
        ocr_text_clean = "\n".join(ocr_lines).strip()
        if not ocr_text_clean:
            continue
        new_lines.append("")
        new_lines.append(f"<!-- OCR extracted from {img_filename} -->")
        new_lines.append(ocr_text_clean)
        new_lines.append("<!-- end OCR -->")
        injected_count += 1

    Path(output_path).write_text("\n".join(new_lines), encoding="utf-8")
    return injected_count


def main() -> None:
    parser = argparse.ArgumentParser(description="Run second-pass OCR on images and inject text into Markdown.")
    parser.add_argument("--md", required=True, help="Original Markdown file path")
    parser.add_argument("--output", default=None, help="Enhanced Markdown output path (default: <stem>_enhanced.md)")
    parser.add_argument("--ocr-output-dir", default=None, help="OCR intermediate output directory (default: images_ocr/)")
    parser.add_argument(
        "--backend",
        default=DEFAULT_BACKEND,
        choices=[BACKEND_OFFICIAL_API, BACKEND_SELF_HOSTED],
        help="OCR backend: official-api or self-hosted (default: official-api)",
    )
    parser.add_argument("--concurrency", type=int, default=10, help="File-level concurrency (default: 10)")
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
    parser.add_argument("--task-timeout", type=int, default=DEFAULT_TASK_TIMEOUT, help="Per-image timeout in seconds")
    args = parser.parse_args()

    backend = resolve_backend(args.backend)
    raw_api_base_url = args.api_base_url or args.server_url
    api_base_url = (
        normalize_api_base_url(raw_api_base_url)
        if backend == BACKEND_OFFICIAL_API
        else (normalize_self_hosted_url(raw_api_base_url) if raw_api_base_url else None)
    )
    api_token = args.api_token or args.api_key

    md_path = os.path.abspath(args.md)
    if not os.path.isfile(md_path):
        print(f"[ERROR] File not found: {md_path}")
        sys.exit(1)

    md_dir = os.path.dirname(md_path)
    md_stem = Path(md_path).stem
    image_dir = os.path.join(md_dir, "images")
    if not os.path.isdir(image_dir):
        print(f"[ERROR] Image directory not found: {image_dir}")
        sys.exit(1)

    output_path = os.path.abspath(args.output) if args.output else os.path.join(md_dir, f"{md_stem}_enhanced.md")
    ocr_output_dir = args.ocr_output_dir or os.path.join(md_dir, "images_ocr")
    os.makedirs(ocr_output_dir, exist_ok=True)

    img_refs = find_images_in_md(md_path)
    img_count = sum(1 for fname in os.listdir(image_dir) if Path(fname).suffix.lower() in IMAGE_EXTENSIONS)
    print(f"[INFO] Markdown references {len(img_refs)} images; image directory contains {img_count} images")
    print(f"[INFO] Backend: {backend}")
    print(f"[INFO] MinerU API base: {api_base_url}")
    if backend == BACKEND_SELF_HOSTED:
        print(f"[INFO] Self-hosted model name: {args.model_name or DEFAULT_SELF_HOSTED_MODEL}")

    start_time = time.time()
    ocr_results = run_concurrent_ocr(
        image_dir,
        ocr_output_dir,
        backend,
        api_base_url,
        api_token,
        args.model_name,
        args.language,
        args.task_timeout,
        args.page_concurrency,
        args.concurrency,
    )
    elapsed = time.time() - start_time
    print(f"[INFO] OCR complete: {len(ocr_results)}/{img_count} images contain text ({elapsed:.1f}s)")

    injected = inject_ocr_into_md(md_path, ocr_results, output_path)

    print(f"\n{'=' * 60}")
    print("Second-pass image OCR post-processing complete")
    print(f"{'=' * 60}")
    print(f"Original Markdown: {md_path}")
    print(f"Enhanced Markdown: {output_path}")
    print(f"Concurrency:       {args.concurrency}")
    print(f"Total images:      {img_count}")
    print(f"Images with text:  {len(ocr_results)}")
    print(f"Injected blocks:   {injected}")
    print(f"Elapsed:           {elapsed:.1f}s")

    original_size = os.path.getsize(md_path)
    enhanced_size = os.path.getsize(output_path)
    print(f"Original size:     {original_size / 1024:.1f} KB")
    print(f"Enhanced size:     {enhanced_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
