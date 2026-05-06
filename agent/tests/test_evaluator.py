"""Tests for benchmark/scripts/evaluator.py — v3 scoring system."""

import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "benchmark", "scripts"))
from evaluator import (
    EVAL_FIELDS, CORE_FIELDS, STANDARD_FIELDS, AUXILIARY_FIELDS,
    get_field_weight, compute_penalty, is_empty, normalize, has_model_output,
    antibody_name_similarity, antibody_pair_similarity, match_antibodies_optimal,
    evaluate_unmatched, PaperScore, AntibodyScore, BenchmarkResult,
    generate_markdown_report, result_to_dict,
)


class TestFieldConfig(unittest.TestCase):
    """Test 22-field configuration."""

    def test_22_eval_fields(self):
        self.assertEqual(len(EVAL_FIELDS), 22)

    def test_field_weight_coverage(self):
        all_weighted = CORE_FIELDS | STANDARD_FIELDS | AUXILIARY_FIELDS
        self.assertEqual(all_weighted, set(EVAL_FIELDS))

    def test_core_count(self):
        self.assertEqual(len(CORE_FIELDS), 4)

    def test_standard_count(self):
        self.assertEqual(len(STANDARD_FIELDS), 9)

    def test_auxiliary_count(self):
        self.assertEqual(len(AUXILIARY_FIELDS), 9)

    def test_weights(self):
        self.assertEqual(get_field_weight("CDRH3_Sequence"), 2.0)
        self.assertEqual(get_field_weight("Binding_Kinetics_KD"), 2.0)
        self.assertEqual(get_field_weight("Target_Name"), 1.0)
        self.assertEqual(get_field_weight("Binding_EC50"), 1.0)
        self.assertEqual(get_field_weight("Structure"), 1.0)
        self.assertEqual(get_field_weight("source"), 0.5)
        self.assertEqual(get_field_weight("Antibody_Isotype"), 0.5)
        self.assertEqual(get_field_weight("Cross_Reactivity"), 0.5)
        self.assertEqual(get_field_weight("Thermal_Stability_Tm"), 0.5)

    def test_no_legacy_fields(self):
        legacy = {"Affinity_nM", "PK_source", "External_Database_ID"}
        for f in legacy:
            self.assertNotIn(f, EVAL_FIELDS)


class TestPenaltyFormula(unittest.TestCase):
    """Test continuous penalty formula: max(0, 1.0 - 0.01*NFP - 0.05*NFN)."""

    def test_perfect(self):
        self.assertEqual(compute_penalty(5, 5, 0, 0), 1.0)

    def test_one_miss(self):
        self.assertAlmostEqual(compute_penalty(5, 4, 1, 0), 0.95)

    def test_one_hallucination(self):
        self.assertAlmostEqual(compute_penalty(5, 5, 0, 1), 1.0)

    def test_mixed(self):
        self.assertAlmostEqual(compute_penalty(5, 4, 1, 2), 0.95)

    def test_ntp_zero(self):
        self.assertEqual(compute_penalty(5, 0, 5, 0), 0.0)

    def test_empty_correct(self):
        self.assertEqual(compute_penalty(0, 0, 0, 0), 1.0)

    def test_empty_hallucinate(self):
        self.assertEqual(compute_penalty(0, 0, 0, 3), 0.0)

    def test_clamp_to_zero(self):
        self.assertAlmostEqual(compute_penalty(10, 1, 9, 100), 0.35)

    def test_returns_float(self):
        result = compute_penalty(5, 5, 0, 0)
        self.assertIsInstance(result, float)


class TestPaperScoreNoGrade(unittest.TestCase):
    """Test PaperScore no longer has penalty_grade."""

    def test_no_penalty_grade(self):
        import dataclasses
        field_names = [f.name for f in dataclasses.fields(PaperScore)]
        self.assertNotIn("penalty_grade", field_names)
        self.assertIn("penalty_coeff", field_names)


