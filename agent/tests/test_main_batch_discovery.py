"""Tests for batch markdown discovery preferences."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from main import discover_batch_markdowns


class TestBatchMarkdownDiscovery(unittest.TestCase):
    def test_prefers_images_ocr_merged_over_other_markdowns(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paper = root / "Fantin et al. Cell 2025"
            paper.mkdir()
            (paper / "Fantin et al. Cell 2025.md").write_text("orig", encoding="utf-8")
            (paper / "Fantin et al. Cell 2025_enhanced.md").write_text("enhanced", encoding="utf-8")
            (paper / "images_ocr_merged.md").write_text("merged", encoding="utf-8")

            found = discover_batch_markdowns(str(root))

            self.assertEqual(found, [str(paper / "images_ocr_merged.md")])

    def test_prefers_enhanced_when_merged_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paper = root / "Paper A"
            paper.mkdir()
            (paper / "Paper A.md").write_text("orig", encoding="utf-8")
            (paper / "Paper A_enhanced.md").write_text("enhanced", encoding="utf-8")

            found = discover_batch_markdowns(str(root))

            self.assertEqual(found, [str(paper / "Paper A_enhanced.md")])

    def test_keeps_vlm_markdown_for_legacy_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paper = root / "legacy-paper"
            vlm = paper / "vlm"
            vlm.mkdir(parents=True)
            (vlm / "legacy-paper.md").write_text("legacy", encoding="utf-8")

            found = discover_batch_markdowns(str(root))

            self.assertEqual(found, [str(vlm / "legacy-paper.md")])


if __name__ == "__main__":
    unittest.main()
