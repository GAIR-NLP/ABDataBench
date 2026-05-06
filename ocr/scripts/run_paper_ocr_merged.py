#!/usr/bin/env python3
"""Run the merged stage-1 OCR flow for one paper directory or one source file."""

from __future__ import annotations

import argparse
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


SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
    ".jpg",
    ".jpeg",
    ".png",
}

OCR_BATCH = str(Path(__file__).resolve().parent / "ocr_batch.py")


def collect_input_files(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path] if input_path.suffix.lower() in SUPPORTED_EXTENSIONS else []

    if not input_path.is_dir():
        raise SystemExit(f"Input not found: {input_path}")

    return sorted(
        p
        for p in input_path.iterdir()
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    )


def copy_inputs(files: list[Path], temp_input_dir: Path) -> list[Path]:
    copied = []
    for src in files:
        dst = temp_input_dir / src.name
        shutil.copy2(src, dst)
        copied.append(dst)
    return copied


def write_manifest(files: list[Path], manifest_path: Path) -> None:
    manifest_path.write_text(
        "".join(f"{path.name}\n" for path in files),
        encoding="utf-8",
    )


def aggregate_images(output_dir: Path) -> int:
    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    copied = 0
    for image_path in sorted(output_dir.glob("*/vlm/images/*")):
        if not image_path.is_file():
            continue
        target = images_dir / image_path.name
        if target.exists():
            continue
        shutil.copy2(image_path, target)
        copied += 1
    return copied


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def run_stage1(cmd: list[str], base_md: Path) -> None:
    result = subprocess.run(cmd, check=False)
    if result.returncode == 0:
        return
    if base_md.is_file():
        print(
            f"[WARN] Stage 1 returned rc={result.returncode} but produced {base_md.name}; continuing with partial OCR output.",
            flush=True,
        )
        return
    raise subprocess.CalledProcessError(result.returncode, cmd)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the merged stage-1 OCR flow for one paper directory."
    )
    parser.add_argument("--input", required=True, help="One paper directory or one source file")
    parser.add_argument("--output", required=True, help="Per-paper output directory")
    parser.add_argument(
        "--concurrency",
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
    parser.add_argument(
        "--server-url",
        default=None,
        help="Official API base URL or self-hosted MinerU endpoint URL",
    )
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

    input_path = Path(args.input).resolve()
    output_dir = Path(args.output).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    paper_name = input_path.stem if input_path.is_file() else input_path.name
    base_md = output_dir / f"{paper_name}.md"
    manifest_path = output_dir / "input_manifest.txt"

    source_files = collect_input_files(input_path)
    if not source_files:
        raise SystemExit(f"No supported top-level input files found under: {input_path}")

    with tempfile.TemporaryDirectory(prefix="ocr_clean_input_") as temp_input:
        temp_input_dir = Path(temp_input)

        copied_files = copy_inputs(source_files, temp_input_dir)
        write_manifest(copied_files, manifest_path)

        run_stage1(
            [
                sys.executable,
                OCR_BATCH,
                "--input",
                str(temp_input_dir),
                "--output",
                str(output_dir),
                "--concurrency",
                str(args.concurrency),
                "--page-concurrency",
                str(args.page_concurrency),
                "--backend",
                args.backend,
                "--merge",
                str(base_md),
                *(["--api-base-url", api_base_url] if api_base_url else []),
                *(["--api-token", api_token] if api_token else []),
                *(["--model-name", args.model_name] if args.model_name else []),
            ],
            base_md,
        )

        image_count = aggregate_images(output_dir)
        print(
            f"Stage-1 OCR merged into {base_md.name}; aggregated {image_count} extracted image(s) into images/",
            flush=True,
        )

    print(f"Final merged markdown: {base_md}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
