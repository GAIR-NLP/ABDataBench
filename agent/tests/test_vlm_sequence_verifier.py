"""Tests for agent/tools/vlm_sequence_verifier.py."""

import asyncio
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.vlm_sequence_verifier import (
    resolve_sequence_image_record_path,
    verify_sequence_image_records_with_vlm,
)


class _FakeVLMResponse:
    def __init__(self, content: str):
        self.content = content


class _FakeVLMClient:
    def __init__(self, corrected_sequence: str):
        self.corrected_sequence = corrected_sequence
        self.calls = []

    async def chat_with_image(self, system, user_text, image_path, temperature, max_tokens):
        self.calls.append(
            {
                "user_text": user_text,
                "image_path": image_path,
            }
        )
        return _FakeVLMResponse(
            f'{{"corrected_sequence":"{self.corrected_sequence}","changes":2}}'
        )


class TestVLMSequenceVerifier(unittest.TestCase):
    def test_resolve_sequence_image_record_path_prefers_crop(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            crop_dir = os.path.join(tmpdir, "images_ocr", "abc123", "vlm", "images")
            os.makedirs(crop_dir, exist_ok=True)
            crop_path = os.path.join(crop_dir, "crop1.jpg")
            with open(crop_path, "wb") as handle:
                handle.write(b"fake")

            record = {
                "_source_image": "images/abc123.jpg",
                "_source_crop_image": "crop1.jpg",
            }
            resolved = resolve_sequence_image_record_path(tmpdir, record)
            self.assertEqual(resolved, crop_path)

    def test_verify_sequence_image_records_updates_sequences(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            crop_dir = os.path.join(tmpdir, "images_ocr", "abc123", "vlm", "images")
            os.makedirs(crop_dir, exist_ok=True)
            crop_path = os.path.join(crop_dir, "crop1.jpg")
            with open(crop_path, "wb") as handle:
                handle.write(b"fake")

            original = "Q" * 90
            corrected = "E" * 90
            records = [
                {
                    "mAb": "1C8-H3",
                    "VH_sequence": original,
                    "_source_image": "images/abc123.jpg",
                    "_source_crop_image": "crop1.jpg",
                }
            ]
            vlm = _FakeVLMClient(corrected)

            asyncio.run(verify_sequence_image_records_with_vlm(vlm, tmpdir, records))

            self.assertEqual(records[0]["VH_sequence"], corrected)
            self.assertEqual(records[0]["_vlm_corrections"]["VH"]["mode"], "sequence_image_verify")
            self.assertEqual(vlm.calls[0]["image_path"], crop_path)


if __name__ == "__main__":
    unittest.main()
