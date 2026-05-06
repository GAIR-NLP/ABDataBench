"""Tests for agent/agents/skeleton_agent.py — field normalization logic."""

import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from agents.skeleton_agent import SkeletonAgent
from config import Config


class FakeConfig(Config):
    mock_llm: bool = True


class TestFixAntibodyFields(unittest.TestCase):
    """Test _fix_antibody_fields for v3 schema normalization."""

    def setUp(self):
        self.agent = SkeletonAgent.__new__(SkeletonAgent)
        self.agent.name = "skeleton"
        self.agent.config = FakeConfig()
        import logging
        self.agent.logger = logging.getLogger("test")

    def test_experiment_value_list_to_binding_kinetics(self):
        """Experiment_value list should be split into Binding_Kinetics_KD/EC50/kon/koff."""
        ab = {
            "Experiment_value": [
                {"assay": "SPR KD", "value": "6.91 nM"},
                {"assay": "ELISA EC50", "value": "0.5 nM"},
                {"assay": "SPR kon", "value": "1.74e7 1/Ms"},
                {"assay": "SPR koff", "value": "1.2e-4 1/s"},
            ]
        }
        self.agent._fix_antibody_fields(ab)
        self.assertNotIn("Experiment_value", ab)
        self.assertEqual(ab["Binding_Kinetics_KD"], "6.91 nM")
        self.assertEqual(ab["Binding_EC50"], "0.5 nM")
        self.assertEqual(ab["Binding_Kinetics_kon"], "1.74e7 1/Ms")
        self.assertEqual(ab["Binding_Kinetics_koff"], "1.2e-4 1/s")

    def test_experiment_value_string_to_kd(self):
        """Experiment_value as plain string → Binding_Kinetics_KD."""
        ab = {"Experiment_value": "6.91 nM"}
        self.agent._fix_antibody_fields(ab)
        self.assertNotIn("Experiment_value", ab)
        self.assertEqual(ab["Binding_Kinetics_KD"], "6.91 nM")

    def test_affinity_nm_to_binding_kinetics_kd(self):
        """Legacy Affinity_nM → Binding_Kinetics_KD."""
        ab = {"Affinity_nM": "45 pM"}
        self.agent._fix_antibody_fields(ab)
        self.assertNotIn("Affinity_nM", ab)
        self.assertEqual(ab["Binding_Kinetics_KD"], "45 pM")

    def test_affinity_nm_no_overwrite(self):
        """Affinity_nM should not overwrite existing Binding_Kinetics_KD."""
        ab = {"Affinity_nM": "45 pM", "Binding_Kinetics_KD": "6.91 nM"}
        self.agent._fix_antibody_fields(ab)
        self.assertEqual(ab["Binding_Kinetics_KD"], "6.91 nM")
        self.assertNotIn("Affinity_nM", ab)

    def test_external_database_id_to_structure(self):
        """External_Database_ID → Structure."""
        ab = {"External_Database_ID": {"value": "PDB: 6WPT", "action": "API Fetch"}}
        self.agent._fix_antibody_fields(ab)
        self.assertNotIn("External_Database_ID", ab)
        self.assertEqual(ab["Structure"], "PDB: 6WPT")

    def test_pk_source_removed(self):
        """PK_source should be dropped."""
        ab = {"PK_source": "Cynomolgus monkeys"}
        self.agent._fix_antibody_fields(ab)
        self.assertNotIn("PK_source", ab)

    def test_flatten_nested_value_dicts(self):
        """Nested {value, quote} dicts should be flattened to plain strings."""
        ab = {
            "Target_Name": {"value": "Spike RBD", "quote": "The Spike..."},
            "Antibody_Type": {"value": "IgG1", "quote": "..."},
        }
        self.agent._fix_antibody_fields(ab)
        self.assertEqual(ab["Target_Name"], "Spike RBD")
        self.assertEqual(ab["Antibody_Type"], "IgG1")

    def test_structured_moa_flattened(self):
        """Structured Mechanism_of_Action list should be flattened."""
        ab = {
            "Mechanism_of_Action": [
                {
                    "MoA_Type": {"value": "Neutralization", "quote": "..."},
                    "Quantitative_Metric": {
                        "metric_name": "IC50",
                        "metric_value": "0.05 ug/mL",
                        "pointer": "Figure 4B",
                        "action": "Script Extract",
                    },
                },
                {
                    "MoA_Type": {"value": "ADCC", "quote": "..."},
                    "Quantitative_Metric": {
                        "metric_name": "Max Lysis",
                        "metric_value": "85%",
                        "pointer": "Figure 5",
                        "action": "Script Extract",
                    },
                },
            ]
        }
        self.agent._fix_antibody_fields(ab)
        self.assertEqual(ab["Mechanism_of_Action"], "Neutralization; ADCC")
        self.assertEqual(ab["Quantitative_Metric"], "IC50 = 0.05 ug/mL; Max Lysis = 85%")

    def test_vh_germline_not_merged_into_full_sequence(self):
        """VH_Germline should be dropped instead of being treated as a full VH sequence."""
        ab = {"VH_Germline": "VH4-4/JH3(93%)", "vh_sequence_aa": ""}
        self.agent._fix_antibody_fields(ab)
        self.assertEqual(ab["vh_sequence_aa"], "")
        self.assertNotIn("VH_Germline", ab)

    def test_vh_germline_no_overwrite(self):
        """Dropping VH_Germline should not affect an existing full VH sequence."""
        ab = {
            "VH_Germline": "VH4-4/JH3(93%)",
            "vh_sequence_aa": "EVQLVESGGGLVQPGGSLRLSCAASGFTFSSYAMSWVRQAPGKGLEWVSAISSGGGSTYYADSVKGRFTISRDNAKNTLYLQMNSLRAEDTAVYYCARDRSTGYYYYFDYWGQGTLVTVSS",
        }
        self.agent._fix_antibody_fields(ab)
        self.assertEqual(
            ab["vh_sequence_aa"],
            "EVQLVESGGGLVQPGGSLRLSCAASGFTFSSYAMSWVRQAPGKGLEWVSAISSGGGSTYYADSVKGRFTISRDNAKNTLYLQMNSLRAEDTAVYYCARDRSTGYYYYFDYWGQGTLVTVSS",
        )

    def test_germline_annotation_is_cleared_from_sequence_field(self):
        """Germline annotations are not valid vh_sequence_aa values."""
        ab = {"vh_sequence_aa": "VH4-4/JH3 (V identity 93%)"}
        self.agent._fix_antibody_fields(ab)
        self.assertEqual(ab["vh_sequence_aa"], "")

    def test_full_variable_sequence_is_preserved_and_normalized(self):
        ab = {
            "vh_sequence_aa": " EVQLVESGGGLVQPGGSLRLSCAASGFTFSSYAMSWVRQAPGKGLEWVSAISSGGGSTYYADSVKGRFTISRDNAKNTLYLQMNSLRAEDTAVYYCARDRSTGYYYYFDYWGQGTLVTVSS "
        }
        self.agent._fix_antibody_fields(ab)
        self.assertEqual(
            ab["vh_sequence_aa"],
            "EVQLVESGGGLVQPGGSLRLSCAASGFTFSSYAMSWVRQAPGKGLEWVSAISSGGGSTYYADSVKGRFTISRDNAKNTLYLQMNSLRAEDTAVYYCARDRSTGYYYYFDYWGQGTLVTVSS",
        )

    def test_cdrh3_sequence_is_preserved_and_normalized(self):
        ab = {"CDRH3_Sequence": " C ARD-RSTGYYYYFDYW "}
        self.agent._fix_antibody_fields(ab)
        self.assertEqual(ab["CDRH3_Sequence"], "CARDRSTGYYYYFDYW")

    def test_cdrh3_three_letter_sequence_is_converted_to_one_letter(self):
        ab = {"CDRH3_Sequence": "Asp Leu Pro Gly Ile Ala Val Ala Gly Tyr"}
        self.agent._fix_antibody_fields(ab)
        self.assertEqual(ab["CDRH3_Sequence"], "DLPGIAVAGY")

    def test_vh_three_letter_sequence_is_converted_to_one_letter(self):
        ab = {
            "vh_sequence_aa": (
                "Glu Val Gln Leu Leu Glu Ser Gly Gly Gly Leu Val Gln Pro Gly Gly Ser "
                "Leu Arg Leu Ser Cys Ala Ala Ser Gly Phe Thr Phe Gly Asn Ser Trp Met "
                "Ser Trp Val Arg Gln Ala Pro Gly Lys Gly Leu Glu Trp Val Ser Ala Ile "
                "Ser Gly Ser Gly Gly Ser Thr Tyr Tyr Ala Asp Ser Val Lys Gly Arg Phe "
                "Thr Ile Ser Arg Asp Asn Ser Lys Asn Thr Leu Tyr Leu Gln Met Asn Ser "
                "Leu Arg Ala Glu Asp Thr Ala Val Tyr Tyr Cys Thr Arg Asp Leu Pro Gly "
                "Ile Ala Val Ala Gly Tyr Trp Gly Gln Gly Thr Leu Val Thr Val Ser Ser"
            )
        }
        self.agent._fix_antibody_fields(ab)
        self.assertTrue(ab["vh_sequence_aa"].startswith("EVQLLESGGGLVQPGGSLRLSCAASGFTFGNSWMSWVRQAPGK"))
        self.assertTrue(ab["vh_sequence_aa"].endswith("CTRDLPGIAVAGYWGQGTLVTVSS"))
        self.assertGreaterEqual(len(ab["vh_sequence_aa"]), 110)

    def test_cdrh3_placeholder_text_is_cleared(self):
        ab = {"CDRH3_Sequence": "Sequence not provided in text or images"}
        self.agent._fix_antibody_fields(ab)
        self.assertEqual(ab["CDRH3_Sequence"], "")

    def test_sequence_pointer_metadata_is_preserved_for_api_backfill(self):
        ab = {
            "vh_sequence_aa": {
                "pointer": "GenBank PQ382870; Table-S1-(IGHV4-59 lineage)",
                "action": "API Fetch",
                "quote": "PQ382870 was deposited for this clonal lineage.",
            }
        }
        self.agent._fix_antibody_fields(ab)
        self.assertEqual(ab["vh_sequence_aa"], "")
        self.assertIn("_field_hints", ab)
        self.assertEqual(ab["_field_hints"]["vh_sequence_aa"]["pointer"], "GenBank PQ382870; Table-S1-(IGHV4-59 lineage)")
        self.assertEqual(ab["_field_hints"]["vh_sequence_aa"]["action"], "API Fetch")

    def test_experiment_is_reduced_to_direct_methods(self):
        ab = {"Experiment": "Flow cytometry (sporozoite binding), ELISA, Western blot, ITC, X-ray crystallography"}
        self.agent._fix_antibody_fields(ab)
        self.assertEqual(ab["Experiment"], "Flow Cytometry, ELISA, ITC")

    def test_reference_source_is_normalized_to_compact_gbt_style(self):
        ab = {"Reference_Source": "Science 2025 (Dacon et al.), DOI: 10.1126/science.adr0510"}
        self.agent._fix_antibody_fields(ab)
        self.assertEqual(ab["Reference_Source"], "Dacon et al. Science, 2025. DOI: 10.1126/science.adr0510")


