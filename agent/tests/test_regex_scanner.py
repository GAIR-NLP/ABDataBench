"""Tests for agent/tools/regex_scanner.py"""

import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tools.regex_scanner import RegexScanner


class TestPDBScan(unittest.TestCase):
    def setUp(self):
        self.scanner = RegexScanner()

    def test_find_pdb_ids(self):
        text = "The structure was deposited as 6WPT and 7XYZ in RCSB PDB."
        result = self.scanner.scan_pdb_ids(text)
        self.assertIn("6WPT", result)
        self.assertIn("7XYZ", result)

    def test_no_pdb_ids(self):
        text = "No structural data was deposited."
        result = self.scanner.scan_pdb_ids(text)
        self.assertEqual(len(result), 0)


class TestGermlineScan(unittest.TestCase):
    def setUp(self):
        self.scanner = RegexScanner()

    def test_imgt_v_genes(self):
        text = "The antibody uses IGHV1-3*01 and IGKV3-20*01 germline genes."
        result = self.scanner.scan_germline_genes(text)
        self.assertIn("IGHV1-3*01", result["IMGT_V_genes"])
        self.assertIn("IGKV3-20*01", result["IMGT_V_genes"])

    def test_short_v_genes(self):
        text = "Germline assignment: VH4-4/JH3"
        result = self.scanner.scan_germline_genes(text)
        self.assertIn("VH4-4", result["short_V_genes"])

    def test_vdj_combos(self):
        text = "The heavy chain uses VH4-4/DH1-26/JH3 rearrangement."
        result = self.scanner.scan_germline_genes(text)
        # Should find VH4-4/DH1-26/JH3 combo
        self.assertGreater(len(result["VDJ_combos"]), 0)


class TestCDR3Scan(unittest.TestCase):
    def setUp(self):
        self.scanner = RegexScanner()

    def test_labeled_cdrh3(self):
        text = "CDR-H3: CARDRSTGYYYYFDYW"
        result = self.scanner.scan_cdr3_sequences(text)
        self.assertIn("CARDRSTGYYYYFDYW", result["CDRH3_candidates"])

    def test_anchor_based_cdrh3(self):
        text = "The sequence CARDLQELGSLDYW was identified."
        result = self.scanner.scan_cdr3_sequences(text)
        self.assertIn("CARDLQELGSLDYW", result["CDRH3_candidates"])

    def test_exclude_common_words(self):
        text = "CORRESPONDENCE was noted in the document."
        result = self.scanner.scan_cdr3_sequences(text)
        self.assertNotIn("CORRESPONDENCE", result["CDRH3_candidates"])


class TestTableScan(unittest.TestCase):
    def setUp(self):
        self.scanner = RegexScanner()

    def test_html_table(self):
        text = "<table><tr><td>A</td></tr></table>"
        result = self.scanner.scan_tables(text)
        self.assertEqual(result["html_table_count"], 1)

    def test_markdown_table(self):
        text = "| A | B |\n| --- | --- |\n| 1 | 2 |"
        result = self.scanner.scan_tables(text)
        self.assertEqual(result["markdown_table_count"], 1)

    def test_no_tables(self):
        text = "Just plain text without any tables."
        result = self.scanner.scan_tables(text)
        self.assertEqual(result["total_table_count"], 0)


class TestAntibodyNameScan(unittest.TestCase):
    def setUp(self):
        self.scanner = RegexScanner()

    def test_mab_pattern(self):
        text = "mAb S309 was identified as a potent neutralizer."
        result = self.scanner.scan_antibody_names(text)
        self.assertIn("S309", result)

    def test_exclude_false_positives(self):
        text = "ELISA and FACS were used. COVID was studied."
        result = self.scanner.scan_antibody_names(text)
        self.assertNotIn("ELISA", result)
        self.assertNotIn("FACS", result)
        self.assertNotIn("COVID", result)

    def test_detects_short_and_dotted_antibody_names(self):
        text = "Sequence alignment of anti-MUC1 mAbs SM3, SN-101, and AR20.5."
        result = self.scanner.scan_antibody_names(text)
        self.assertIn("SM3", result)
        self.assertIn("AR20.5", result)

    def test_detects_letter_digit_lowercase_digit_antibody_names(self):
        text = (
            "A commercialized antibody, R387c6, did not compete with mAb 975 or mAb 981. "
            "Mpox virus antibody (R387c6) was purchased from OKayBio."
        )
        result = self.scanner.scan_antibody_names(text)
        self.assertIn("R387c6", result)


class TestScanAll(unittest.TestCase):
    def setUp(self):
        self.scanner = RegexScanner()

    def test_scan_all_returns_all_keys(self):
        text = "Sample text with PDB 6WPT and IGHV1-3*01."
        result = self.scanner.scan_all(text)
        expected_keys = [
            "file_size_chars", "pdb_ids", "genbank", "uniprot_ids",
            "germline_genes", "cdr3_sequences", "dois", "pmids",
            "tables", "antibody_name_candidates",
        ]
        for key in expected_keys:
            self.assertIn(key, result)

    def test_scan_all_separates_nucleotide_and_protein_accessions(self):
        text = "COVA1-16 used MT599835, MT599919 and QHD43416 as database accessions."
        result = self.scanner.scan_all(text)
        self.assertIn("MT599835", result["genbank"]["likely_nucleotide"])
        self.assertIn("MT599919", result["genbank"]["likely_nucleotide"])
        self.assertIn("QHD43416", result["genbank"]["likely_protein"])

    def test_scan_all_normalizes_common_accession_separator_variants(self):
        text = "Observed MK_749197, mk-749198 and QHD 43416.1 in OCR output."
        result = self.scanner.scan_all(text)
        self.assertIn("MK749197", result["genbank"]["likely_nucleotide"])
        self.assertIn("MK749198", result["genbank"]["likely_nucleotide"])
        self.assertIn("QHD43416", result["genbank"]["likely_protein"])


class TestFormatHints(unittest.TestCase):
    def setUp(self):
        self.scanner = RegexScanner()

    def test_format_hints_output(self):
        results = self.scanner.scan_all("PDB 6WPT found. CDR-H3: CARDRSTGYW")
        hints = self.scanner.format_hints(results)
        self.assertIn("[Regex Hints]:", hints)
        self.assertIn("PDB IDs:", hints)
        self.assertIn("6WPT", hints)


class TestSuggestRouting(unittest.TestCase):
    def setUp(self):
        self.scanner = RegexScanner()

    def test_routing_with_pdb(self):
        results = self.scanner.scan_all("PDB 6WPT found.")
        routes = self.scanner.suggest_routing(results)
        self.assertTrue(any("Track A" in r and "RCSB" in r for r in routes))

    def test_routing_without_external_ids(self):
        results = self.scanner.scan_all("No database IDs here.")
        routes = self.scanner.suggest_routing(results)
        self.assertTrue(any("Track A not applicable" in r for r in routes))


if __name__ == "__main__":
    unittest.main()
