import asyncio
import os
import sys
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.extract.table_extract_agent import TableExtractAgent
from tools.table_parser import TableParser


PATENT_SEQUENCE_TABLE = """
<table>
  <tr><td>Antibody portion</td><td>SEQ ID NO</td><td colspan="5"></td></tr>
  <tr><td>31C3 VL</td><td>3</td><td>MSVPTQVLGLSSLAWYQQKQF/SSLKINSLQP</td><td>LLLWLTGARCGKSPQLLVYNEDFGTYYCQH</td><td>DIQMTQSPASAKTLAEGVPSHYGTPPTFGG</td><td>LSASVGETVRRFSGSGSGTQGTKLEIK</td><td>ITCRASENIY</td></tr>
  <tr><td>31C3 VH</td><td>2</td><td>MGWSWIFLFLYYMHWVKQSHELHSLTSEDS</td><td>LSGTAGVLSEVKSLEWIGRIAVYYCARSGG</td><td>VQLQQSGPELPNYNGATSYNNTYFDYWGQG</td><td>VKPGASVKISRNFKDKASLTTTLTVS</td><td>CKPSGYSFTAVDKSSSTAYM</td></tr>
  <tr><td rowspan="3">34A3 VH</td><td rowspan="3">34</td><td>MEWRWIFLFL</td><td>LSGTTGVHSE</td><td>IQLQQSGPEL</td><td>VKPGASVKVS</td><td>CKASGYVFTT</td></tr>
  <tr><td>YSIYWVKQSH</td><td>GKSLEWIGYI</td><td>DPYNGDTSYN</td><td>QKFKGKATLT</td><td>VDKSSSTAYM</td></tr>
  <tr><td>HLNSLTSEDS</td><td>TVYYCAREGN</td><td>YYGYFDYWGQ</td><td>GTTLTVS</td><td></td></tr>
</table>
"""


class TestTableParserPatentSequenceTables(unittest.TestCase):
    def setUp(self):
        self.parser = TableParser()
        self.table = self.parser.extract_html_tables(PATENT_SEQUENCE_TABLE)[0]

    def test_detects_patent_sequence_fragment_table_without_parentheses(self):
        self.assertTrue(self.parser._detect_sequence_fragment_table(self.table))

    def test_assembles_single_row_patent_sequences_row_major(self):
        records = self.parser._assemble_sequence_fragment_records(self.table)
        by_key = {
            (record["mAb"], "VH_sequence" if "VH_sequence" in record else "VL_sequence"): record
            for record in records
        }

        # Row-major: concatenate cells left-to-right within each row
        self.assertEqual(
            by_key[("31C3", "VH_sequence")]["VH_sequence"],
            "MGWSWIFLFLYYMHWVKQSHELHSLTSEDSLSGTAGVLSEVKSLEWIGRIAVYYCARSGGVQLQQSGPELPNYNGATSYNNTYFDYWGQGVKPGASVKISRNFKDKASLTTTLTVSCKPSGYSFTAVDKSSSTAYM",
        )
        self.assertTrue(
            by_key[("31C3", "VL_sequence")]["VL_sequence"].startswith("MSVPTQVLGLSSLAWYQQKQF")
        )

    def test_assembles_multi_row_patent_sequences_row_major(self):
        records = self.parser._assemble_sequence_fragment_records(self.table)
        by_key = {
            (record["mAb"], "VH_sequence" if "VH_sequence" in record else "VL_sequence"): record
            for record in records
        }

        self.assertEqual(
            by_key[("34A3", "VH_sequence")]["VH_sequence"],
            "MEWRWIFLFLLSGTTGVHSEIQLQQSGPELVKPGASVKVSCKASGYVFTTYSIYWVKQSHGKSLEWIGYIDPYNGDTSYNQKFKGKATLTVDKSSSTAYMHLNSLTSEDSTVYYCAREGNYYGYFDYWGQGTTLTVS",
        )

    def test_table_extract_agent_emits_reconstructed_sequences(self):
        agent = TableExtractAgent(SimpleNamespace(trace_recorder=None))
        result = asyncio.run(
            agent.execute(
                {
                    "markdown_text": PATENT_SEQUENCE_TABLE,
                    "paper_id": "WO2011004028A2",
                    "current_phase": "extract",
                }
            )
        )

        records = result.data["table_records"]
        by_key = {
            (record["mAb"], "VH_sequence" if "VH_sequence" in record else "VL_sequence"): record
            for record in records
            if record.get("mAb") in {"31C3", "34A3"} and ("VH_sequence" in record or "VL_sequence" in record)
        }

        self.assertIn(("31C3", "VH_sequence"), by_key)
        self.assertIn(("31C3", "VL_sequence"), by_key)
        self.assertIn(("34A3", "VH_sequence"), by_key)
        self.assertTrue(by_key[("31C3", "VH_sequence")]["VH_sequence"].startswith("MGWSWIFLFLYYMHWVKQSH"))