class TestFilterNonCore(unittest.TestCase):
    """Test _filter_non_core for antibody filtering."""

    def setUp(self):
        self.agent = SkeletonAgent.__new__(SkeletonAgent)
        self.agent.name = "skeleton"
        self.agent.config = FakeConfig()
        import logging
        self.agent.logger = logging.getLogger("test")

    def test_keep_normal_antibody(self):
        skeleton = {
            "paper1": {
                "paper_id": "paper1",
                "antibodies": [
                    {"Antibody_Name": "Ab1", "Target_Name": "Spike", "CDRH3_Sequence": "CARDRSTG"}
                ],
            }
        }
        result = self.agent._filter_non_core(skeleton, "paper1")
        self.assertEqual(len(result["paper1"]["antibodies"]), 1)

    def test_filter_failed_candidate(self):
        skeleton = {
            "paper1": {
                "paper_id": "paper1",
                "antibodies": [
                    {"Antibody_Name": "FailedAb", "Target_Name": "amplification failed",
                     "Mechanism_of_Action": "", "CDRH3_Sequence": "", "vh_sequence_aa": "", "vl_sequence_aa": ""}
                ],
            }
        }
        result = self.agent._filter_non_core(skeleton, "paper1")
        self.assertEqual(len(result["paper1"]["antibodies"]), 0)


