"""Tests for tools/fetch_chain_info.py."""

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.fetch_chain_info import fetch_results, format_chain_info, format_text_output


class TestFetchChainInfoFormatting(unittest.TestCase):
    def test_format_chain_info(self):
        info = {
            "accession": "PQ382870",
            "normalized_from": "PQ_382870",
            "chain_type": "VH",
            "location": "1..360",
            "product": "immunoglobulin heavy chain variable region",
            "protein_id": "AAA00001.1",
            "translation": "QVQLQESG",
        }
        text = format_chain_info(info)
        self.assertIn("accession: PQ382870", text)
        self.assertIn("normalized_from: PQ_382870", text)
        self.assertIn("chain_type: VH", text)
        self.assertIn("translation: QVQLQESG", text)

    def test_format_text_output_for_multiple_chains(self):
        results = {
            "PQ382870": [
                {"accession": "PQ382870", "chain_type": "VH", "location": "1..360", "product": "heavy", "protein_id": "A1", "translation": "QVQL"},
                {"accession": "PQ382870", "chain_type": "VL", "location": "361..690", "product": "light", "protein_id": "A2", "translation": "DIQM"},
            ]
        }
        text = format_text_output(results, preferred_chain=None)
        self.assertIn("PQ382870", text)
        self.assertIn("chain_type: VH", text)
        self.assertIn("chain_type: VL", text)

    def test_format_text_output_for_missing_preferred_chain(self):
        text = format_text_output({"PQ382871": None}, preferred_chain="VL")
        self.assertIn("no VL chain found", text)

    def test_format_text_output_for_error_payload(self):
        text = format_text_output({"PQ382871": {"accession": "PQ382871", "error": "HTTP 400"}}, preferred_chain=None)
        self.assertIn("error: HTTP 400", text)

    @patch("tools.fetch_chain_info.APIClient")
    def test_fetch_results_preserves_raw_accession_for_client_and_normalizes_result_key(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_client_cls.normalize_accession.return_value = "MK749197"
        mock_client.fetch_genbank_chain_infos.return_value = {
            "accession": "MK749197",
            "normalized_from": "MK_749197",
            "chain_type": "VH",
        }

        results = fetch_results(["MK_749197"], preferred_chain=None, email="", api_key="")

        mock_client.fetch_genbank_chain_infos.assert_called_once_with("MK_749197", preferred_chain=None)
        self.assertIn("MK749197", results)
        self.assertEqual(results["MK749197"]["normalized_from"], "MK_749197")
