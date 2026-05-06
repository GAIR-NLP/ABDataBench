"""Tests for targeted enrichment flow in orchestrator/image supplement logic."""

import asyncio
import logging
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from orchestrator import Orchestrator
from agents.extract.image_extract_agent import ImageExtractAgent


class TestOrchestratorGapFlow(unittest.TestCase):
    def setUp(self):
        self.orchestrator = Orchestrator.__new__(Orchestrator)
        self.orchestrator.logger = logging.getLogger("test.orchestrator")

    def test_build_gap_report_only_tracks_vlm_target_fields(self):
        skeleton = {
            "paper-1": {
                "paper_id": "paper-1",
                "antibodies": [
                    {
                        "Antibody_Name": "Ab1",
                        "CDRH3_Sequence": "",
                        "vh_sequence_aa": "EVQLV...",
                        "vl_sequence_aa": "",
                        "Binding_Kinetics_KD": "",
                        "Target_Name": "",
                    },
                    {
                        "Antibody_Name": "Ab2",
                        "CDRH3_Sequence": "CARDRSTW",
                        "vh_sequence_aa": "QVQL...",
                        "vl_sequence_aa": "DIQMT...",
                        "Binding_Kinetics_KD": "1.2 nM",
                        "Binding_Kinetics_kon": "1.0e5 1/Ms",
                        "Binding_Kinetics_koff": "2.0e-4 1/s",
                        "Binding_EC50": "0.5 nM",
                        "Quantitative_Metric": "0.2 ug/mL",
                        "Thermal_Stability_Tm": "68 C",
                        "In_Vivo_Efficacy": "protection:100% survival at 150 μg",
                    },
                ],
            }
        }

        gap_report = Orchestrator._build_gap_report(skeleton, "paper-1")

        self.assertEqual(gap_report["summary"]["total_antibodies"], 2)
        self.assertEqual(gap_report["summary"]["antibodies_with_gaps"], 1)
        self.assertEqual(gap_report["targets"][0]["antibody_name"], "Ab1")
        self.assertIn("CDRH3_Sequence", gap_report["targets"][0]["missing_fields"])
        self.assertIn("vl_sequence_aa", gap_report["targets"][0]["missing_fields"])
        self.assertIn("Binding_Kinetics_KD", gap_report["targets"][0]["missing_fields"])
        self.assertIn("In_Vivo_Efficacy", gap_report["targets"][0]["missing_fields"])
        self.assertNotIn("Target_Name", gap_report["summary"]["missing_counts"])

    def test_should_run_vlm_gap_fill_requires_targets_antibodies_and_images(self):
        context = {
            "paper_id": "paper-1",
            "markdown_text": "body ![fig](images/fig1.png)",
            "skeleton": {"paper-1": {"antibodies": [{"Antibody_Name": "Ab1"}]}},
        }
        gap_report = {"targets": [{"antibody_name": "Ab1", "missing_fields": ["CDRH3_Sequence"]}]}

        self.assertTrue(Orchestrator._should_run_vlm_gap_fill(context, gap_report))
        self.assertFalse(
            Orchestrator._should_run_vlm_gap_fill(
                {**context, "markdown_text": "body without figures"},
                gap_report,
            )
        )
        self.assertFalse(
            Orchestrator._should_run_vlm_gap_fill(
                {**context, "skeleton": {"paper-1": {"antibodies": []}}},
                gap_report,
            )
        )
        self.assertFalse(Orchestrator._should_run_vlm_gap_fill(context, {"targets": []}))

    def test_merge_extractions_fills_only_missing_fields(self):
        skeleton = {
            "paper-1": {
                "paper_id": "paper-1",
                "antibodies": [
                    {
                        "Antibody_Name": "Ab1",
                        "CDRH3_Sequence": "",
                        "vh_sequence_aa": "EVQLV-existing",
                        "vl_sequence_aa": "",
                        "Binding_Kinetics_KD": "",
                        "Binding_EC50": "",
                        "Binding_Kinetics_kon": "",
                        "Binding_Kinetics_koff": "",
                        "Quantitative_Metric": "",
                        "Thermal_Stability_Tm": "",
                    }
                ],
            }
        }
        extract_results = [
            SimpleNamespace(
                data={
                    "table_records": [
                        {
                            "mAb": "Ab1",
                            "CDRH3": "CARDRSTW",
                            "VH_sequence": "EVQLV-from-vlm",
                            "VL_sequence": "DIQMTQSP",
                            "KD": "2.3 nM",
                            "EC50": "0.5 nM",
                            "kon": "1.0e5 1/Ms",
                            "koff": "2.0e-4 1/s",
                            "IC50": "0.2 ug/mL",
                            "Tm": "68 C",
                        }
                    ]
                }
            )
        ]

        merged, stats = self.orchestrator._merge_extractions(skeleton, "paper-1", extract_results)
        ab = merged["paper-1"]["antibodies"][0]

        self.assertEqual(ab["CDRH3_Sequence"], "CARDRSTW")
        self.assertEqual(ab["vh_sequence_aa"], "EVQLV-existing")
        self.assertEqual(ab["vl_sequence_aa"], "")
        self.assertEqual(ab["Binding_Kinetics_KD"], "2.3 nM")
        self.assertEqual(ab["Binding_EC50"], "0.5 nM")
        self.assertEqual(ab["Binding_Kinetics_kon"], "1.0e5 1/Ms")
        self.assertEqual(ab["Binding_Kinetics_koff"], "2.0e-4 1/s")
        self.assertEqual(ab["Quantitative_Metric"], "0.2 ug/mL")
        self.assertEqual(ab["Thermal_Stability_Tm"], "68 C")
        self.assertEqual(stats["matched_antibodies"], 1)
        self.assertEqual(stats["records_seen"], 1)
        self.assertEqual(stats["filled_fields"], 7)

    def test_record_supports_new_antibody_rejects_reference_only_sequence_panel(self):
        record = {
            "mAb": "S2E12",
            "CDRH3": "CASPYCSGGSCSDGFDIW",
            "_source_category": "SEQUENCE_DATA",
            "_source_context": (
                "Figure 3. Sequence alignment of 2C08 with RBD-binding mAbs from SARS-CoV-2 "
                "infected patients and vaccinees. previously described human mAb S2E12."
            ),
        }

        self.assertFalse(Orchestrator._record_supports_new_antibody(record))

    def test_record_supports_new_antibody_accepts_study_quantitative_record(self):
        record = {
            "mAb": "3.10A7",
            "CDRH3": "TAGTTVVPFDY",
            "KD": "1.0E-09 M",
            "_source_category": "KINETICS_DATA",
            "_source_context": "Supplementary Fig. 2. Monovalent binding kinetics and KD of antibodies to TREM2.",
        }

        self.assertTrue(Orchestrator._record_supports_new_antibody(record))

    def test_hydrate_sequence_fields_from_hints_converts_three_letter_sequences(self):
        antibodies = [
            {
                "Antibody_Name": "Antibody 1",
                "CDRH3_Sequence": "",
                "vh_sequence_aa": "",
                "vl_sequence_aa": "",
                "_field_hints": {
                    "CDRH3_Sequence": {
                        "value": "Asp Leu Pro Gly Ile Ala Val Ala Gly Tyr",
                        "pointer": "SEQ ID NO: 5",
                        "action": "Script Extract",
                    },
                    "vh_sequence_aa": {
                        "value": (
                            "Glu Val Gln Leu Leu Glu Ser Gly Gly Gly Leu Val Gln Pro Gly Gly Ser "
                            "Leu Arg Leu Ser Cys Ala Ala Ser Gly Phe Thr Phe Gly Asn Ser Trp Met "
                            "Ser Trp Val Arg Gln Ala Pro Gly Lys Gly Leu Glu Trp Val Ser Ala Ile "
                            "Ser Gly Ser Gly Gly Ser Thr Tyr Tyr Ala Asp Ser Val Lys Gly Arg Phe "
                            "Thr Ile Ser Arg Asp Asn Ser Lys Asn Thr Leu Tyr Leu Gln Met Asn Ser "
                            "Leu Arg Ala Glu Asp Thr Ala Val Tyr Tyr Cys Thr Arg Asp Leu Pro Gly "
                            "Ile Ala Val Ala Gly Tyr Trp Gly Gln Gly Thr Leu Val Thr Val Ser Ser"
                        ),
                        "pointer": "SEQ ID NO: 2",
                        "action": "Script Extract",
                    },
                    "vl_sequence_aa": {
                        "value": (
                            "Asp Thr Gln Met Thr Gln Ser Pro Ser Leu Ser Ala Ser Val Gly Asp Arg "
                            "Val Thr Ile Thr Cys Arg Ala Ser Glu Gly Ile Tyr His Trp Leu Ala Trp "
                            "Tyr Gln Gln Lys Pro Gly Lys Ala Pro Lys Leu Leu Ile Tyr Lys Ala Ser "
                            "Ser Leu Ala Ser Gly Val Pro Ser Arg Phe Ser Gly Ser Gly Ser Gly Thr "
                            "Glu Phe Thr Leu Thr Ile Ser Ser Leu Gln Pro Asp Asp Phe Ala Thr Tyr "
                            "Tyr Cys Gln Gln Tyr Ser Asn Tyr Pro Leu Thr Phe Gly Gly Gly Thr Lys "
                            "Leu Glu Ile Lys Arg"
                        ),
                        "pointer": "SEQ ID NO: 7",
                        "action": "Script Extract",
                    },
                },
            }
        ]

        filled = Orchestrator._hydrate_sequence_fields_from_hints(antibodies)
        ab = antibodies[0]

        self.assertGreaterEqual(filled, 3)
        self.assertEqual(ab["CDRH3_Sequence"], "DLPGIAVAGY")
        self.assertTrue(ab["vh_sequence_aa"].startswith("EVQLLESGGGLVQPGGSLRLSCAAS"))
        self.assertTrue(ab["vl_sequence_aa"].startswith("DTQMTQSPSLSASVGDRVTITCRAS"))
        self.assertEqual(ab["field_sources"]["vh_sequence_aa"]["source_type"], "skeleton_hint_normalized")

    def test_dedup_sequence_image_records_preserves_legitimate_shared_sequences(self):
        records = [
            {
                "mAb": "F4.30",
                "VH_sequence": "DVQLQESGPGLVKPSQSLALTCSVTGYSITSGYYWNWIRQFPGNKLEWMGYISYDGRNNYNPSLKNRMSITRDTSKNQFFLKLNSVTTEDTATYYCASLRRYFDYWGQGTTL",
                "VL_sequence": "DIVLTQSPASLAVSLGQRATISCRASESVDHYGISFMNWFQQKPGQPPKLLIYAASNQGSGVPRFSGSGSGTDFSLNIHPMEEDDTAMYFCQQSKEVPWTFGGGTKLEIKR",
                "CDRH3": "ASLRRYFDYWGQGTTL",
                "_source_image": "images/shared.jpg",
                "_source_context": "FIGURE 4. Sequencing of the C region of the H and L chain of F4.30 and C6.11.",
                "_source_category": "SEQUENCE_DATA",
                "_discovered_from_sequence_image": True,
            },
            {
                "mAb": "C6.11",
                "VH_sequence": "DVQLQESGPGLVKPSQSLALTCSVTGYSITSGYYWNWIRQFPGNKLEWMGYISYDGRNNYNPSLKNRMSITRDTSKNQFFLKLNSVTTEDTATYYCASLRRYFDYWGQGTTL",
                "VL_sequence": "DIVLTQSPASLAVSLGQRATISCRASESVDHYGISFMNWFQQKPGQPPKLLIYAASNQGSGVPRFSGSGSGTDFSLNIHPMEEDDTAMYFCQQSKEVPWTFGGGTKLEIKR",
                "CDRH3": "ASLRRYFDYWGQGTTL",
                "_source_image": "images/shared.jpg",
                "_source_context": "FIGURE 4. Sequencing of the C region of the H and L chain of F4.30 and C6.11.",
                "_source_category": "SEQUENCE_DATA",
                "_discovered_from_sequence_image": True,
            },
        ]

        cleaned = Orchestrator._dedup_sequence_image_records(records)

        self.assertEqual(cleaned[0]["VH_sequence"], records[0]["VH_sequence"])
        self.assertEqual(cleaned[0]["VL_sequence"], records[0]["VL_sequence"])
        self.assertEqual(cleaned[1]["VH_sequence"], records[1]["VH_sequence"])
        self.assertEqual(cleaned[1]["VL_sequence"], records[1]["VL_sequence"])
        self.assertTrue(cleaned[0]["_sequence_duplicate_cluster"]["shared_context_named_group"])
        self.assertTrue(cleaned[0]["_sequence_duplicate_cluster"]["shared_vl_sequence"])
        self.assertFalse(cleaned[0]["_sequence_duplicate_review_required"])

    def test_merge_extractions_fills_identical_sequence_image_records(self):
        skeleton = {
            "paper-1": {
                "paper_id": "paper-1",
                "antibodies": [
                    {
                        "Antibody_Name": "F4.30",
                        "CDRH3_Sequence": "",
                        "vh_sequence_aa": "",
                        "vl_sequence_aa": "",
                        "Binding_Kinetics_KD": "",
                    },
                    {
                        "Antibody_Name": "C6.11",
                        "CDRH3_Sequence": "",
                        "vh_sequence_aa": "",
                        "vl_sequence_aa": "",
                        "Binding_Kinetics_KD": "",
                    },
                ],
            }
        }
        records = Orchestrator._dedup_sequence_image_records(
            [
                {
                    "mAb": "F4.30",
                    "VH_sequence": "DVQLQESGPGLVKPSQSLALTCSVTGYSITSGYYWNWIRQFPGNKLEWMGYISYDGRNNYNPSLKNRMSITRDTSKNQFFLKLNSVTTEDTATYYCASLRRYFDYWGQGTTL",
                    "VL_sequence": "DIVLTQSPASLAVSLGQRATISCRASESVDHYGISFMNWFQQKPGQPPKLLIYAASNQGSGVPRFSGSGSGTDFSLNIHPMEEDDTAMYFCQQSKEVPWTFGGGTKLEIKR",
                    "CDRH3": "ASLRRYFDYWGQGTTL",
                    "_source_image": "images/shared.jpg",
                    "_source_context": "FIGURE 4. Sequencing of the C region of the H and L chain of F4.30 and C6.11.",
                    "_source_category": "SEQUENCE_DATA",
                    "_discovered_from_sequence_image": True,
                },
                {
                    "mAb": "C6.11",
                    "VH_sequence": "DVQLQESGPGLVKPSQSLALTCSVTGYSITSGYYWNWIRQFPGNKLEWMGYISYDGRNNYNPSLKNRMSITRDTSKNQFFLKLNSVTTEDTATYYCASLRRYFDYWGQGTTL",
                    "VL_sequence": "DIVLTQSPASLAVSLGQRATISCRASESVDHYGISFMNWFQQKPGQPPKLLIYAASNQGSGVPRFSGSGSGTDFSLNIHPMEEDDTAMYFCQQSKEVPWTFGGGTKLEIKR",
                    "CDRH3": "ASLRRYFDYWGQGTTL",
                    "_source_image": "images/shared.jpg",
                    "_source_context": "FIGURE 4. Sequencing of the C region of the H and L chain of F4.30 and C6.11.",
                    "_source_category": "SEQUENCE_DATA",
                    "_discovered_from_sequence_image": True,
                },
            ]
        )
        extract_results = [SimpleNamespace(data={"table_records": records})]

        merged, stats = self.orchestrator._merge_extractions(skeleton, "paper-1", extract_results)
        f430 = merged["paper-1"]["antibodies"][0]
        c611 = merged["paper-1"]["antibodies"][1]

        self.assertEqual(f430["CDRH3_Sequence"], "ASLRRYFDYWGQGTTL")
        self.assertTrue(f430["vh_sequence_aa"].startswith("DVQLQESGPGLVKPSQSLALT"))
        self.assertTrue(f430["vl_sequence_aa"].startswith("DIVLTQSPASLAVSLGQRAT"))
        self.assertEqual(c611["CDRH3_Sequence"], "ASLRRYFDYWGQGTTL")
        self.assertTrue(c611["vh_sequence_aa"].startswith("DVQLQESGPGLVKPSQSLALT"))
        self.assertTrue(c611["vl_sequence_aa"].startswith("DIVLTQSPASLAVSLGQRAT"))
        self.assertEqual(stats["matched_antibodies"], 2)
        self.assertEqual(stats["records_seen"], 2)
        self.assertGreaterEqual(stats["filled_fields"], 6)

    def test_merge_extractions_prefers_authoritative_api_sequence_for_minor_ocr_mismatch(self):
        skeleton = {
            "paper-1": {
                "paper_id": "paper-1",
                "antibodies": [
                    {
                        "Antibody_Name": "Nb55",
                        "CDRH3_Sequence": "",
                        "vh_sequence_aa": "QVQLQESGGGLVQAGGSLRLSCAASGSRFSSNTMTWYRQAPGKQREWVATMRSIGTTRYASSVEGRFTLSRDNAKNTVYLQMNSLKPEDTAVYYCNLRGGGIIWGQGTQVTVSS",
                        "vl_sequence_aa": "",
                    }
                ],
            }
        }
        extract_results = [
            SimpleNamespace(
                data={
                    "table_records": [
                        {
                            "mAb": "Nb55",
                            "VH_sequence": "QVQLQESGGGLVQAGGSLRLSCAASGSRFSSNTMTWYRQAPGKQREWVATMRSIGTTRYASSVEGRFTLSRDNAKNTVYLQMNSLKPEDTAVYYCNLRRGGGIYWGQGTQVTVSS",
                            "_api_source_ids": "9GXH",
                            "_api_source_kind": "genbank",
                        }
                    ]
                }
            )
        ]

        merged, _ = self.orchestrator._merge_extractions(skeleton, "paper-1", extract_results)
        ab = merged["paper-1"]["antibodies"][0]

        self.assertEqual(
            ab["vh_sequence_aa"],
            "QVQLQESGGGLVQAGGSLRLSCAASGSRFSSNTMTWYRQAPGKQREWVATMRSIGTTRYASSVEGRFTLSRDNAKNTVYLQMNSLKPEDTAVYYCNLRRGGGIYWGQGTQVTVSS",
        )
        self.assertEqual(ab["_sequence_diagnostics"][0]["action"], "replace_with_authoritative")
        self.assertEqual(ab["_sequence_diagnostics"][0]["source_ids"], "9GXH")

    def test_merge_extractions_authoritative_sequence_overrides_major_conflict(self):
        skeleton = {
            "paper-1": {
                "paper_id": "paper-1",
                "antibodies": [
                    {
                        "Antibody_Name": "Ab1",
                        "CDRH3_Sequence": "CARPPRNYYDRSGYYQRAEYFQHW",
                        "vh_sequence_aa": "QVQLVQSGAEVKKPGASVKVSCKASGYTFTSYYMHWVRQAPGQGLEWMGIINSSGGSTSYAQKFQGRVTMTRDTSTSTVYMELSSLRSEDTAVYYCARPPRNYYDRSGYYQRAEYFQHWGQGTLVTVSS",
                        "vl_sequence_aa": "",
                    }
                ],
            }
        }
        extract_results = [
            SimpleNamespace(
                data={
                    "table_records": [
                        {
                            "mAb": "Ab1",
                            "VH_sequence": "QVQLQESGGGLVQAGGSLRLSCAASGSRFSSNTMTWYRQAPGKQREWVATMRSIGTTRYASSVEGRFTLSRDNAKNTVYLQMNSLKPEDTAVYYCNLRRGGGIYWGQGTQVTVSS",
                            "_api_source_ids": "9GXH",
                            "_api_source_kind": "genbank",
                        }
                    ]
                }
            )
        ]

        merged, _ = self.orchestrator._merge_extractions(skeleton, "paper-1", extract_results)
        ab = merged["paper-1"]["antibodies"][0]

        self.assertEqual(
            ab["vh_sequence_aa"],
            "QVQLQESGGGLVQAGGSLRLSCAASGSRFSSNTMTWYRQAPGKQREWVATMRSIGTTRYASSVEGRFTLSRDNAKNTVYLQMNSLKPEDTAVYYCNLRRGGGIYWGQGTQVTVSS",
        )
        self.assertEqual(ab["CDRH3_Sequence"], "CNLRRGGGIYW")
        self.assertEqual(ab["_sequence_diagnostics"][0]["action"], "replace_with_authoritative")
        self.assertEqual(ab["_sequence_diagnostics"][0]["source_ids"], "9GXH")

    def test_merge_extractions_pdb_record_overrides_even_for_major_sequence_conflict(self):
        skeleton = {
            "paper-1": {
                "paper_id": "paper-1",
                "antibodies": [
                    {
                        "Antibody_Name": "Ab1",
                        "CDRH3_Sequence": "CARPPRNYYDRSGYYQRAEYFQHW",
                        "vh_sequence_aa": "QVQLVQSGAEVKKPGASVKVSCKASGYTFTSYYMHWVRQAPGQGLEWMGIINSSGGSTSYAQKFQGRVTMTRDTSTSTVYMELSSLRSEDTAVYYCARPPRNYYDRSGYYQRAEYFQHWGQGTLVTVSS",
                        "vl_sequence_aa": "DIQMTQSPSSLSASVGDRVTITCRASQGIRNWLNWYQQKPGKAPKLLIYYASSLQSGVPSRFSGSGSGTDFTLTISSLQPEDFATYYCQQYNSYPLTFGQGTKVEIK",
                    }
                ],
            }
        }
        extract_results = [
            SimpleNamespace(
                data={
                    "table_records": [
                        {
                            "mAb": "Ab1",
                            "VH_sequence": "QVQLQESGGGLVQAGGSLRLSCAASGSRFSSNTMTWYRQAPGKQREWVATMRSIGTTRYASSVEGRFTLSRDNAKNTVYLQMNSLKPEDTAVYYCNLRRGGGIYWGQGTQVTVSS",
                            "VL_sequence": "DIQMTQSPSSLSASVGDRVTITCRASQDISNYLNWYQQKPGKAPKLLIYAASSLQSGVPSRFSGSGSGTDFTLTISSLQPEDFATYYCQQYNSYPLTFGQGTKVEIK",
                            "_api_source_ids": "9GXH",
                            "_api_source_kind": "pdb",
                        }
                    ]
                }
            )
        ]

        merged, _ = self.orchestrator._merge_extractions(skeleton, "paper-1", extract_results)
        ab = merged["paper-1"]["antibodies"][0]

        self.assertEqual(
            ab["vh_sequence_aa"],
            "QVQLQESGGGLVQAGGSLRLSCAASGSRFSSNTMTWYRQAPGKQREWVATMRSIGTTRYASSVEGRFTLSRDNAKNTVYLQMNSLKPEDTAVYYCNLRRGGGIYWGQGTQVTVSS",
        )
        self.assertEqual(
            ab["vl_sequence_aa"],
            "DIQMTQSPSSLSASVGDRVTITCRASQDISNYLNWYQQKPGKAPKLLIYAASSLQSGVPSRFSGSGSGTDFTLTISSLQPEDFATYYCQQYNSYPLTFGQGTKVEIK",
        )
        self.assertEqual(ab["CDRH3_Sequence"], "CNLRRGGGIYW")
        self.assertEqual(ab["_sequence_diagnostics"][0]["action"], "replace_with_pdb_authoritative")
        self.assertEqual(ab["_sequence_diagnostics"][0]["source_ids"], "9GXH")

    def test_sequence_image_overrides_existing_ocr_sequence_value(self):
        skeleton = {
            "paper-1": {
                "paper_id": "paper-1",
                "antibodies": [
                    {
                        "Antibody_Name": "Ab1",
                        "vh_sequence_aa": "QVQLQESGGGLVQAGGSLRLSCAASGSRFSSNTMTWYRQAPGKQREWVATMRSIGTTRYASSVEGRFTLSRDNAKNTVYLQMNSLKPEDTAVYYCNLRRGGGIYWGQGTQVTVSS",
                        "vl_sequence_aa": "DIQMTQSPSSLSASVGDRVTITCRASQDISNYLNWYQQKPGKAPKLLIYAASSLQSGVPSRFSGSGSGTDFTLTISSLQPEDFATYYCQQYNSYPLTFGQGTKVEIK",
                        "field_sources": {
                            "vh_sequence_aa": {"source_type": "ocr_text_sequence"},
                            "vl_sequence_aa": {"source_type": "ocr_text_sequence"},
                        },
                    }
                ],
            }
        }
        extract_results = [
            SimpleNamespace(
                data={
                    "table_records": [
                        {
                            "mAb": "Ab1",
                            "VH_sequence": "QVQLVQSGAEVKKPGASVKVSCKASGYTFTSYYMHWVRQAPGQGLEWMGIINSSGGSTSYAQKFQGRVTMTRDTSTSTVYMELSSLRSEDTAVYYCARPPRNYYDRSGYYQRAEYFQHWGQGTLVTVSS",
                            "VL_sequence": "DIQLTQSPSSLSASVGDRVTITCQASQDISNYLNWYQQRPGKAPKLLIYDASNLETGVPSRFSGSGSGTDFTFTISSLQPEDIATYYCQQYDNPPLTFGGGTKLEIK",
                            "_source_category": "SEQUENCE_DATA",
                            "_discovered_from_sequence_image": True,
                            "_source_image": "images/fig_s7a.jpg",
                        }
                    ]
                }
            )
        ]

        merged, _ = self.orchestrator._merge_extractions(skeleton, "paper-1", extract_results)
        ab = merged["paper-1"]["antibodies"][0]
        self.assertTrue(ab["vh_sequence_aa"].startswith("QVQLVQSGAEVKKPGA"))
        self.assertTrue(ab["vl_sequence_aa"].startswith("DIQLTQSPSSLSASVG"))
        self.assertEqual(ab["field_sources"]["vh_sequence_aa"]["source_type"], "sequence_image")
        self.assertEqual(ab["field_sources"]["vl_sequence_aa"]["source_type"], "sequence_image")

    def test_ocr_text_sequence_cannot_override_existing_sequence_image_value(self):
        skeleton = {
            "paper-1": {
                "paper_id": "paper-1",
                "antibodies": [
                    {
                        "Antibody_Name": "Ab1",
                        "vh_sequence_aa": "QVQLVQSGAEVKKPGASVKVSCKASGYTFTSYYMHWVRQAPGQGLEWMGIINSSGGSTSYAQKFQGRVTMTRDTSTSTVYMELSSLRSEDTAVYYCARPPRNYYDRSGYYQRAEYFQHWGQGTLVTVSS",
                        "vl_sequence_aa": "DIQLTQSPSSLSASVGDRVTITCQASQDISNYLNWYQQRPGKAPKLLIYDASNLETGVPSRFSGSGSGTDFTFTISSLQPEDIATYYCQQYDNPPLTFGGGTKLEIK",
                        "field_sources": {
                            "vh_sequence_aa": {"source_type": "sequence_image"},
                            "vl_sequence_aa": {"source_type": "sequence_image"},
                        },
                    }
                ],
            }
        }
        extract_results = [
            SimpleNamespace(
                data={
                    "table_records": [
                        {
                            "mAb": "Ab1",
                            "VH_sequence": "QVQLQESGGGLVQAGGSLRLSCAASGSRFSSNTMTWYRQAPGKQREWVATMRSIGTTRYASSVEGRFTLSRDNAKNTVYLQMNSLKPEDTAVYYCNLRRGGGIYWGQGTQVTVSS",
                            "VL_sequence": "DIQMTQSPSSLSASVGDRVTITCRASQDISNYLNWYQQKPGKAPKLLIYAASSLQSGVPSRFSGSGSGTDFTLTISSLQPEDFATYYCQQYNSYPLTFGQGTKVEIK",
                            "_discovered_from_text_sequence": True,
                            "_source_image": "images/text_block.jpg",
                        }
                    ]
                }
            )
        ]

        merged, _ = self.orchestrator._merge_extractions(skeleton, "paper-1", extract_results)
        ab = merged["paper-1"]["antibodies"][0]
        self.assertTrue(ab["vh_sequence_aa"].startswith("QVQLVQSGAEVKKPGA"))
        self.assertTrue(ab["vl_sequence_aa"].startswith("DIQLTQSPSSLSASVG"))
        self.assertEqual(ab["field_sources"]["vh_sequence_aa"]["source_type"], "sequence_image")
        self.assertEqual(ab["_sequence_diagnostics"][0]["action"], "keep_existing_higher_priority")

    def test_ocr_text_sequence_cannot_override_existing_pdb_value(self):
        skeleton = {
            "paper-1": {
                "paper_id": "paper-1",
                "antibodies": [
                    {
                        "Antibody_Name": "Ab1",
                        "vh_sequence_aa": "QVQLQESGGGLVQAGGSLRLSCAASGSRFSSNTMTWYRQAPGKQREWVATMRSIGTTRYASSVEGRFTLSRDNAKNTVYLQMNSLKPEDTAVYYCNLRRGGGIYWGQGTQVTVSS",
                        "vl_sequence_aa": "DIQMTQSPSSLSASVGDRVTITCRASQDISNYLNWYQQKPGKAPKLLIYAASSLQSGVPSRFSGSGSGTDFTLTISSLQPEDFATYYCQQYNSYPLTFGQGTKVEIK",
                        "field_sources": {
                            "vh_sequence_aa": {"source_type": "api_fetch"},
                            "vl_sequence_aa": {"source_type": "api_fetch"},
                        },
                    }
                ],
            }
        }
        extract_results = [
            SimpleNamespace(
                data={
                    "table_records": [
                        {
                            "mAb": "Ab1",
                            "VH_sequence": "QVQLVQSGAEVKKPGASVKVSCKASGYTFTSYYMHWVRQAPGQGLEWMGIINSSGGSTSYAQKFQGRVTMTRDTSTSTVYMELSSLRSEDTAVYYCARPPRNYYDRSGYYQRAEYFQHWGQGTLVTVSA",
                            "VL_sequence": "DIQLTQSPSSLSASVGDRVTITCQASQDISNYLNWYQQRPGKAPKLLIYDASNLETGVPSRFSGSGSGTDFTFTISSLQPEDIATYYCQQYDNPPLTFGGGTKLEIKA",
                            "_discovered_from_text_sequence": True,
                            "_source_image": "images/text_block.jpg",
                        }
                    ]
                }
            )
        ]

        merged, _ = self.orchestrator._merge_extractions(skeleton, "paper-1", extract_results)
        ab = merged["paper-1"]["antibodies"][0]
        self.assertTrue(ab["vh_sequence_aa"].endswith("WGQGTQVTVSS"))
        self.assertTrue(ab["vl_sequence_aa"].endswith("TFGQGTKVEIK"))
        self.assertEqual(ab["field_sources"]["vh_sequence_aa"]["source_type"], "api_fetch")
        self.assertEqual(ab["_sequence_diagnostics"][0]["action"], "keep_existing_higher_priority")

    def test_merge_extractions_rejects_light_chain_like_sequence_in_vh_field(self):
        skeleton = {
            "paper-1": {
                "paper_id": "paper-1",
                "antibodies": [
                    {
                        "Antibody_Name": "anifrolumab",
                        "vh_sequence_aa": "EVQLVQSGAEVKKPGESLKISCKGSGYIFTNYWIAWVRQMPGKGLESMGIIYPGDSDIRYSPSFQGQVTISADKSITTAYLQWSSLKASDTAMYYCARHDIEGFDYWGRGTLVTVSS",
                        "vl_sequence_aa": "",
                        "CDRH3_Sequence": "CARHDIEGFDYW",
                        "field_sources": {
                            "vh_sequence_aa": {"source_type": "sequence_image"},
                        },
                    }
                ],
            }
        }
        extract_results = [
            SimpleNamespace(
                data={
                    "table_records": [
                        {
                            "mAb": "anifrolumab",
                            "VH_sequence": "EIVLTQSPGTLSLSPGERATLSCRASQSVSSSFFAWYQQKPGQAPRLLIYGASSRATGIPDRLSGSGSGTDFTLTITRLEPEDFAVYYCQQYDSSAITFGQGTRLEIK",
                            "VL_sequence": "EIVLTQSPGTLSLSPGERATLSCRASQSVSSSFFAWYQQKPGQAPRLLIYGASSRATGIPDRLSGSGSGTDFTLTITRLEPEDFAVYYCQQYDSSAITFGQGTRLEIK",
                            "_source_category": "SEQUENCE_DATA",
                            "_discovered_from_sequence_image": True,
                            "_source_image": "images/fig5a.jpg",
                        }
                    ]
                }
            )
        ]

        merged, _ = self.orchestrator._merge_extractions(skeleton, "paper-1", extract_results)
        ab = merged["paper-1"]["antibodies"][0]

        self.assertEqual(
            ab["vh_sequence_aa"],
            "EVQLVQSGAEVKKPGESLKISCKGSGYIFTNYWIAWVRQMPGKGLESMGIIYPGDSDIRYSPSFQGQVTISADKSITTAYLQWSSLKASDTAMYYCARHDIEGFDYWGRGTLVTVSS",
        )
        self.assertEqual(
            ab["vl_sequence_aa"],
            "EIVLTQSPGTLSLSPGERATLSCRASQSVSSSFFAWYQQKPGQAPRLLIYGASSRATGIPDRLSGSGSGTDFTLTITRLEPEDFAVYYCQQYDSSAITFGQGTRLEIK",
        )
        self.assertTrue(
            any(
                entry.get("action") == "skip_chain_mismatch" and entry.get("field") == "vh_sequence_aa"
                for entry in ab.get("_sequence_diagnostics", [])
            )
        )

    def test_merge_extractions_accepts_canonical_vlm_field_names(self):
        skeleton = {
            "paper-1": {
                "paper_id": "paper-1",
                "antibodies": [
                    {
                        "Antibody_Name": "Ab1",
                        "Binding_Kinetics_KD": "",
                        "Binding_EC50": "",
                    }
                ],
            }
        }
        extract_results = [
            SimpleNamespace(
                data={
                    "table_records": [
                        {
                            "mAb": "Ab1",
                            "Binding_Kinetics_KD": "3.6 nM",
                            "Binding_EC50": "0.5 nM",
                        }
                    ]
                }
            )
        ]

        merged, stats = self.orchestrator._merge_extractions(skeleton, "paper-1", extract_results)
        ab = merged["paper-1"]["antibodies"][0]
        self.assertEqual(ab["Binding_Kinetics_KD"], "3.6 nM")
        self.assertEqual(ab["Binding_EC50"], "0.5 nM")
        self.assertEqual(stats["filled_fields"], 2)

    def test_merge_extractions_synchronizes_sequence_fields_across_same_antibody_name(self):
        skeleton = {
            "paper-1": {
                "paper_id": "paper-1",
                "antibodies": [
                    {
                        "Antibody_Name": "COVA1-16",
                        "Target_Name": "SARS-CoV-2",
                        "CDRH3_Sequence": "",
                        "vh_sequence_aa": "",
                        "vl_sequence_aa": "",
                    },
                    {
                        "Antibody_Name": "COVA1-16",
                        "Target_Name": "SARS-CoV",
                        "CDRH3_Sequence": "",
                        "vh_sequence_aa": "",
                        "vl_sequence_aa": "",
                    },
                ],
            }
        }
        extract_results = [
            SimpleNamespace(
                data={
                    "table_records": [
                        {
                            "mAb": "COVA1-16",
                            "CDRH3": "CARPPRNYYDRSGYYQRAEYFQHW",
                            "VH_sequence": "QVQLVQSGAEVKKPGASVKVSCKASGYTFTSYYMHWVRQAPGQGLEWMGIINSSGGSTSYAQKFQGRVTMTRDTSTSTVYMELSSLRSEDTAVYYCARPPRNYYDRSGYYQRAEYFQHWGQGTLVTVSS",
                            "VL_sequence": "DIQLTQSPSSLSASVGDRVTITCQASQDISNYLNWYQQRPGKAPKLLIYDASNLETGVPSRFSGSGSGTDFTFTISSLQPEDIATYYCQQYDNPPLTFGGGTKLEIK",
                        }
                    ]
                }
            )
        ]

        merged, stats = self.orchestrator._merge_extractions(skeleton, "paper-1", extract_results)
        antibodies = merged["paper-1"]["antibodies"]
        for ab in antibodies:
            self.assertEqual(ab["CDRH3_Sequence"], "CARPPRNYYDRSGYYQRAEYFQHW")
            self.assertTrue(ab["vh_sequence_aa"].startswith("QVQLVQSGAEVKKPGA"))
            self.assertTrue(ab["vl_sequence_aa"].startswith("DIQLTQSPSSLSASVG"))
        self.assertEqual(stats["matched_antibodies"], 1)

    def test_merge_extractions_overrides_inconsistent_cdrh3_with_vh_derived_value(self):
        skeleton = {
            "paper-1": {
                "paper_id": "paper-1",
                "antibodies": [
                    {
                        "Antibody_Name": "COVA1-16",
                        "CDRH3_Sequence": "CARPPRNYYDRSGYYQRAEYFQQHW",
                        "vh_sequence_aa": "",
                        "vl_sequence_aa": "",
                    }
                ],
            }
        }
        extract_results = [
            SimpleNamespace(
                data={
                    "table_records": [
                        {
                            "mAb": "COVA1-16",
                            "VH_sequence": "QVQLVQSGAEVKKPGASVKVSCKASGYTFTSYYMHWVRQAPGQGLEWMGIINSSGGSTSYAQKFQGRVTMTRDTSTSTVYMELSSLRSEDTAVYYCARPPRNYYDRSGYYQRAEYFQHWGQGTLVTVSS",
                        }
                    ]
                }
            )
        ]

        merged, _ = self.orchestrator._merge_extractions(skeleton, "paper-1", extract_results)
        ab = merged["paper-1"]["antibodies"][0]
        self.assertEqual(ab["CDRH3_Sequence"], "CARPPRNYYDRSGYYQRAEYFQHW")

    def test_merge_extractions_keeps_direct_paper_cdrh3_over_sequence_image_derived_value(self):
        skeleton = {
            "paper-1": {
                "paper_id": "paper-1",
                "antibodies": [
                    {
                        "Antibody_Name": "PCIN63-77A",
                        "CDRH3_Sequence": "TTHSSRRDFQWSLDP",
                        "vh_sequence_aa": "",
                        "vl_sequence_aa": "",
                        "field_sources": {
                            "CDRH3_Sequence": {"source_type": "paper_text"},
                        },
                    }
                ],
            }
        }
        extract_results = [
            SimpleNamespace(
                data={
                    "table_records": [
                        {
                            "mAb": "PCIN63-77A",
                            "VH_sequence": "QVQLVQSGAEVKKPGASVRVSCKASGFAFTGYYHWVRQAPGQGLEWVGWINHNSGATNYAQKFQGRVSMTRDTSTSTAYMELSRLKSDDTAVYYCTTHSSRDFQSWLDPWGQGTLVTVSS",
                            "_discovered_from_sequence_image": True,
                            "_source_image": "images/fig_s2.jpg",
                        }
                    ]
                }
            )
        ]

        merged, _ = self.orchestrator._merge_extractions(skeleton, "paper-1", extract_results)
        ab = merged["paper-1"]["antibodies"][0]
        self.assertEqual(ab["CDRH3_Sequence"], "TTHSSRRDFQWSLDP")
        self.assertTrue(ab["vh_sequence_aa"].startswith("QVQLVQSGAEVKKPGASV"))

    def test_merge_extractions_skips_germline_labels_for_full_vh_vl_sequences(self):
        skeleton = {
            "paper-1": {
                "paper_id": "paper-1",
                "antibodies": [
                    {
                        "Antibody_Name": "Ab1",
                        "vh_sequence_aa": "",
                        "vl_sequence_aa": "",
                    }
                ],
            }
        }
        extract_results = [
            SimpleNamespace(
                data={
                    "table_records": [
                        {
                            "mAb": "Ab1",
                            "VH_sequence": "IGHV1-2",
                            "VL_sequence": "IGKV3-20",
                            "VDJ_Heavy": "IGHV1-2",
                            "VJ_Light": "IGKV3-20",
                            "VH_identity_pct": "93",
                            "VL_identity_pct": "94.3",
                        }
                    ]
                }
            )
        ]

        merged, stats = self.orchestrator._merge_extractions(skeleton, "paper-1", extract_results)
        ab = merged["paper-1"]["antibodies"][0]
        self.assertEqual(ab["vh_sequence_aa"], "")
        self.assertEqual(ab["vl_sequence_aa"], "")
        self.assertEqual(stats["filled_fields"], 0)

    def test_combine_vlm_targets_merges_validation_and_gap_targets(self):
        targets = Orchestrator._combine_vlm_targets(
            [{"antibody_name": "Ab1", "missing_fields": ["Binding_Kinetics_KD"]}],
            [{"antibody_name": "Ab1", "missing_fields": ["vh_sequence_aa"], "validation_only": True}],
        )
        self.assertEqual(len(targets), 1)
        self.assertEqual(set(targets[0]["missing_fields"]), {"Binding_Kinetics_KD", "vh_sequence_aa"})
        self.assertFalse(targets[0]["validation_only"])

    def test_validate_sequence_records_accepts_markdown_or_presequence_support(self):
        records = [
            {"mAb": "SM3", "VH_sequence": "VQLQESGGGLVQPGGSMKLSCVASGFTFSNYWMNWVRQSPEK", "_source_category": "SEQUENCE_DATA"},
            {"mAb": "Ghost", "VH_sequence": "ACDEFGHIKLMNPQRSTVWYACDEFGHIK", "_source_category": "SEQUENCE_DATA"},
        ]
        md_text = '... VQLQESGGGLVQPGGSMKLSCVASGFTFSNYWMNWVRQSPEK ...'
        pre = {"table_records": [{"mAb": "SM3", "VH_sequence": "VQLQESGGGLVQPGGSMKLSCVASGFTFSNYWMNWVRQSPEK"}]}
        validated = Orchestrator._validate_sequence_records(records, md_text, pre)
        self.assertEqual(len(validated), 1)
        self.assertEqual(validated[0]["mAb"], "SM3")

    def test_propagate_identical_variant_chains_copies_wt_light_chain_and_derives_cdrh3(self):
        skeleton = {
            "paper-1": {
                "paper_id": "paper-1",
                "antibodies": [
                    {
                        "Antibody_Name": "VRC01",
                        "vh_sequence_aa": "QVQLVQSGAEVKKPGASVKVSCKASGYTFTSYYMHWVRQAPGQGLEWMGIINSSGGSTSYAQKFQGRVTMTRDTSTSTVYMELSSLRSEDTAVYYCARPPRNYYDRSGYYQRAEYFQHWGQGTLVTVSS",
                        "vl_sequence_aa": "DIQLTQSPSSLSASVGDRVTITCQASQDISNYLNWYQQRPGKAPKLLIYDASNLETGVPSRFSGSGSGTDFTFTISSLQPEDIATYYCQQYDNPPLTFGGGTKLEIK",
                        "CDRH3_Sequence": "CARPPRNYYDRSGYYQRAEYFQHW",
                    },
                    {
                        "Antibody_Name": "VRC01 FR3-03",
                        "vh_sequence_aa": "",
                        "vl_sequence_aa": "",
                        "CDRH3_Sequence": "",
                    },
                ],
            }
        }
        md_text = (
            "Supplementary Fig. 3. The VRC01 FR3-03 chimeric antibody retained the same light chain as WT. "
            "Its heavy chain was unchanged relative to the wild-type VRC01 framework."
        )

        summary = Orchestrator._propagate_identical_variant_chains(skeleton, "paper-1", md_text)

        child = skeleton["paper-1"]["antibodies"][1]
        self.assertEqual(summary["pairs_applied"], 1)
        self.assertGreaterEqual(summary["filled_fields"], 3)
        self.assertEqual(child["vl_sequence_aa"], skeleton["paper-1"]["antibodies"][0]["vl_sequence_aa"])
        self.assertEqual(child["vh_sequence_aa"], skeleton["paper-1"]["antibodies"][0]["vh_sequence_aa"])
        self.assertTrue(child["CDRH3_Sequence"].startswith("C"))
        self.assertTrue(child["CDRH3_Sequence"].endswith("W"))
        self.assertEqual(child["_variant_parent"], "VRC01")
        self.assertEqual(child["_sequence_inheritance"][0]["from_antibody"], "VRC01")

    def test_propagate_chain_variant_combinations_fills_hxly_from_chain_level_records(self):
        skeleton = {
            "paper-1": {
                "paper_id": "paper-1",
                "antibodies": [
                    {
                        "Antibody_Name": "1C8-H3",
                        "vh_sequence_aa": "QSVKESGGGLFQPGGSLRLSCSVSGFSLSSYAISWVRQAPGKGLEYIGYISSIGDPYYADWVKGRFTISRDSSTVYLQMTSLRAEDTAVYFCARSYPGNGDLGRLDIWGQGTTVTVSS",
                        "vl_sequence_aa": "",
                        "CDRH3_Sequence": "ARSYPGNGDLGRLDI",
                    },
                    {
                        "Antibody_Name": "1C8-L1",
                        "vh_sequence_aa": "",
                        "vl_sequence_aa": "DIQLTQSPSFLSASVGDRVTITCQSSQSVYRNKYLSWYQQKPGKAPKLLIYASTLASGVPSRFSGSGSGTEFTLTISSLQPEDFATYYCAGDYSDDIENAFGQGTKVEIK",
                        "CDRH3_Sequence": "",
                    },
                    {
                        "Antibody_Name": "H3L1",
                        "vh_sequence_aa": "",
                        "vl_sequence_aa": "",
                        "CDRH3_Sequence": "",
                    },
                ],
            }
        }

        summary = Orchestrator._propagate_chain_variant_combinations(skeleton, "paper-1")

        child = skeleton["paper-1"]["antibodies"][2]
        self.assertEqual(summary["variants_filled"], 1)
        self.assertGreaterEqual(summary["filled_fields"], 3)
        self.assertEqual(
            child["vh_sequence_aa"],
            skeleton["paper-1"]["antibodies"][0]["vh_sequence_aa"],
        )
        self.assertEqual(
            child["vl_sequence_aa"],
            skeleton["paper-1"]["antibodies"][1]["vl_sequence_aa"],
        )
        self.assertEqual(child["CDRH3_Sequence"], "ARSYPGNGDLGRLDI")

    def test_merge_extractions_can_create_comparator_antibody_from_sequence_image_record(self):
        skeleton = {
            "paper-1": {
                "paper_id": "paper-1",
                "antibodies": [
                    {
                        "Antibody_Name": "SN-101",
                        "Target_Name": "Tn-MUC1 glycopeptide",
                        "Target_Type": "mucins",
                        "Reference_Source": "Wakui et al. Chem Sci 2020",
                        "CDRH3_Sequence": "",
                        "vh_sequence_aa": "",
                        "vl_sequence_aa": "",
                    }
                ],
            }
        }
        extract_results = [
            SimpleNamespace(
                data={
                    "source": "sequence_image_tool",
                    "table_records": [
                        {
                            "mAb": "SM3",
                            "VH_sequence": "VQLQESGGGLVQPGGSMKLSCVASGFTFSNYWMNWVRQSPEKGLEWVAEIRLKSNNYATHYAESVKGRFTISRDDSKSSVYLQMNNLRAEDTGIYYCTGVGQFAYWGQGTTVTVSIVVT",
                            "VL_sequence": "LTTSPGETVTLTCRSSTGAVTTSNYANWVQEKPDHLFTGLIGGTNNRAPGVPARFSGSLIGDKAALTITGAQTEDEAIYFCALWYSNHWVFGGGTKLTV",
                            "_source_category": "SEQUENCE_DATA",
                            "_discovered_from_sequence_image": True,
                        }
                    ],
                }
            )
        ]

        merged, stats = self.orchestrator._merge_extractions(skeleton, "paper-1", extract_results)

        self.assertEqual(len(merged["paper-1"]["antibodies"]), 2)
        created = {ab["Antibody_Name"]: ab for ab in merged["paper-1"]["antibodies"]}["SM3"]
        self.assertEqual(created["Target_Name"], "Tn-MUC1 glycopeptide")
        self.assertTrue(created["vh_sequence_aa"].startswith("VQLQESGGGLVQPGGSMKLS"))
        self.assertTrue(created["vl_sequence_aa"].startswith("LTTSPGETVTLTCRSSTGAV"))
        self.assertEqual(created["Reference_Source"], "Wakui et al. Chem Sci 2020")
        self.assertEqual(stats["matched_antibodies"], 1)

    def test_expand_multi_target_variants_creates_sibling_for_explicit_target(self):
        skeleton = {
            "paper-1": {
                "paper_id": "paper-1",
                "antibodies": [
                    {
                        "Antibody_Name": "Ab1",
                        "Target_Name": "MPXV A35 (Clade IIb)",
                        "Cross_Reactivity": "VACV A33",
                        "Binding_Kinetics_KD": "0.2 nM",
                        "Structure": "A35 complex (PDB: 9XYZ)",
                        "CDRH3_Sequence": "CARDRSTW",
                    }
                ],
            }
        }

        summary = self.orchestrator._expand_multi_target_variants(
            skeleton,
            "paper-1",
            [
                {"mAb": "Ab1", "Target_Name": "MPXV A35 (Clade IIb)", "Binding_Kinetics_KD": "0.2 nM"},
                {"mAb": "Ab1", "Target_Name": "VACV A33", "Binding_Kinetics_KD": "3.6 nM"},
            ],
        )

        antibodies = skeleton["paper-1"]["antibodies"]
        self.assertEqual(len(antibodies), 2)
        self.assertEqual(summary["expanded_records"], 1)

    def test_expand_multi_target_variants_requires_explicit_target_records(self):
        skeleton = {
            "paper-1": {
                "paper_id": "paper-1",
                "antibodies": [
                    {
                        "Antibody_Name": "COVA1-16",
                        "Target_Name": "SARS-CoV-2",
                        "Cross_Reactivity": "SARS-CoV; Bat CoV RaTG13",
                        "Binding_Kinetics_KD": "125 nM",
                    }
                ],
            }
        }

        summary = self.orchestrator._expand_multi_target_variants(
            skeleton,
            "paper-1",
            [
                {"mAb": "COVA1-16", "KD": "125 nM", "_source_context": "cross-reactive binding panel"},
                {"mAb": "COVA1-16", "KD": "405 nM", "_source_context": "cross-reactive binding panel"},
            ],
        )

        self.assertEqual(len(skeleton["paper-1"]["antibodies"]), 1)
        self.assertEqual(summary["expanded_records"], 0)

    def test_expand_multi_target_variants_uses_explicit_record_targets_for_cross_reactive_case(self):
        skeleton = {
            "paper-1": {
                "paper_id": "paper-1",
                "antibodies": [
                    {
                        "Antibody_Name": "EV35-2",
                        "Target_Name": "MPXV A35 (Clade IIb)",
                        "Cross_Reactivity": "VACV A33",
                        "Binding_Kinetics_KD": "3.6 nM",
                        "Structure": "A35 complex (PDB: 9MSN)",
                        "CDRH3_Sequence": "AKIYCRGDCYSYFDYLQYGNSPPPT",
                    }
                ],
            }
        }

        summary = self.orchestrator._expand_multi_target_variants(
            skeleton,
            "paper-1",
            [
                {"mAb": "EV35-2", "Target_Name": "VACV A33", "Binding_Kinetics_KD": "3.6 nM", "_source_context": "panel G EV35-2 VACV A33"},
                {"mAb": "EV35-2", "Target_Name": "MPXV A35 (Clade IIb)", "Binding_Kinetics_KD": "0.2 nM", "_source_context": "panel E EV35-2 MPXV A35"},
            ],
        )

        antibodies = skeleton["paper-1"]["antibodies"]
        self.assertEqual(len(antibodies), 2)
        self.assertEqual(summary["expanded_records"], 1)

        by_target = {ab["Target_Name"]: ab for ab in antibodies}
        self.assertEqual(by_target["MPXV A35 (Clade IIb)"]["Binding_Kinetics_KD"], "0.2 nM")
        self.assertEqual(by_target["VACV A33"]["Binding_Kinetics_KD"], "3.6 nM")
        self.assertEqual(by_target["VACV A33"]["Structure"], "")

    def test_refine_experiment_fields_prefers_local_assay_methods(self):
        skeleton = {
            "paper-1": {
                "paper_id": "paper-1",
                "antibodies": [
                    {
                        "Antibody_Name": "EV35-2",
                        "Target_Name": "MPXV A35 (Clade IIb)",
                        "Cross_Reactivity": "VACV A33",
                        "CDRH3_Sequence": "AKIY",
                        "Experiment": "V(D)J sequencing, X-ray crystallography",
                    },
                    {
                        "Antibody_Name": "EV35-1",
                        "Target_Name": "MPXV A35 (Clade IIb)",
                        "Cross_Reactivity": "VACV A33",
                        "CDRH3_Sequence": "ARGP",
                        "Experiment": "VACV challenge",
                    },
                ],
            }
        }
        summary = self.orchestrator._refine_experiment_fields(
            skeleton,
            "paper-1",
            "body without explicit ELISA words",
            [
                {"mAb": "EV35-2", "Binding_Kinetics_KD": "0.2 nM", "_source_category": "KINETICS_DATA"},
            ],
        )

        antibodies = {ab["Antibody_Name"]: ab for ab in skeleton["paper-1"]["antibodies"]}
        self.assertEqual(antibodies["EV35-2"]["Experiment"], "BLI,ELISA")
        self.assertEqual(antibodies["EV35-1"]["Experiment"], "ELISA")
        self.assertEqual(summary["updated"], 2)


