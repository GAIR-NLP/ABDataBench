"""Tests for benchmark/scripts/dataset_partition.py."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "benchmark", "scripts"))
from dataset_partition import annotate_categories, filter_ground_truth, infer_category, normalize_subset


class TestDatasetPartition(unittest.TestCase):
    def test_infer_category_for_patent_ids(self):
        self.assertEqual(infer_category("WO2016073890A1"), "patent")
        self.assertEqual(infer_category("US20080199481A1"), "patent")

    def test_infer_category_for_paper_titles(self):
        self.assertEqual(infer_category("Peng et al. mAbs 2015"), "paper")
        self.assertEqual(infer_category("Lei et al. Immunity 2023"), "paper")

    def test_normalize_subset_accepts_aliases(self):
        self.assertEqual(normalize_subset("papers"), "paper")
        self.assertEqual(normalize_subset("patents"), "patent")
        self.assertEqual(normalize_subset(None), "all")

    def test_annotate_categories_preserves_existing_values(self):
        gt = {
            "WO2016073890A1": {"paper_id": "WO2016073890A1", "category": "patent", "antibodies": []},
            "Paper A": {"paper_id": "Paper A", "antibodies": []},
        }
        annotated = annotate_categories(gt)
        self.assertEqual(annotated["WO2016073890A1"]["category"], "patent")
        self.assertEqual(annotated["Paper A"]["category"], "paper")

    def test_filter_ground_truth_by_subset(self):
        gt = {
            "WO2016073890A1": {"paper_id": "WO2016073890A1", "antibodies": []},
            "Peng et al. mAbs 2015": {"paper_id": "Peng et al. mAbs 2015", "antibodies": []},
        }
        patents = filter_ground_truth(gt, "patent")
        papers = filter_ground_truth(gt, "paper")
        self.assertEqual(list(patents.keys()), ["WO2016073890A1"])
        self.assertEqual(list(papers.keys()), ["Peng et al. mAbs 2015"])


if __name__ == "__main__":
    unittest.main()