class TestSequenceImageHints(unittest.TestCase):
    def setUp(self):
        self.agent = SkeletonAgent.__new__(SkeletonAgent)
        self.agent.name = "skeleton"
        self.agent.config = FakeConfig()
        import logging
        self.agent.logger = logging.getLogger("test")

    def test_reference_only_sequence_image_hints_are_suppressed(self):
        payload = {
            "table_records": [
                {
                    "mAb": "S2E12",
                    "CDRH3": "CASPYCSGGSCSDGFDIW",
                    "_source_image": "images/fig3e.jpg",
                    "_source_context": (
                        "Figure 3. Sequence alignment of 2C08 with RBD-binding mAbs from SARS-CoV-2 "
                        "infected patients and vaccinees. previously described human mAb S2E12."
                    ),
                },
                {
                    "mAb": "2C08",
                    "CDRH3": "CAAAYCSGGSCSDGFDIW",
                    "_source_image": "images/fig3e.jpg",
                    "_source_context": "Figure 3. mAb 2C08 recognizes a public epitope in SARS-CoV-2 RBD.",
                },
            ]
        }

        hints = SkeletonAgent._format_sequence_image_hints(payload)

        self.assertIn("2C08", hints)
        self.assertNotIn("S2E12", hints)

    def test_filter_control_no_data(self):
        """Control antibody without seq or KD should be filtered."""
        skeleton = {
            "paper1": {
                "paper_id": "paper1",
                "antibodies": [
                    {"Antibody_Name": "CtrlAb", "Target_Name": "used as control",
                     "Mechanism_of_Action": "", "CDRH3_Sequence": "", "vh_sequence_aa": "",
                     "vl_sequence_aa": "", "Binding_Kinetics_KD": ""}
                ],
            }
        }
        result = self.agent._filter_non_core(skeleton, "paper1")
        self.assertEqual(len(result["paper1"]["antibodies"]), 0)

    def test_keep_control_with_sequence(self):
        """Control antibody WITH sequence data should be kept."""
        skeleton = {
            "paper1": {
                "paper_id": "paper1",
                "antibodies": [
                    {"Antibody_Name": "CtrlAb", "Target_Name": "used as control",
                     "Mechanism_of_Action": "", "CDRH3_Sequence": "CARDRSTG",
                     "vh_sequence_aa": "", "vl_sequence_aa": ""}
                ],
            }
        }
        result = self.agent._filter_non_core(skeleton, "paper1")
        self.assertEqual(len(result["paper1"]["antibodies"]), 1)