class TestImageExtractAgentHelpers(unittest.TestCase):
    def setUp(self):
        self.agent = ImageExtractAgent.__new__(ImageExtractAgent)
        self.agent.logger = logging.getLogger("test.image_extract")
        self.agent.top_k_images = 5
        self.agent.parallel_limit = 10

    def test_allowed_categories_for_sequence_only_gaps(self):
        targets = [{"antibody_name": "Ab1", "missing_fields": ["CDRH3_Sequence", "vh_sequence_aa"]}]
        self.assertEqual(self.agent._allowed_categories(targets), {"SEQUENCE_DATA"})

    def test_allowed_categories_for_kinetics_only_gaps(self):
        targets = [{"antibody_name": "Ab1", "missing_fields": ["Binding_Kinetics_KD", "Binding_EC50"]}]
        self.assertEqual(
            self.agent._allowed_categories(targets),
            {"KINETICS_DATA", "QUANTITATIVE_TABLE"},
        )

    def test_allowed_categories_for_efficacy_only_gaps(self):
        targets = [{"antibody_name": "Ab1", "missing_fields": ["In_Vivo_Efficacy"]}]
        self.assertEqual(
            self.agent._allowed_categories(targets),
            {"EFFICACY_DATA", "QUANTITATIVE_TABLE"},
        )

    def test_allowed_categories_can_force_sequence_validation(self):
        targets = [{"antibody_name": "Ab1", "missing_fields": ["Binding_Kinetics_KD"]}]
        self.assertEqual(
            self.agent._allowed_categories(targets, force_sequence_images=True),
            {"SEQUENCE_DATA", "KINETICS_DATA", "QUANTITATIVE_TABLE"},
        )

    def test_normalize_category_accepts_partial_sequence_labels(self):
        self.assertEqual(self.agent._normalize_category('SEQUENCE_'), 'SEQUENCE_DATA')
        self.assertEqual(self.agent._normalize_category('sequence-data'), 'SEQUENCE_DATA')
        self.assertEqual(self.agent._normalize_category('SEQUENCE'), 'SEQUENCE_DATA')

    def test_should_preserve_known_sequence_image_category(self):
        refs = [{"rel_path": "images/fig1.jpg", "context": "ctx", "abs_path": "/tmp/f.jpg", "category": "SEQUENCE_DATA"}]

        async def run_test():
            kept = await self.agent._triage_images(refs, {"SEQUENCE_DATA"})
            self.assertEqual(len(kept), 1)
            self.assertEqual(kept[0]["category"], "SEQUENCE_DATA")

        import asyncio
        asyncio.run(run_test())

    def test_triage_images_runs_concurrently(self):
        class StubVLM:
            def __init__(self):
                self.active = 0
                self.max_active = 0

            async def chat_with_images(self, **kwargs):
                self.active += 1
                self.max_active = max(self.max_active, self.active)
                await asyncio.sleep(0.01)
                self.active -= 1

                class Resp:
                    content = "SEQUENCE_DATA"

                return Resp()

        self.agent.vlm = StubVLM()
        self.agent._triage_prompt = "triage"
        refs = [
            {"rel_path": f"images/fig{i}.jpg", "context": "Ab1 sequence panel", "abs_path": f"/tmp/f{i}.jpg", "alt_text": ""}
            for i in range(10)
        ]

        async def run_test():
            kept = await self.agent._triage_images(refs, {"SEQUENCE_DATA"})
            self.assertEqual(len(kept), 10)
            self.assertGreater(self.agent.vlm.max_active, 1)

        asyncio.run(run_test())

    def test_extract_from_images_runs_concurrently(self):
        class StubVLM:
            def __init__(self):
                self.active = 0
                self.max_active = 0

            async def chat_with_images(self, **kwargs):
                self.active += 1
                self.max_active = max(self.max_active, self.active)
                await asyncio.sleep(0.01)
                self.active -= 1

                class Resp:
                    content = '[{"mAb":"Ab1","Binding_Kinetics_KD":"1 nM"}]'

                return Resp()

        self.agent.vlm = StubVLM()
        self.agent._extract_prompt = "extract"
        refs = [
            {
                "rel_path": f"images/fig{i}.jpg",
                "context": "Ab1 kd by BLI",
                "abs_path": f"/tmp/f{i}.jpg",
                "alt_text": "",
                "category": "KINETICS_DATA",
            }
            for i in range(10)
        ]
        targets = [{"antibody_name": "Ab1", "missing_fields": ["Binding_Kinetics_KD"]}]

        async def run_test():
            records = await self.agent._extract_from_images(refs, targets)
            self.assertEqual(len(records), 10)
            self.assertGreater(self.agent.vlm.max_active, 1)

        asyncio.run(run_test())

    def test_build_extract_user_text_includes_targeted_antibodies(self):
        ref = {"context": "Figure 4 shows Ab1 and Ab2 kinetics curves."}
        text = self.agent._build_extract_user_text(
            ref,
            "KINETICS_DATA",
            [
                {"antibody_name": "Ab1", "missing_fields": ["Binding_Kinetics_KD"]},
                {"antibody_name": "Ab2", "missing_fields": ["Binding_EC50"]},
            ],
        )
        self.assertIn("Ab1", text)
        self.assertIn("Binding_Kinetics_KD", text)
        self.assertIn("Ab2", text)
        self.assertIn("只为当前 JSON 骨架中已有抗体补充缺失字段", text)

    def test_filter_records_drops_efficacy_without_name_anchor(self):
        ref = {"context": "Whole body survival curve EV35-2 EV35-6 EV35-7"}
        records = [
            {"mAb": "EV35-2", "In_Vivo_Efficacy": "protection:100% survival at 150 μg"},
            {"mAb": "EV35-1", "In_Vivo_Efficacy": "protection:100% survival at 150 μg"},
        ]
        filtered = self.agent._filter_records(records, ref, {"ev35-1", "ev35-2", "ev35-6", "ev35-7"})
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["mAb"], "EV35-2")

    def test_resolve_image_path_falls_back_to_section_hash(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            images_dir = os.path.join(tmpdir, "images")
            os.makedirs(images_dir, exist_ok=True)
            real_path = os.path.join(images_dir, "abcdef1234567890abcdef1234567890.jpg")
            with open(real_path, "wb") as f:
                f.write(b"fake")

            md_text = (
                "# abcdef1234567890abcdef1234567890\n\n"
                "![](images/missing-reference.jpg)\n"
            )
            match_start = md_text.index("![](")
            resolved = self.agent._resolve_image_path(
                tmpdir,
                "images/missing-reference.jpg",
                md_text,
                match_start,
            )
            self.assertEqual(resolved, real_path)

    def test_select_top_relevant_images_prefers_known_and_target_hits(self):
        refs = [
            {"rel_path": "images/fig0.jpg", "context": "overview", "abs_path": "/tmp/a.jpg", "alt_text": ""},
            {"rel_path": "images/fig1.jpg", "context": "Ab1 sequence alignment heavy chain", "abs_path": "/tmp/b.jpg", "alt_text": ""},
            {"rel_path": "images/fig2.jpg", "context": "Ab1 kd by BLI", "abs_path": "/tmp/c.jpg", "alt_text": ""},
            {"rel_path": "images/fig3.jpg", "context": "mouse survival curve for Ab1", "abs_path": "/tmp/d.jpg", "alt_text": ""},
            {"rel_path": "images/fig4.jpg", "context": "Ab2 sequence alignment", "abs_path": "/tmp/e.jpg", "alt_text": ""},
            {"rel_path": "images/fig5.jpg", "context": "irrelevant microscopy", "abs_path": "/tmp/f.jpg", "alt_text": ""},
        ]
        targets = [
            {"antibody_name": "Ab1", "missing_fields": ["CDRH3_Sequence", "Binding_Kinetics_KD", "In_Vivo_Efficacy"]}
        ]

        selected = self.agent._select_top_relevant_images(
            refs,
            targets,
            {"SEQUENCE_DATA", "KINETICS_DATA", "QUANTITATIVE_TABLE", "EFFICACY_DATA"},
            {"images/fig4.jpg"},
        )

        self.assertEqual(len(selected), 5)
        self.assertEqual(selected[0]["rel_path"], "images/fig4.jpg")
        self.assertNotEqual(selected[-1]["rel_path"], "images/fig5.jpg")

    def test_image_relevance_score_boosts_antibody_cluster_alignment_context(self):
        plain_ref = {"rel_path": "images/plain.jpg", "context": "overview panel", "abs_path": "/tmp/a.jpg", "alt_text": ""}
        cluster_ref = {
            "rel_path": "images/cluster.jpg",
            "context": (
                "2C08 S2E12 C121 REGN10987\n"
                "<!-- OCR extracted from image -->\n"
                "2C08\nS2E12\nC121\nREGN10987\n"
                "EVQLVQSGPEVKKPGTSVRVSCKASGFTFTSSAVQWVRQARGQRLEWIGWVISPSSGGTNYAQKFQGRVTITADESTSTAYMELSSLRSEDTAVYYCARTAGRGGWYFDLWGQGTLVTVSS\n"
                "................................................................................................................................................\n"
                "................................................................................................................................................\n"
                "................................................................................................................................................\n"
                "................................................................................................................................................\n"
                "<!-- end OCR -->"
            ),
            "abs_path": "/tmp/b.jpg",
            "alt_text": "",
        }
        targets = [{"antibody_name": "2C08", "missing_fields": ["vh_sequence_aa"]}]

        plain_score = self.agent._image_relevance_score(plain_ref, targets, {"SEQUENCE_DATA"}, set())
        cluster_score = self.agent._image_relevance_score(cluster_ref, targets, {"SEQUENCE_DATA"}, set())

        self.assertGreater(cluster_score, plain_score)

    def test_select_top_relevant_images_keeps_neighboring_sequence_panels(self):
        self.agent.top_k_images = 2
        refs = [
            {"rel_path": "images/fig0.jpg", "context": "overview", "abs_path": "/tmp/a.jpg", "alt_text": ""},
            {
                "rel_path": "images/fig1.jpg",
                "context": (
                    "2C08 S2E12 C121 REGN10987\n"
                    "<!-- OCR extracted from image -->\n"
                    "2C08\nS2E12\nC121\nREGN10987\n"
                    "EVQLVQSGPEVKKPGTSVRVSCKASGFTFTSSAVQWVRQARGQRLEWIGWVISPSSGGTNYAQKFQGRVTITADESTSTAYMELSSLRSEDTAVYYCARTAGRGGWYFDLWGQGTLVTVSS\n"
                    "................................................................................................................................................\n"
                    "................................................................................................................................................\n"
                    "................................................................................................................................................\n"
                    "................................................................................................................................................\n"
                    "<!-- end OCR -->"
                ),
                "abs_path": "/tmp/b.jpg",
                "alt_text": "",
            },
            {
                "rel_path": "images/fig2.jpg",
                "context": "2C08 S2E12 C121 REGN10987 light panel with antibody rows but no explicit keyword",
                "abs_path": "/tmp/c.jpg",
                "alt_text": "",
            },
            {"rel_path": "images/fig3.jpg", "context": "irrelevant microscopy panel", "abs_path": "/tmp/d.jpg", "alt_text": ""},
        ]
        targets = [{"antibody_name": "2C08", "missing_fields": ["vh_sequence_aa", "vl_sequence_aa"]}]

        selected = self.agent._select_top_relevant_images(refs, targets, {"SEQUENCE_DATA"}, set())

        self.assertEqual([ref["rel_path"] for ref in selected], ["images/fig1.jpg", "images/fig2.jpg"])


if __name__ == "__main__":
    unittest.main()
