"""Tests for benchmark/scripts/llm_judge.py."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "benchmark", "scripts"))
from llm_judge import LLMJudge, extract_json_object, FIELD_SPECIAL_GUIDANCE


class _FailingClient:
    class _Chat:
        class _Completions:
            @staticmethod
            def create(**kwargs):
                raise AssertionError("LLM should not be called for rule-based sequence scoring")

        completions = _Completions()

    chat = _Chat()


class _CapturingClient:
    def __init__(self):
        self.last_kwargs = None

    class _Chat:
        def __init__(self, outer):
            self.outer = outer

        class _Completions:
            def __init__(self, outer):
                self.outer = outer

            def create(self, **kwargs):
                self.outer.last_kwargs = kwargs
                return type(
                    "Resp",
                    (),
                    {
                        "choices": [
                            type(
                                "Choice",
                                (),
                                {"message": type("Msg", (), {"content": '{"label":"exact","score":1.0,"reason":"ok"}'})()},
                            )()
                        ]
                    },
                )()

        @property
        def completions(self):
            return self._Completions(self.outer)

    @property
    def chat(self):
        return self._Chat(self)


class TestExtractJsonObject(unittest.TestCase):
    def test_extracts_trailing_json_after_explanation(self):
        text = (
            "比较两个序列，差异如下。\n\n"
            '{"label": "partial", "score": 0.5, "reason": "存在局部差异"}'
        )
        result = extract_json_object(text)
        self.assertEqual(result["label"], "partial")
        self.assertEqual(result["score"], 0.5)

    def test_extracts_json_inside_code_fence(self):
        text = '```json\n{"label": "exact", "score": 1.0, "reason": "ok"}\n```'
        result = extract_json_object(text)
        self.assertEqual(result["label"], "exact")


class TestSequenceRuleScoring(unittest.TestCase):
    def setUp(self):
        self.judge = LLMJudge(api_key="dummy", base_url="https://example.invalid", model="dummy-model")
        self.judge.client = _FailingClient()

    def test_identical_sequences_are_exact_without_llm(self):
        seq = "QVQLQQSGPGLVKPSQTLSLTCVISGDSVSSNTAAWDWIRQSPSRGLEWLGRTYYRSK"
        result = self.judge.judge_field("vh_sequence_aa", seq, seq)
        self.assertEqual(result["label"], "exact")
        self.assertEqual(result["score"], 1.0)

    def test_small_sequence_difference_is_partial_without_llm(self):
        gt = "QVQLQQSGPGLVKPSQTLSLTCVISGDSVSSNTAAWDWIRQSPSRGLEWLGRTYYRSKWYNDYAESVKSRITINPDTSK"
        pred = "QVQLQQSGPGLPGLKVPSQTLSLTCVISGDSVSSNTAAWDWIRQSPSRGLEWLGRTYYRSKWYNDYAESVKSRITINPDTSK"
        result = self.judge.judge_field("vh_sequence_aa", gt, pred)
        self.assertEqual(result["label"], "partial")
        self.assertEqual(result["score"], 0.5)
        self.assertIn("edit distance", result["reason"])

    def test_missing_predicted_sequence_is_wrong_without_llm(self):
        gt = "AIQLTQSPSSLSASVGDRVTITCRASQGANSYLAWYQQKPGKAPKLLIYAASTLQSGVPSRFSGSGSGTDFTLTISSLEPEDFATYYCQQYNSYPLTFGQGTKLEIK"
        result = self.judge.judge_field("vl_sequence_aa", gt, "")
        self.assertEqual(result["label"], "wrong")
        self.assertEqual(result["score"], 0.0)


class TestPromptGuidance(unittest.TestCase):
    def test_target_name_prompt_includes_field_specific_guidance(self):
        judge = LLMJudge(api_key="dummy", base_url="https://example.invalid", model="dummy-model")
        judge.client = _CapturingClient()

        result = judge.judge_field("Target_Name", "MPXV A35 clade IIb", "MPXV A35")
        self.assertEqual(result["label"], "exact")

        user_prompt = judge.client.last_kwargs["messages"][1]["content"]
        self.assertIn("Field-specific rule", user_prompt)
        self.assertIn("clade/subtype/strain/lineage/variant", user_prompt)

    def test_experiment_prompt_includes_superset_rule(self):
        judge = LLMJudge(api_key="dummy", base_url="https://example.invalid", model="dummy-model")
        judge.client = _CapturingClient()

        result = judge.judge_field("Experiment", "BLI,ELISA", "BLI, ELISA, SPR")
        self.assertEqual(result["label"], "exact")
        self.assertIn("Western blot", FIELD_SPECIAL_GUIDANCE["Experiment"])


class TestRuleBasedNonSequenceFields(unittest.TestCase):
    def setUp(self):
        self.judge = LLMJudge(api_key="dummy", base_url="https://example.invalid", model="dummy-model")
        self.judge.client = _FailingClient()

    def test_experiment_with_peripheral_extra_method_is_partial(self):
        result = self.judge.judge_field(
            "Experiment",
            "ITC, Flow Cytometry, ELISA",
            "ITC, Flow Cytometry, ELISA, Western blot",
        )
        self.assertEqual(result["label"], "partial")
        self.assertIn("peripheral methods", result["reason"])

    def test_antibody_type_relaxes_igg_subtype_to_major_class(self):
        result = self.judge.judge_field("Antibody_Type", "IgG", "Monoclonal IgG1")
        self.assertEqual(result["label"], "exact")

    def test_reference_source_matches_same_doi_despite_format(self):
        result = self.judge.judge_field(
            "Reference_Source",
            "Dacon et al. Science 2025",
            "Dacon et al. Science, 2025. DOI: 10.1126/science.adr0510",
        )
        self.assertEqual(result["label"], "exact")

    def test_reference_source_author_year_with_pred_only_doi_is_exact(self):
        result = self.judge.judge_field(
            "Reference_Source",
            "Fantin et al. Cell 2025",
            "Fantin et al. Fantin . Fantin, 2025. DOI: 10.1016/j.cell.2025.08.004",
        )
        self.assertEqual(result["label"], "exact")
        self.assertIn("DOI", result["reason"])

    def test_reference_source_conflicting_doi_stays_partial(self):
        result = self.judge.judge_field(
            "Reference_Source",
            "Fantin et al. Cell 2025. DOI: 10.1016/j.cell.2025.08.004",
            "Fantin et al. Cell 2025. DOI: 10.1016/j.cell.2025.08.999",
        )
        self.assertEqual(result["label"], "partial")
        self.assertIn("DOI conflicts", result["reason"])


if __name__ == "__main__":
    unittest.main()