class TestNormalize(unittest.TestCase):
    """Test _normalize for different LLM output formats."""

    def setUp(self):
        self.agent = SkeletonAgent.__new__(SkeletonAgent)
        self.agent.name = "skeleton"
        self.agent.config = FakeConfig()
        import logging
        self.agent.logger = logging.getLogger("test")

    def test_already_correct_format(self):
        data = {"paper1": {"paper_id": "paper1", "antibodies": [{"Antibody_Name": "Ab1"}]}}
        result = self.agent._normalize(data, "paper1")
        self.assertIn("paper1", result)
        self.assertEqual(len(result["paper1"]["antibodies"]), 1)

    def test_flat_antibodies_list(self):
        data = [{"Antibody_Name": "Ab1"}, {"Antibody_Name": "Ab2"}]
        result = self.agent._normalize(data, "paper1")
        self.assertIn("paper1", result)
        self.assertEqual(len(result["paper1"]["antibodies"]), 2)

    def test_unnested_dict(self):
        data = {"antibodies": [{"Antibody_Name": "Ab1"}]}
        result = self.agent._normalize(data, "paper1")
        self.assertIn("paper1", result)
        self.assertEqual(len(result["paper1"]["antibodies"]), 1)


class TestMergePageAntibodies(unittest.TestCase):
    def setUp(self):
        self.agent = SkeletonAgent.__new__(SkeletonAgent)
        self.agent.name = "skeleton"
        self.agent.config = FakeConfig()
        import logging
        self.agent.logger = logging.getLogger("test")

    def test_same_name_different_target_kept_as_two_records(self):
        combined = [{"Antibody_Name": "EV35-2", "Target_Name": "MPXV A35", "Antibody_Type": "IgG"}]
        page = [{"Antibody_Name": "EV35-2", "Target_Name": "VACV A33", "Antibody_Type": "IgG"}]
        added = self.agent._merge_page_antibodies(combined, page)
        self.assertEqual(added, 1)
        self.assertEqual(len(combined), 2)


if __name__ == "__main__":
    unittest.main()
