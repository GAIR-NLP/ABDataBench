"""Tests for agent/tools/bio_validator.py"""

import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tools.bio_validator import BioValidator, FIELD_NAME_CORRECTIONS, _fuzzy_get


class TestFieldNameCorrections(unittest.TestCase):
    """Test that legacy field names are flagged for correction."""

    def setUp(self):
        self.validator = BioValidator()

    def test_legacy_experiment_value_corrected(self):
        ab = {"Experiment_value": "some value", "Antibody_Name": "X"}
        result = self.validator._validate_field_names(ab)
        msgs = [r["message"] for r in result]
        self.assertTrue(any("Experiment_value" in m and "Binding_Kinetics_KD" in m for m in msgs))

    def test_legacy_affinity_corrected(self):
        ab = {"Affinity_nM": "6.91 nM", "Antibody_Name": "X"}
        result = self.validator._validate_field_names(ab)
        msgs = [r["message"] for r in result]
        self.assertTrue(any("Affinity_nM" in m and "Binding_Kinetics_KD" in m for m in msgs))

    def test_legacy_pk_source_corrected(self):
        ab = {"PK_source": "mouse", "Antibody_Name": "X"}
        result = self.validator._validate_field_names(ab)
        msgs = [r["message"] for r in result]
        self.assertTrue(any("PK_source" in m and "source" in m for m in msgs))

    def test_legacy_external_db_corrected(self):
        ab = {"External_Database_ID": "6WPT", "Antibody_Name": "X"}
        result = self.validator._validate_field_names(ab)
        msgs = [r["message"] for r in result]
        self.assertTrue(any("External_Database_ID" in m and "Structure" in m for m in msgs))

    def test_no_corrections_for_valid_fields(self):
        ab = {
            "Antibody_Name": "X", "Antibody_Type": "IgG1",
            "Binding_Kinetics_KD": "6.91 nM", "Structure": "PDB: 6WPT",
        }
        result = self.validator._validate_field_names(ab)
        self.assertEqual(len(result), 0)


class TestRequiredFields(unittest.TestCase):
    """Test required and recommended field validation."""

    def setUp(self):
        self.validator = BioValidator()

    def test_all_required_present(self):
        ab = {
            "Antibody_Name": "X", "Antibody_Type": "IgG1",
            "Target_Name": "Spike", "Experiment": "SPR",
            "CDRH3_Sequence": "CARDRSTG", "vh_sequence_aa": "EVQL...",
            "vl_sequence_aa": "DIQM...", "Reference_Source": "Nature 2024",
        }
        result = self.validator._validate_required_fields(ab)
        warns = [r for r in result if r["status"] == "warn"]
        self.assertEqual(len(warns), 0)

    def test_missing_required_fields_warned(self):
        ab = {"Antibody_Name": "X"}
        result = self.validator._validate_required_fields(ab)
        warns = [r for r in result if r["status"] == "warn"]
        self.assertGreater(len(warns), 0)
        missing_fields = " ".join(r["message"] for r in warns)
        self.assertIn("Antibody_Type", missing_fields)
        self.assertIn("Target_Name", missing_fields)

    def test_recommended_fields_info(self):
        ab = {
            "Antibody_Name": "X", "Antibody_Type": "IgG1",
            "Target_Name": "Spike", "Experiment": "SPR",
            "CDRH3_Sequence": "CARDRSTG", "vh_sequence_aa": "EVQL...",
            "vl_sequence_aa": "DIQM...", "Reference_Source": "Nature 2024",
        }
        result = self.validator._validate_required_fields(ab)
        info_msgs = [r for r in result if r["status"] == "info"]
        info_fields = " ".join(r["message"] for r in info_msgs)
        self.assertIn("Binding_Kinetics_KD", info_fields)
        self.assertIn("Mechanism_of_Action", info_fields)


class TestSequenceValidation(unittest.TestCase):
    """Test amino acid sequence validation."""

    def setUp(self):
        self.validator = BioValidator()

    def test_valid_cdrh3(self):
        result = self.validator._validate_aa_chars("CARDRSTGYYYYFDYW", "CDRH3")
        self.assertEqual(result[0]["status"], "pass")

    def test_invalid_aa_chars(self):
        result = self.validator._validate_aa_chars("CARD1STGX", "CDRH3")
        # '1' is not in standard AA set
        self.assertEqual(result[0]["status"], "fail")

    def test_empty_sequence_skip(self):
        result = self.validator._validate_aa_chars("N/A", "CDRH3")
        self.assertEqual(result[0]["status"], "skip")

    def test_cdrh3_length_ok(self):
        result = self.validator._validate_cdr3_length("CARDRSTGYYYYFDYW", "CDRH3", "H")
        self.assertEqual(result[0]["status"], "pass")

    def test_cdrh3_anchors(self):
        result = self.validator._validate_cdr3_anchors("CARDRSTGYYYYFDYW", "CDRH3", "H")
        n_anchor = next(r for r in result if "n_anchor" in r["check"])
        self.assertEqual(n_anchor["status"], "pass")  # starts with C
        c_anchor = next(r for r in result if "c_anchor" in r["check"])
        self.assertEqual(c_anchor["status"], "pass")  # ends with W