class TestIsEmpty(unittest.TestCase):
    """Test empty value detection."""

    def test_empty_string(self):
        self.assertTrue(is_empty(""))

    def test_na(self):
        self.assertTrue(is_empty("N/A"))

    def test_not_reported(self):
        self.assertTrue(is_empty("not reported"))

    def test_chinese_empty(self):
        self.assertTrue(is_empty("未报道"))

    def test_normal_value(self):
        self.assertFalse(is_empty("6.91 nM"))

    def test_na_with_parens(self):
        self.assertTrue(is_empty("N/A (Light chain-devoid)"))

    def test_pointer_like_text_is_not_empty(self):
        self.assertFalse(is_empty("See Supplementary Table S6"))

    def test_explicit_null_statement_counts_as_output(self):
        self.assertTrue(has_model_output("未提供（仅给出长度 15 aa）"))

    def test_blank_string_is_not_output(self):
        self.assertFalse(has_model_output(""))


class TestAntibodyNameSimilarity(unittest.TestCase):
    def test_exact_match(self):
        self.assertEqual(antibody_name_similarity("mAb-123", "mAb-123"), 1.0)

    def test_case_insensitive(self):
        self.assertEqual(antibody_name_similarity("MAB-123", "mab-123"), 1.0)

    def test_substring(self):
        self.assertGreaterEqual(antibody_name_similarity("Ab1", "Ab1-variant"), 0.9)

    def test_compact_suffix_variant_is_lower_than_exact(self):
        self.assertLess(antibody_name_similarity("L9", "L9K"), 0.9)

    def test_completely_different(self):
        self.assertLess(antibody_name_similarity("Alpha", "ZetaGamma"), 0.5)

    def test_empty(self):
        self.assertEqual(antibody_name_similarity("", "Ab1"), 0.0)


class TestMatchAntibodies(unittest.TestCase):
    def test_perfect_match(self):
        gt = [{"Antibody_Name": "Ab1"}, {"Antibody_Name": "Ab2"}]
        pred = [{"Antibody_Name": "Ab2"}, {"Antibody_Name": "Ab1"}]
        matched, unmatched, extra = match_antibodies_optimal(gt, pred)
        self.assertEqual(len(matched), 2)
        self.assertEqual(len(unmatched), 0)
        self.assertEqual(len(extra), 0)

    def test_unmatched_gt(self):
        gt = [{"Antibody_Name": "Ab1"}, {"Antibody_Name": "Ab2"}]
        pred = [{"Antibody_Name": "Ab1"}]
        matched, unmatched, extra = match_antibodies_optimal(gt, pred)
        self.assertEqual(len(matched), 1)
        self.assertEqual(len(unmatched), 1)

    def test_extra_pred(self):
        gt = [{"Antibody_Name": "Ab1"}]
        pred = [{"Antibody_Name": "Ab1"}, {"Antibody_Name": "Extra"}]
        matched, unmatched, extra = match_antibodies_optimal(gt, pred)
        self.assertEqual(len(matched), 1)
        self.assertEqual(len(extra), 1)

    def test_empty_gt(self):
        matched, unmatched, extra = match_antibodies_optimal([], [{"Antibody_Name": "X"}])
        self.assertEqual(len(matched), 0)
        self.assertEqual(len(extra), 1)

    def test_same_name_duplicates_use_target_context(self):
        gt = [
            {"Antibody_Name": "EV35-2", "Target_Name": "MPXV A35 clade IIb", "Antibody_Type": "IgG"},
            {"Antibody_Name": "EV35-2", "Target_Name": "VACV A33", "Antibody_Type": "IgG"},
        ]
        pred = [
            {"Antibody_Name": "EV35-2", "Target_Name": "VACV A33", "Antibody_Type": "IgG"},
            {"Antibody_Name": "EV35-2", "Target_Name": "MPXV A35", "Antibody_Type": "IgG"},
        ]
        matched, unmatched, extra = match_antibodies_optimal(gt, pred)
        self.assertEqual(len(matched), 2)
        self.assertEqual(len(unmatched), 0)
        self.assertEqual(len(extra), 0)
        pairs = {(g["Target_Name"], p["Target_Name"]) for g, p in matched}
        self.assertIn(("VACV A33", "VACV A33"), pairs)

    def test_exact_name_beats_compact_suffix_variant(self):
        gt = [
            {"Antibody_Name": "L9", "Target_Name": "PfCSP", "Antibody_Type": "mAbs", "Experiment": "ITC,BLI,ELISA", "Structure": "7RQP"},
            {"Antibody_Name": "F10", "Target_Name": "PfCSP", "Antibody_Type": "mAbs", "Experiment": "ITC,BLI,ELISA"},
        ]
        pred = [
            {"Antibody_Name": "L9", "Target_Name": "PfCSP", "Antibody_Type": "IgG", "Experiment": "Flow Cytometry, ELISA, ITC, BLI", "Structure": "7RQP"},
            {"Antibody_Name": "F10", "Target_Name": "PfCSP", "Antibody_Type": "IgG", "Experiment": "Flow Cytometry, ELISA, ITC, BLI"},
            {"Antibody_Name": "L9K", "Target_Name": "PfCSP", "Experiment": "BLI,ELISA"},
            {"Antibody_Name": "F10K", "Target_Name": "PfCSP", "Experiment": "BLI,ELISA"},
        ]
        matched, unmatched, extra = match_antibodies_optimal(gt, pred)
        self.assertEqual(len(matched), 2)
        self.assertEqual(len(unmatched), 0)
        self.assertEqual({p["Antibody_Name"] for _, p in matched}, {"L9", "F10"})
        self.assertEqual({p["Antibody_Name"] for p in extra}, {"L9K", "F10K"})


