"""Tests for benchmark/scripts/unit_parser.py"""

import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "benchmark", "scripts"))
from unit_parser import parse_numeric_value, try_numeric_match, NUMERIC_FIELDS


class TestParseConcentration(unittest.TestCase):
    """Test KD/EC50 concentration parsing with unit conversion."""

    def test_nm_value(self):
        v = parse_numeric_value("6.91 nM", "Binding_Kinetics_KD")
        self.assertAlmostEqual(v, 6.91, places=2)

    def test_pm_to_nm(self):
        v = parse_numeric_value("45 pM", "Binding_Kinetics_KD")
        self.assertAlmostEqual(v, 0.045, places=4)

    def test_um_to_nm(self):
        v = parse_numeric_value("1.2 μM", "Binding_Kinetics_KD")
        self.assertAlmostEqual(v, 1200, places=0)

    def test_kd_with_prefix(self):
        v = parse_numeric_value("KD = 6.91 nM", "Binding_Kinetics_KD")
        self.assertAlmostEqual(v, 6.91, places=2)

    def test_ec50(self):
        v = parse_numeric_value("0.5 nM", "Binding_EC50")
        self.assertAlmostEqual(v, 0.5, places=2)


class TestParseScientificNotation(unittest.TestCase):
    """Test kon/koff scientific notation parsing."""

    def test_kon_unicode_multiply(self):
        v = parse_numeric_value("1.74 × 10^7 1/Ms", "Binding_Kinetics_kon")
        self.assertAlmostEqual(v, 1.74e7, delta=1e3)

    def test_koff_negative_exponent(self):
        v = parse_numeric_value("2.51 × 10^(-4) 1/s", "Binding_Kinetics_koff")
        self.assertAlmostEqual(v, 2.51e-4, delta=1e-6)

    def test_python_scientific_notation(self):
        v = parse_numeric_value("1.74e7", "Binding_Kinetics_kon")
        self.assertAlmostEqual(v, 1.74e7, delta=1e3)

    def test_negative_exponent_e_notation(self):
        v = parse_numeric_value("2.51e-4", "Binding_Kinetics_koff")
        self.assertAlmostEqual(v, 2.51e-4, delta=1e-6)


class TestParseTemperature(unittest.TestCase):
    """Test Tm temperature parsing."""

    def test_tm_with_degree(self):
        v = parse_numeric_value("65.3°C", "Thermal_Stability_Tm")
        self.assertAlmostEqual(v, 65.3, places=1)

    def test_tm_plain_number(self):
        v = parse_numeric_value("72", "Thermal_Stability_Tm")
        self.assertAlmostEqual(v, 72.0, places=1)

    def test_tm_out_of_range(self):
        v = parse_numeric_value("5°C", "Thermal_Stability_Tm")
        self.assertIsNone(v)  # Below 20, rejected


class TestMultiValueDetection(unittest.TestCase):
    """Test that multi-value/ambiguous texts return None."""

    def test_and_separator(self):
        v = parse_numeric_value("6.91 nM and 12.3 nM", "Binding_Kinetics_KD")
        self.assertIsNone(v)

    def test_range(self):
        v = parse_numeric_value("5-10 nM", "Binding_Kinetics_KD")
        self.assertIsNone(v)

    def test_greater_than(self):
        v = parse_numeric_value("> 100 nM", "Binding_Kinetics_KD")
        self.assertIsNone(v)

    def test_plus_minus(self):
        v = parse_numeric_value("6.91 ± 0.5 nM", "Binding_Kinetics_KD")
        self.assertIsNone(v)


class TestTryNumericMatch(unittest.TestCase):
    """Test numeric matching logic."""

    def test_exact_same_unit(self):
        r = try_numeric_match("Binding_Kinetics_KD", "6.91 nM", "6.91 nM")
        self.assertEqual(r["label"], "exact")

    def test_exact_cross_unit(self):
        r = try_numeric_match("Binding_Kinetics_KD", "6.91 nM", "6910 pM")
        self.assertEqual(r["label"], "exact")

    def test_partial_2x(self):
        r = try_numeric_match("Binding_Kinetics_KD", "6.91 nM", "15 nM")
        self.assertEqual(r["label"], "partial")

    def test_wrong_10x(self):
        r = try_numeric_match("Binding_Kinetics_KD", "6.91 nM", "100 nM")
        self.assertEqual(r["label"], "wrong")

    def test_non_numeric_field_returns_none(self):
        r = try_numeric_match("Target_Name", "Spike", "Spike")
        self.assertIsNone(r)

    def test_unparseable_returns_none(self):
        r = try_numeric_match("Binding_Kinetics_KD", "strong binding", "weak binding")
        self.assertIsNone(r)

    def test_both_zero(self):
        r = try_numeric_match("Binding_Kinetics_KD", "0 nM", "0 nM")
        self.assertEqual(r["label"], "exact")


class TestNumericFieldsCoverage(unittest.TestCase):
    """Test that NUMERIC_FIELDS covers all expected fields."""

    def test_all_kinetics_fields(self):
        expected = {"Binding_Kinetics_KD", "Binding_Kinetics_kon",
                    "Binding_Kinetics_koff", "Binding_EC50", "Thermal_Stability_Tm"}
        self.assertEqual(set(NUMERIC_FIELDS.keys()), expected)


if __name__ == "__main__":
    unittest.main()