class TestDuplicateDetection(unittest.TestCase):
    """Test duplicate sequence detection."""

    def setUp(self):
        self.validator = BioValidator()

    def test_detect_duplicate_cdrh3(self):
        skeleton = [
            {"Antibody_Name": "Ab1", "CDRH3_Sequence": "CARDRSTGYYYYFDYW"},
            {"Antibody_Name": "Ab2", "CDRH3_Sequence": "CARDRSTGYYYYFDYW"},
        ]
        dups = self.validator.detect_duplicates(skeleton)
        self.assertEqual(len(dups), 1)
        self.assertEqual(dups[0]["status"], "warn")

    def test_no_duplicates(self):
        skeleton = [
            {"Antibody_Name": "Ab1", "CDRH3_Sequence": "CARDRSTGYYYYFDYW"},
            {"Antibody_Name": "Ab2", "CDRH3_Sequence": "CAREVVVVVGMDVW"},
        ]
        dups = self.validator.detect_duplicates(skeleton)
        self.assertEqual(len(dups), 0)


class TestFullValidation(unittest.TestCase):
    """Test full antibody validation with 22-field schema."""

    def setUp(self):
        self.validator = BioValidator()

    def test_complete_v3_antibody(self):
        ab = {
            "Antibody_Name": "mAb-1",
            "Antibody_Type": "IgG1",
            "Antibody_Isotype": "Human IgG1",
            "source": "Human",
            "Target_Name": "SARS-CoV-2 Spike RBD",
            "Target_Type": "Viral surface glycoprotein",
            "Cross_Reactivity": "SARS-CoV-1",
            "Epitope": "RBD",
            "Experiment": "SPR, ELISA",
            "Binding_Kinetics_KD": "6.91 nM",
            "Binding_Kinetics_kon": "1.74e7 1/Ms",
            "Binding_Kinetics_koff": "1.2e-4 1/s",
            "Binding_EC50": "0.5 nM",
            "Mechanism_of_Action": "Neutralization",
            "Quantitative_Metric": "IC50 = 0.05 ug/mL",
            "Structure": "Cryo-EM 3.2 Å (PDB: 7XYZ)",
            "CDRH3_Sequence": "CARDRSTGYYYYFDYW",
            "vh_sequence_aa": "EVQLVESGGGLVQPGGSLRLSCAASGFTFSSYAMSWVRQAPGKGLEWVSAISSGGGSTYYADSVKGRFTISRDNAKNTLYLQMNSLRAEDTAVYYCARDRSTGYYYYFDYWGQGTLVTVSS",
            "vl_sequence_aa": "DIQMTQSPSSLSASVGDRVTITCRASQDISNYLNWYQQKPGKAPKLLIYAASSLQSGVPSRFSGSGSGTDFTLTISSLQPEDFATYYCQQYNSYPLTFGQGTKVEIK",
            "Thermal_Stability_Tm": "65.3°C",
            "In_Vivo_Half_Life": "21 days",
            "In_Vivo_Efficacy": "100% survival at 10 mg/kg",
            "Reference_Source": "Nature 2024 (Smith et al.)",
        }
        result = self.validator.validate_antibody(ab)
        # Should have no field name warnings (all v3 field names)
        field_name_checks = [c for c in result["checks"] if c["check"] == "field_name"]
        self.assertEqual(len(field_name_checks), 0)
        # Should have no missing required fields
        missing_checks = [c for c in result["checks"] if c["check"] == "missing_field"]
        self.assertEqual(len(missing_checks), 0)

    def test_experiment_with_peripheral_methods_warns(self):
        ab = {
            "Antibody_Name": "mAb-1",
            "Antibody_Type": "IgG1",
            "Target_Name": "Spike",
            "Experiment": "ELISA, Western blot, mouse model",
            "CDRH3_Sequence": "CARDRSTGYYYYFDYW",
            "vh_sequence_aa": "EVQLVESGGGLVQPGGSLRLSCAASGFTFSSYAMSWVRQAPGKGLEWVSAISSGGGSTYYADSVKGRFTISRDNAKNTLYLQMNSLRAEDTAVYYCARDRSTGYYYYFDYWGQGTLVTVSS",
            "vl_sequence_aa": "DIQMTQSPSSLSASVGDRVTITCRASQDISNYLNWYQQKPGKAPKLLIYAASSLQSGVPSRFSGSGSGTDFTLTISSLQPEDFATYYCQQYNSYPLTFGQGTKVEIK",
            "Reference_Source": "Nature 2024 (Smith et al.)",
        }
        result = self.validator.validate_antibody(ab)
        warnings = [c for c in result["checks"] if c["check"] == "experiment_scope"]
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]["status"], "warn")


class TestFuzzyGet(unittest.TestCase):
    """Test _fuzzy_get helper for key aliases."""

    def test_direct_key(self):
        entry = {"Antibody_Name": "X"}
        self.assertEqual(_fuzzy_get(entry, ["Antibody_Name"], "default"), "X")

    def test_alias_key(self):
        entry = {"mAb": "Y"}
        from tools.bio_validator import AB_NAME_KEYS
        self.assertEqual(_fuzzy_get(entry, AB_NAME_KEYS, "default"), "Y")

    def test_nested_dict_value(self):
        entry = {"Antibody_Name": {"value": "Z", "quote": "..."}}
        self.assertEqual(_fuzzy_get(entry, ["Antibody_Name"], "default"), "Z")

    def test_missing_key(self):
        entry = {"other": "val"}
        self.assertEqual(_fuzzy_get(entry, ["Antibody_Name"], "default"), "default")


if __name__ == "__main__":
    unittest.main()
