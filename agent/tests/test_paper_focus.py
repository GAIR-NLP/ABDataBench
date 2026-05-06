import os
import sys
import asyncio
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.paper_focus_agent import PaperFocusAgent
from agents.skeleton_agent import SkeletonAgent
from config import Config
from tools.paper_focus import PaperFocusBuilder


class FakeConfig(Config):
    mock_llm: bool = True


class TestPaperFocusBuilder(unittest.TestCase):
    def setUp(self):
        self.builder = PaperFocusBuilder()

    def test_detects_table_supplement_and_control_risks(self):
        text = """
        Supplementary Table 1 lists antibody sequences. Supplementary Figure 2 shows alignment.
        Table 1 summarizes neutralization. Table 2 reports binding kinetics.
        Previously described control antibody S2E12 was used as control.
        We isolated antibody 2C08 and characterized its VH and VL sequences.
        """
        scan_results = {
            "tables": {"total_table_count": 4},
            "pdb_ids": [],
            "genbank": {"likely_genbank": []},
            "germline_genes": {"IMGT_V_genes": []},
            "cdr3_sequences": {"CDRH3_candidates": ["CARDRSTG"], "CDRL3_candidates": []},
            "antibody_name_candidates": ["S2E12", "2C08"],
        }

        focus = self.builder.analyze(text, scan_results)

        self.assertIn("table-heavy", focus["paper_type"])
        self.assertIn("supplement-heavy", focus["paper_type"])
        self.assertIn("mixed", focus["evidence_carriers"])
        self.assertIn("Table row extraction", focus["activated_modules"])
        self.assertTrue(any("evidence unit" in item.lower() for item in [focus["evidence_unit_policy"]]))
        self.assertTrue(any("control" in risk.lower() for risk in focus["entity_risks"]))
        self.assertIn("2C08", focus["priority_antibody_names"])
        self.assertIn("S2E12", focus["deprioritized_antibody_names"])
        self.assertIn("Activated modules", focus["paper_focus_text"])
        self.assertIn("Priority antibody names", focus["paper_focus_text"])


class TestSkeletonPromptInjection(unittest.TestCase):
    def setUp(self):
        self.agent = SkeletonAgent.__new__(SkeletonAgent)
        self.agent.name = "skeleton"
        self.agent.config = FakeConfig()
        self.agent.user_template = (
            "{REGEX_HINTS}\n\n"
            "[Paper ID]: {PAPER_ID}\n\n"
            "[Paper Focus Analysis]:\n{PAPER_FOCUS_ANALYSIS}\n\n"
            "[Document Text]:\n{DOCUMENT_TEXT}"
        )
        import logging
        self.agent.logger = logging.getLogger("test")

    def test_build_user_message_includes_paper_focus_block(self):
        context = {
            "paper_id": "paper1",
            "markdown_text": "body text",
            "regex_hints": {"regex_hints_text": "regex hints"},
            "paper_focus": {"paper_focus_text": "- Paper profile: table-heavy"},
        }

        user_msg = self.agent._build_user_message(context)

        self.assertIn("[Paper Focus Analysis]", user_msg)
        self.assertIn("table-heavy", user_msg)
        self.assertIn("regex hints", user_msg)
        self.assertIn("body text", user_msg)


class TestHardPaperFocusAnalyzer(unittest.TestCase):
    def test_hard_paper_uses_llm_refinement_by_default(self):
        agent = PaperFocusAgent(FakeConfig(mock_llm=True))
        context = {
            "paper_id": "paper-hard",
            "markdown_text": (
                "Supplementary Table 1 lists antibody sequences. Supplementary Table 2 reports KD, kon, and koff. "
                "Figure 3 shows structure and cross-reactive binding. Previously described control antibody S2E12 was used as control. "
                "We identified antibody 2C08 and antibody 2C11. Table 1 reports target-specific values. "
                "Lineage analysis includes germline and MRCA nodes plus engineered chimera constructs."
            ),
            "regex_hints": {
                "tables": {"total_table_count": 5},
                "pdb_ids": ["7XYZ"],
                "genbank": {"likely_genbank": ["PQ382870"]},
                "germline_genes": {"IMGT_V_genes": []},
                "cdr3_sequences": {"CDRH3_candidates": ["CARDRSTG"], "CDRL3_candidates": []},
                "antibody_name_candidates": ["S2E12", "2C08", "2C11"],
            },
            "current_phase": "paper_focus",
        }

        result = asyncio.run(agent.execute(context))

        self.assertTrue(result.metrics["hard_paper"])
        self.assertTrue(result.metrics["llm_focus_used"])
        self.assertGreaterEqual(result.metrics["llm_tokens"], 1)
        self.assertIn("llm_focus_analysis", result.data)
        self.assertIn("Hard-paper LLM refinement", result.data["paper_focus_text"])


if __name__ == "__main__":
    unittest.main()
