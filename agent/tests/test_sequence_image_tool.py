"""Tests for agent/tools/sequence_image_tool.py."""

import asyncio
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.sequence_image_tool import SequenceImageTool


class TestSequenceImageToolHelpers(unittest.TestCase):
    def setUp(self):
        self.tool = SequenceImageTool.__new__(SequenceImageTool)
        self.tool.NAME_LINE_RE = SequenceImageTool.NAME_LINE_RE
        self.tool.SEQUENCE_CONTEXT_KEYWORDS = SequenceImageTool.SEQUENCE_CONTEXT_KEYWORDS
        self.tool.OCR_SEQUENCE_KEYWORDS = SequenceImageTool.OCR_SEQUENCE_KEYWORDS
        self.tool.OCR_NON_SEQUENCE_KEYWORDS = SequenceImageTool.OCR_NON_SEQUENCE_KEYWORDS
        self.tool.SEQUENCE_RE = SequenceImageTool.SEQUENCE_RE

    def test_detects_sequence_alignment_context(self):
        context = "Figure S1. Sequence alignment of anti-MUC1 mAbs SM3, SN-101, and AR20.5. ![](images/x.jpg)"
        self.assertTrue(self.tool._looks_like_sequence_image(context))

    def test_plaintext_parser_handles_h_and_l_chain_blocks(self):
        text = (
            "SM3\n"
            "H chain: VQLQESGGGLVQPGGSMKLSCVASGFTFSNYWMNWVRQSPEKGLEWVAEIRLKSNNYATHYAESVKGRFTISRDDSKSSVYLQMNNLRAEDTGIYYCTGVGQFAYWGQGTTVTVSIVVT\n"
            "L chain: LTTSPGETVTLTCRSSTGAVTTSNYANWVQEKPDHLFTGLIGGTNNRAPGVPARFSGSLIGDKAALTITGAQTEDEAIYFCALWYSNHWVFGGGTKLTV\n"
        )
        records = self.tool._parse_plaintext_blocks(text)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["mAb"], "SM3")
        self.assertTrue(records[0]["VH_sequence"].startswith("VQLQESGGGLVQPGGS"))
        self.assertTrue(records[0]["VL_sequence"].startswith("LTTSPGETVTLTCRSS"))

    def test_plaintext_parser_handles_chinese_chain_labels(self):
        text = (
            "AR20.5\n"
            "H链: VKLVESGGLVAPGGSLKLSCAASGFTFSSYPMSWVRQTPEKRLEWVAYINNGG--NPYYPDTVKGRFTISRDNAKNTLYLQMSSLKSEDTAIYYCIRQYYGFDYWGQGTTLTVSSAKT\n"
            "L链: DVLMTQTPLSLPVSLGDQASISCRSSQTIVHSNGKIYLEWYLQKPGQSPKLLIYRVSKRFSGVPDRFSGSGSGTDFTLKISRVEAEDLGVYYCFQGSHVPWTFGGGTKLEI\n"
        )
        records = self.tool._parse_plaintext_blocks(text)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["mAb"], "AR20.5")
        self.assertIn("QYYGFDYWGQGTTLTVSSAKT", records[0]["VH_sequence"])

    def test_clean_sequence_preserves_gap_but_removes_noise(self):
        value = " VKLVESGGGLVAPGG--SLKLS*CAAS "
        self.assertEqual(
            self.tool._clean_sequence(value),
            "VKLVESGGGLVAPGG--SLKLSCAAS",
        )

    def test_reads_configured_max_output_tokens(self):
        class DummyConfig:
            sequence_vlm_api_base = "https://api.opensii.ai"
            sequence_vlm_api_key = "sk-test"
            sequence_vlm_model = "gzy/gemini-3.1-pro"
            sequence_vlm_timeout = 120
            sequence_vlm_concurrency = 2
            sequence_vlm_max_images = 8
            sequence_vlm_top_k_images = 5
            sequence_vlm_max_output_tokens = 10000

        tool = SequenceImageTool(DummyConfig())
        self.assertEqual(tool.max_output_tokens, 10000)

    def test_system_prompt_contains_multi_panel_assignment_rules(self):
        class DummyConfig:
            sequence_vlm_api_base = "https://api.opensii.ai"
            sequence_vlm_api_key = "sk-test"
            sequence_vlm_model = "gzy/gemini-3.1-pro"
            sequence_vlm_timeout = 120
            sequence_vlm_concurrency = 1
            sequence_vlm_max_images = 8
            sequence_vlm_top_k_images = 5
            sequence_vlm_max_output_tokens = 4000
            llm_api_base = "https://api.opensii.ai"
            llm_api_key = "sk-test"

        tool = SequenceImageTool(DummyConfig())
        self.assertIn("F4.30/C6.11", tool.system_prompt)
        self.assertIn("不要把仅用于对比的行标签误当成新的抗体", tool.system_prompt)
        self.assertIn("不要把重链序列写进 `VL_sequence`", tool.system_prompt)
        self.assertIn("CDRH3", tool.system_prompt)

    def test_select_top_relevant_candidates_prefers_seed_and_sequence_context(self):
        self.tool.top_k_images = 2
        candidates = [
            {"rel_path": "images/fig1.jpg", "context": "random microscopy panel"},
            {"rel_path": "images/fig2.jpg", "context": "Figure 2 sequence alignment of Ab1 heavy chain and light chain CDR"},
            {"rel_path": "images/fig3.jpg", "context": "Supplementary sequence alignment for Ab2 and Ab3"},
        ]
        selected = self.tool._select_top_relevant_candidates(candidates, ["Ab1"])
        self.assertEqual(len(selected), 2)
        self.assertEqual(selected[0]["rel_path"], "images/fig2.jpg")
        self.assertEqual(selected[1]["rel_path"], "images/fig3.jpg")

    def test_detects_alignment_ocr_block_without_literal_sequence_keywords(self):
        context = (
            "Figure 3B\n"
            "<!-- OCR extracted from image -->\n"
            "2C08\nS2E12\nC121\nREGN10987\n"
            "EVQLVQSGPEVKKPGTSVRVSCKASGFTFTSSAVQWVRQARGQRLEWIGWVISPSSGGTNYAQKFQGRVTITADESTSTAYMELSSLRSEDTAVYYCARTAGRGGWYFDLWGQGTLVTVSS\n"
            "................................................................................................................................................\n"
            "...A............................................................................................................................................\n"
            ".................Y.............................................................................................................................\n"
            "........................................T......................................................................................................\n"
            "<!-- end OCR -->\n"
        )
        self.assertTrue(self.tool._looks_like_sequence_image(context))

    def test_rejects_non_sequence_image_when_only_neighbor_caption_mentions_sequence(self):
        context = (
            "Supplementary Fig. 9 Comparison of antibody sequences to the germline sequence.\n"
            "![](images/not-seq.jpg)\n"
        )
        ocr_text = "Anti-strep\nMw (KDa)\n+/- PNGase F"
        self.assertFalse(self.tool._looks_like_sequence_image(context, ocr_text))

    def test_extract_image_ocr_text_prefers_exact_image_block(self):
        md_text = (
            "![](images/a.jpg)\n"
            "<!-- OCR extracted from a.jpg -->\n"
            "Heavy chain\n"
            "<!-- end OCR -->\n"
            "![](images/b.jpg)\n"
            "<!-- OCR extracted from b.jpg -->\n"
            "Anti-strep\n"
            "<!-- end OCR -->\n"
        )
        ocr_a = self.tool._extract_image_ocr_text(md_text, "a.jpg", md_text.find("a.jpg"))
        ocr_b = self.tool._extract_image_ocr_text(md_text, "b.jpg", md_text.find("b.jpg"))
        self.assertEqual(ocr_a, "Heavy chain")
        self.assertEqual(ocr_b, "Anti-strep")

    def test_extract_alignment_ocr_records_reconstructs_full_vh_sequence(self):
        reference = "EVQLVQSGPEVKKPGTSVRVSCKASGFTFTSSAVQWVRQARGQRLEWIGWVISPSSGGTNYAQKFQGRVTITADESTSTAYMELSSLRSEDTAVYYCARTAGRGGWYFDLWGQGTLVTVSS"
        dots = "." * len(reference)
        context = (
            "<!-- OCR extracted from image -->\n"
            "2C08\nS2E12\nC121\nREGN10987\n"
            f"{reference}\n"
            f"{dots}\n"
            f"{dots}\n"
            f"{dots}\n"
            f"{dots}\n"
            "<!-- end OCR -->\n"
        )
        records = self.tool._extract_alignment_ocr_records(context)
        by_name = {record["mAb"]: record for record in records}
        self.assertEqual(by_name["2C08"]["VH_sequence"], reference)
        self.assertEqual(by_name["S2E12"]["VH_sequence"], reference)

    def test_extract_alignment_ocr_records_accepts_small_variant_cluster(self):
        reference = "QVQLVESGGGLVQPGGSLRLSCSVSGSLFSSYAISWVRQAPGIGYEYVSAISIGDPTYYWDSVKGRFTISRDNSKVTVYLQMNSLRAEDTAVYYCARSYPGNGDLGRLDIWGQGTTVTVSS"
        diff = "." * len(reference)
        context = (
            "Figure 2C humanized variant sequences alignment\n"
            "<!-- OCR extracted from image -->\n"
            "1C8-H3\n"
            "1C8-H4\n"
            f"{reference}\n"
            f"{diff}\n"
            f"{diff}\n"
            "<!-- end OCR -->\n"
        )
        records = self.tool._extract_alignment_ocr_records(context)
        by_name = {record["mAb"]: record for record in records}
        self.assertEqual(by_name["1C8-H3"]["VH_sequence"], reference)
        self.assertEqual(by_name["1C8-H4"]["VH_sequence"], reference)

    def test_extract_alignment_ocr_records_parses_name_followed_by_sequence_pairs(self):
        vh = "QVQLVESGGGLVQPGGSLRLSCSVSGSLFSSYAISWVRQAPGIGYEYVSAISIGDPTYYWDSVKGRFTISRDNSKVTVYLQMNSLRAEDTAVYYCARSYPGNGDLGRLDIWGQGTTVTVSS"
        vl = "DIQLTQSPSFLSASVGDRVTITCQSSQSVYRNKYLSWYQQKPGKAPKLLIYYASTAQSGVPSRFSGSGSGTEFTLTISSLQPEDFATYYCAGDYSDDIENAFGQGTKVEIK"
        context = (
            "<!-- OCR extracted from image -->\n"
            "1C8-H3\n"
            f"{vh}\n"
            "1C8-L1\n"
            f"{vl}\n"
            "<!-- end OCR -->\n"
        )
        records = self.tool._extract_alignment_ocr_records(context)
        by_name = {record["mAb"]: record for record in records}
        self.assertEqual(by_name["1C8-H3"]["VH_sequence"], vh)
        self.assertEqual(by_name["1C8-L1"]["VL_sequence"], vl)

    def test_targeted_retry_triggers_for_sparse_alignment_with_crops(self):
        refs = [
            {
                "rel_path": "images/fig.jpg",
                "source_rel_path": "images/fig.jpg",
                "context": "Figure 2C, amino acid sequence alignments of VH and Vk of the humanized variant sequences.",
            },
            {
                "rel_path": "images/fig.jpg#crop:a",
                "source_rel_path": "images/fig.jpg",
                "crop_image_name": "crop-a.jpg",
                "context": "Figure 2C, amino acid sequence alignments of VH and Vk of the humanized variant sequences.",
            },
            {
                "rel_path": "images/fig.jpg#crop:b",
                "source_rel_path": "images/fig.jpg",
                "crop_image_name": "crop-b.jpg",
                "context": "Figure 2C, amino acid sequence alignments of VH and Vk of the humanized variant sequences.",
            },
        ]
        self.assertTrue(
            self.tool._has_alignment_retry_signal(
                refs,
                [],
                ["1C8"],
            )
        )

    def test_extract_from_markdown_uses_targeted_retry_for_sparse_alignment(self):
        tool = SequenceImageTool.__new__(SequenceImageTool)
        tool.max_images = 30
        tool.top_k_images = 30
        tool.parallel_limit = 1
        tool.retry_count = 1
        tool._semaphore = None
        tool._total_calls = 0
        tool._total_tokens = 0

        base_ref = {
            "rel_path": "images/fig.jpg",
            "source_rel_path": "images/fig.jpg",
            "abs_path": "/tmp/fig.jpg",
            "context": "Figure 2C, amino acid sequence alignments of VH and Vk of the humanized variant sequences.",
            "ocr_text": "",
        }
        crop_h = {
            **base_ref,
            "rel_path": "images/fig.jpg#crop:h",
            "crop_image_name": "crop-h.jpg",
        }
        crop_l = {
            **base_ref,
            "rel_path": "images/fig.jpg#crop:l",
            "crop_image_name": "crop-l.jpg",
        }

        tool._scan_images = lambda markdown_text, base_dir: [base_ref]
        tool._looks_like_sequence_image = lambda context, ocr_text="": True
        tool._select_top_relevant_candidates = lambda candidates, seed_names: candidates
        tool._expand_candidate_crop_variants = lambda candidates: [base_ref, crop_h, crop_l]
        tool._extract_alignment_ocr_records = lambda context: []

        async def fake_extract_records_with_user_text(ref, user_text):
            if "上一次抽取结果明显不完整" in user_text:
                if ref.get("crop_image_name") == "crop-h.jpg":
                    return [{"mAb": "1C8-H3", "VH_sequence": "QVQLVESGGGLVQPGGSLRLSCSVSGSLFSSYAISWVRQAPGIGYEYVSAISIGDPTYYWDSVKGRFTISRDNSKVTVYLQMNSLRAEDTAVYYCARSYPGNGDLGRLDIWGQGTTVTVSS"}]
                if ref.get("crop_image_name") == "crop-l.jpg":
                    return [{"mAb": "1C8-L1", "VL_sequence": "DIQLTQSPSFLSASVGDRVTITCQSSQSVYRNKYLSWYQQKPGKAPKLLIYYASTAQSGVPSRFSGSGSGTEFTLTISSLQPEDFATYYCAGDYSDDIENAFGQGTKVEIK"}]
            return [{"mAb": "1C8", "CDRH3": "ARQGYYGSSYVMDY"}] if not ref.get("crop_image_name") else []

        tool._extract_records_with_user_text = fake_extract_records_with_user_text

        result = asyncio.run(
            tool.extract_from_markdown(
                "Figure 2C alignment ![](images/fig.jpg)",
                "/tmp/paper/images_ocr_merged.md",
                seed_names=[],
            )
        )
        names = {record["mAb"] for record in result["table_records"]}
        self.assertIn("1C8", names)
        self.assertIn("1C8-H3", names)
        self.assertIn("1C8-L1", names)

    def test_augment_with_adjacent_image_groups_builds_three_image_panel(self):
        refs = [
            {"rel_path": "images/a.jpg", "abs_path": "/tmp/a.jpg", "context": "", "ocr_text": "", "_match_start": 0, "_match_end": 17},
            {"rel_path": "images/b.jpg", "abs_path": "/tmp/b.jpg", "context": "", "ocr_text": "", "_match_start": 21, "_match_end": 38},
            {"rel_path": "images/c.jpg", "abs_path": "/tmp/c.jpg", "context": "", "ocr_text": "", "_match_start": 40, "_match_end": 57},
        ]
        md_text = "![](images/a.jpg)\n\nb\n\n![](images/b.jpg)\n\n![](images/c.jpg)\n"
        grouped = self.tool._augment_with_adjacent_image_groups(refs, md_text)
        groups = [ref for ref in grouped if ref.get("group_rel_paths")]
        self.assertTrue(any(ref["group_rel_paths"] == ["images/a.jpg", "images/b.jpg"] for ref in groups))
        self.assertTrue(any(ref["group_rel_paths"] == ["images/a.jpg", "images/b.jpg", "images/c.jpg"] for ref in groups))

    def test_augment_with_adjacent_image_groups_stops_at_real_caption_text(self):
        refs = [
            {"rel_path": "images/a.jpg", "abs_path": "/tmp/a.jpg", "context": "", "ocr_text": "", "_match_start": 0, "_match_end": 17},
            {"rel_path": "images/b.jpg", "abs_path": "/tmp/b.jpg", "context": "", "ocr_text": "", "_match_start": 62, "_match_end": 79},
        ]
        md_text = "![](images/a.jpg)\n\nSupplementary Fig. 1 Sequence alignment of heavy chains.\n\n![](images/b.jpg)\n"
        grouped = self.tool._augment_with_adjacent_image_groups(refs, md_text)
        groups = [ref for ref in grouped if ref.get("group_rel_paths")]
        self.assertEqual(groups, [])


if __name__ == "__main__":
    unittest.main()
