"""Tests for file utility helpers."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.file_utils import FileUtils


class TestPaperIdFromPath(unittest.TestCase):
    def test_generic_merged_markdown_uses_parent_dir(self):
        path = "/tmp/Fantin et al. Cell 2025/images_ocr_merged.md"
        self.assertEqual(FileUtils.paper_id_from_path(path), "Fantin et al. Cell 2025")

    def test_regular_markdown_uses_stem(self):
        path = "/tmp/papers/fimmu-15-1374913.md"
        self.assertEqual(FileUtils.paper_id_from_path(path), "fimmu-15-1374913")


if __name__ == "__main__":
    unittest.main()
