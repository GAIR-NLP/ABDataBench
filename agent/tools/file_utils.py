"""File I/O helpers."""

import json
import os
import logging

logger = logging.getLogger(__name__)


class FileUtils:

    @staticmethod
    def read_text(path: str) -> str:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()

    @staticmethod
    def write_json(path: str, data, indent: int = 2):
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
        logger.info(f"Saved: {path}")

    @staticmethod
    def write_text(path: str, data: str):
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(data)
        logger.info(f"Saved: {path}")

    @staticmethod
    def read_json(path: str):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    @staticmethod
    def ensure_dir(path: str):
        os.makedirs(path, exist_ok=True)

    @staticmethod
    def paper_id_from_path(md_path: str) -> str:
        """Infer `paper_id` from a Markdown path.

        Prefer the parent directory for generic filenames such as
        `images_ocr_merged.md`.
        """
        md_path = os.path.abspath(md_path)
        parent = os.path.basename(os.path.dirname(md_path))
        stem = os.path.splitext(os.path.basename(md_path))[0]
        generic_stems = {"index", "document", "doc", "paper", "images_ocr_merged", "merged"}
        if parent and stem.lower() in generic_stems:
            return parent
        if parent and stem.lower() == parent.lower().replace(".md", ""):
            return parent
        return stem
