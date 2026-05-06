"""Tests for conservative OCR repair stage."""

import asyncio
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import Config
from agents.ocr_repair_agent import OCRRepairAgent


class _FakeLLM:
    def __init__(self, payloads):
        self.payloads = list(payloads)

    async def chat(self, **kwargs):
        class _Resp:
            def __init__(self, content):
                self.content = content
                self.total_tokens = 123

        payload = self.payloads.pop(0)
        return _Resp(json.dumps(payload, ensure_ascii=False))

    @staticmethod
    def parse_json_response(text):
        return json.loads(text)


class TestOCRRepairAgent(unittest.TestCase):
    def test_disabled_returns_original_text(self):
        config = Config(mock_llm=True)
        config.enable_ocr_repair = False
        agent = OCRRepairAgent(config)
        context = {
            "paper_id": "paper-1",
            "current_phase": "ocr_repair",
            "markdown_text": "Table 3: SPR results\n\nWT  1.45",
        }

        result = asyncio.run(agent.execute(context))

        self.assertEqual(result.data["repaired_text"], context["markdown_text"])
        self.assertFalse(result.data["meta"]["used_repaired_text"])
        self.assertEqual(result.data["meta"]["reason"], "disabled")

    def test_repairs_formatting_when_protected_tokens_preserved(self):
        config = Config(mock_llm=True)
        config.enable_ocr_repair = True
        config.ocr_repair_min_chars = 1
        config.ocr_repair_chunk_chars = 500
        agent = OCRRepairAgent(
            config,
            llm=_FakeLLM(
                [
                    {
                        "changed": True,
                        "repaired_text": (
                            "Table 3: SPR results for mutant antibodies\n\n"
                            "<table><tr><td>WT</td><td>1.45</td></tr></table>"
                        ),
                        "edit_summary": ["joined broken title and table"],
                        "notes": "formatting repaired",
                    }
                ]
            ),
        )
        context = {
            "paper_id": "paper-1",
            "current_phase": "ocr_repair",
            "markdown_text": "Table 3: SPR results\nfor mutant antibodies\n\n<table><tr><td>WT</td><td>1.45</td></tr></table>",
        }

        result = asyncio.run(agent.execute(context))

        self.assertIn("SPR results for mutant antibodies", result.data["repaired_text"])
        self.assertTrue(result.data["meta"]["used_repaired_text"])
        self.assertEqual(result.data["meta"]["changed_chunks"], 1)

    def test_rejects_chunk_when_protected_tokens_change(self):
        config = Config(mock_llm=True)
        config.enable_ocr_repair = True
        config.ocr_repair_min_chars = 1
        config.ocr_repair_chunk_chars = 500
        original = "<table><tr><td>WT</td><td>1.45</td></tr></table>"
        agent = OCRRepairAgent(
            config,
            llm=_FakeLLM(
                [
                    {
                        "changed": True,
                        "repaired_text": "<table><tr><td>WT</td><td>145</td></tr></table>",
                        "edit_summary": ["normalized OCR digits"],
                        "notes": "unsafe numeric change",
                    }
                ]
            ),
        )
        context = {
            "paper_id": "paper-1",
            "current_phase": "ocr_repair",
            "markdown_text": original,
        }

        result = asyncio.run(agent.execute(context))

        self.assertEqual(result.data["repaired_text"], original)
        self.assertEqual(result.data["meta"]["protected_change_rejections"], 1)
        self.assertFalse(result.data["meta"]["used_repaired_text"])

    def test_allows_whitelisted_html_table_header_repair_only(self):
        config = Config(mock_llm=True)
        config.enable_ocr_repair = True
        config.ocr_repair_min_chars = 1
        config.ocr_repair_chunk_chars = 2000
        original = (
            "Table 3: SPR results for mutant antibodies\n\n"
            "<table><tr><td>Fen</td><td>Fe(Fe)</td><td>Fe(Fe)</td><td>Fe(Fe)(nM)</td>"
            "<td>Fe2(Fe)</td><td>Fe(Fe)</td><td>Fe2(Fe)</td></tr>"
            "<tr><td>WT</td><td>5.48</td><td>6.08</td><td>11.1</td><td>2.94</td><td>4.27</td><td>1.45</td></tr>"
            "<tr><td>A28V/151T/S55G</td><td>8.08</td><td>2.91</td><td>3.6</td><td>3.85</td><td>1.45</td><td>0.40</td></tr></table>"
        )
        candidate = (
            "Table 3: SPR results for mutant antibodies\n\n"
            "<table><tr><th>Variant</th><th>ka1</th><th>kd1</th><th>KD1</th>"
            "<th>ka2</th><th>kd2</th><th>KD2</th></tr>"
            "<tr><td>WT</td><td>5.48</td><td>6.08</td><td>11.1</td><td>2.94</td><td>4.27</td><td>1.45</td></tr>"
            "<tr><td>A28V/151T/S55G</td><td>8.08</td><td>2.91</td><td>3.6</td><td>3.85</td><td>1.45</td><td>0.40</td></tr></table>"
        )
        agent = OCRRepairAgent(
            config,
            llm=_FakeLLM(
                [
                    {
                        "changed": True,
                        "repaired_text": candidate,
                        "edit_summary": ["restored canonical table headers"],
                        "notes": "header-only whitelist repair",
                    }
                ]
            ),
        )
        context = {
            "paper_id": "paper-1",
            "current_phase": "ocr_repair",
            "markdown_text": original,
        }

        result = asyncio.run(agent.execute(context))

        self.assertEqual(result.data["repaired_text"], candidate)
        self.assertTrue(result.data["meta"]["used_repaired_text"])
        self.assertEqual(result.data["meta"]["changed_chunks"], 1)

    def test_rejects_table_repair_when_body_row_changes(self):
        config = Config(mock_llm=True)
        config.enable_ocr_repair = True
        config.ocr_repair_min_chars = 1
        config.ocr_repair_chunk_chars = 2000
        original = (
            "<table><tr><td>Fen</td><td>Fe(Fe)</td></tr>"
            "<tr><td>A28V/151T/S55G</td><td>1.45</td></tr></table>"
        )
        candidate = (
            "<table><tr><th>Variant</th><th>KD2</th></tr>"
            "<tr><td>A28V/I51T/S55G</td><td>1.45</td></tr></table>"
        )
        agent = OCRRepairAgent(
            config,
            llm=_FakeLLM(
                [
                    {
                        "changed": True,
                        "repaired_text": candidate,
                        "edit_summary": ["restored canonical table headers and fixed variant label"],
                        "notes": "unsafe body edit",
                    }
                ]
            ),
        )
        context = {
            "paper_id": "paper-1",
            "current_phase": "ocr_repair",
            "markdown_text": original,
        }

        result = asyncio.run(agent.execute(context))

        self.assertEqual(result.data["repaired_text"], original)
        self.assertEqual(result.data["meta"]["protected_change_rejections"], 1)


if __name__ == "__main__":
    unittest.main()