class TestPairSimilarity(unittest.TestCase):
    def test_context_lowers_score_for_wrong_duplicate_target(self):
        gt = {"Antibody_Name": "EV35-2", "Target_Name": "MPXV A35 clade IIb", "Antibody_Type": "IgG"}
        pred_good = {"Antibody_Name": "EV35-2", "Target_Name": "MPXV A35", "Antibody_Type": "IgG"}
        pred_bad = {"Antibody_Name": "EV35-2", "Target_Name": "VACV A33", "Antibody_Type": "IgG"}
        self.assertGreater(
            antibody_pair_similarity(gt, pred_good),
            antibody_pair_similarity(gt, pred_bad),
        )


class TestEvaluateUnmatched(unittest.TestCase):
    def test_22_field_scores(self):
        gt_ab = {"Antibody_Name": "test", "Target_Name": "X", "Binding_Kinetics_KD": "5 nM"}
        result = evaluate_unmatched(gt_ab)
        self.assertEqual(len(result.field_scores), 22)
        self.assertFalse(result.matched)
        self.assertEqual(result.accuracy, 0.0)

    def test_miss_for_nonempty(self):
        gt_ab = {"Antibody_Name": "test", "Target_Name": "Spike"}
        result = evaluate_unmatched(gt_ab)
        target_fs = next(fs for fs in result.field_scores if fs.field_name == "Target_Name")
        self.assertEqual(target_fs.label, "miss")

    def test_skip_for_empty(self):
        gt_ab = {"Antibody_Name": "test", "Target_Name": ""}
        result = evaluate_unmatched(gt_ab)
        target_fs = next(fs for fs in result.field_scores if fs.field_name == "Target_Name")
        self.assertEqual(target_fs.label, "skip")


class TestBenchmarkMetadata(unittest.TestCase):
    def test_result_to_dict_includes_metadata(self):
        result = BenchmarkResult(accuracy=88.0, metadata={"subset": "patent", "gt_path": "x.json"})
        payload = result_to_dict(result)
        self.assertEqual(payload["metadata"]["subset"], "patent")

    def test_markdown_report_includes_subset_section(self):
        result = BenchmarkResult(accuracy=88.0, metadata={"subset": "paper", "gt_path": "gt.json"})
        report = generate_markdown_report(result)
        self.assertIn("## Evaluation Scope", report)
        self.assertIn("| subset | paper |", report)


if __name__ == "__main__":
    unittest.main()
