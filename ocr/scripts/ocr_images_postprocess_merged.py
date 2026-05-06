#!/usr/bin/env python3
"""Run stage-2 image OCR for one merged markdown plus one explicit images directory."""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from mineru_official_api import (
    BACKEND_OFFICIAL_API,
    BACKEND_SELF_HOSTED,
    DEFAULT_BACKEND,
    DEFAULT_SELF_HOSTED_MODEL,
)


SCRIPT_DIR = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(
        description="Stage-2 OCR for one merged markdown and one explicit images directory."
    )
    parser.add_argument("--md", required=True, help="Merged markdown path")
    parser.add_argument("--images-dir", required=True, help="Directory containing images/")
    parser.add_argument("--output", default=None, help="Enhanced markdown output path")
    parser.add_argument("--ocr-output-dir", default=None, help="Intermediate images_ocr output dir")
    parser.add_argument("--concurrency", type=int, default=10, help="File-level concurrency")
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
    args = parser.parse_args()

    api_base_url = args.api_base_url or args.server_url
    api_token = args.api_token or args.api_key

    md_path = Path(args.md).resolve()
    images_dir = Path(args.images_dir).resolve()
    if not md_path.is_file():
        raise SystemExit(f"Markdown not found: {md_path}")
    if not images_dir.is_dir():
        raise SystemExit(f"Images directory not found: {images_dir}")

    output_path = Path(args.output).resolve() if args.output else md_path.with_name(f"{md_path.stem}_enhanced.md")
    ocr_output_dir = (
        Path(args.ocr_output_dir).resolve()
        if args.ocr_output_dir
        else md_path.parent / "images_ocr"
    )
    ocr_output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="ocr_stage2_") as tmp:
        tmpdir = Path(tmp)
        tmp_md = tmpdir / md_path.name
        tmp_images = tmpdir / "images"

        shutil.copy2(md_path, tmp_md)
        os.symlink(images_dir, tmp_images)

        cmd = [
            sys.executable,
            str(SCRIPT_DIR / "ocr_images_postprocess.py"),
            "--md",
            str(tmp_md),
            "--output",
            str(output_path),
            "--ocr-output-dir",
            str(ocr_output_dir),
            "--concurrency",
            str(args.concurrency),
            "--page-concurrency",
            str(args.page_concurrency),
            "--backend",
            args.backend,
            *(["--api-base-url", api_base_url] if api_base_url else []),
            *(["--api-token", api_token] if api_token else []),
            *(["--model-name", args.model_name] if args.model_name else []),
        ]
        subprocess.run(cmd, check=True)

    print(f"Enhanced markdown written to {output_path}")


if __name__ == "__main__":
    main()
