#!/usr/bin/env python3
"""Remove forbidden benchmark/external Excel supplement blocks from markdown."""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path


def forbidden_excel_names() -> tuple[str, ...]:
    configured = os.environ.get("OCR_FORBIDDEN_EXCEL_NAMES", "")
    return tuple(name.strip() for name in configured.split(",") if name.strip())


def strip_forbidden_excel_blocks(text: str) -> tuple[str, int]:
    removed = 0
    cleaned = text
    for name in forbidden_excel_names():
        pattern = re.compile(
            rf"(?ms)^# Excel Supplement: {re.escape(name)}.*?(?=^# |\Z)"
        )
        cleaned, count = pattern.subn("", cleaned)
        removed += count
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).rstrip() + "\n"
    return cleaned, removed


def main() -> int:
    parser = argparse.ArgumentParser(description="Strip forbidden Excel supplement blocks from markdown.")
    parser.add_argument("--input", required=True, help="Input markdown path")
    parser.add_argument("--output", required=True, help="Output markdown path")
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()
    text = input_path.read_text(encoding="utf-8", errors="ignore")
    cleaned, removed = strip_forbidden_excel_blocks(text)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(cleaned, encoding="utf-8")
    print(f"Removed {removed} forbidden Excel block(s) from {input_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
