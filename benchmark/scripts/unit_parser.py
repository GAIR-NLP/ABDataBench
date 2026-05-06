#!/usr/bin/env python3
"""
Numeric value and unit parser.

Supported field types:
- KD/EC50: pM, nM, and uM normalization
- kon: scientific notation, for example 1.74 x 10^7 1/Ms
- koff: scientific notation, for example 2.51 x 10^(-4) 1/s
- Tm: temperature values in Celsius
- generic numeric text

Ambiguous, ranged, or multi-value text returns None so the LLM judge can decide.
"""

import re
import math
from typing import Optional


# Unit conversion to the benchmark base unit, nM, for KD/EC50 fields.
_CONC_UNIT_TO_NM = {
    "pm": 0.001,
    "pM": 0.001,
    "nm": 1.0,
    "nM": 1.0,
    "μm": 1000.0,
    "µm": 1000.0,
    "uM": 1000.0,
    "μM": 1000.0,
    "µM": 1000.0,
    "mm": 1e6,
    "mM": 1e6,
    "m": 1e9,
    "M": 1e9,
}

# Field name to parser type.
NUMERIC_FIELDS = {
    "Binding_Kinetics_KD": "concentration",
    "Binding_EC50": "concentration",
    "Binding_Kinetics_kon": "scientific",
    "Binding_Kinetics_koff": "scientific",
    "Thermal_Stability_Tm": "temperature",
}

# Multi-value or ranged markers. If present, skip deterministic parsing.
_MULTI_VALUE_PATTERNS = [
    r'\b(and|or|to|~|–|—|respectively)\b',
    r',\s*\d',       # comma-separated numeric values
    r'[;；]',        # semicolon-separated values
    r'>\s*\d',       # greater-than constraint
    r'<\s*\d',       # less-than constraint
    r'±',            # value with error margin
    r'\brange\b',
]


def _has_multi_values(text: str) -> bool:
    """Return whether the text contains multiple values or ambiguous wording."""
    for pat in _MULTI_VALUE_PATTERNS:
        if re.search(pat, text, re.IGNORECASE):
            return True
    # Remove scientific-notation exponents and common unit denominators before counting numbers.
    cleaned = re.sub(r'[×xX\*]\s*10\s*[\^]?\s*[\(\[]?\s*-?\d+\s*[\)\]]?', '', text)
    cleaned = re.sub(r'\d+\.?\d*[eE][+-]?\d+', 'NUM', cleaned)  # Python scientific notation
    cleaned = re.sub(r'\b1/[A-Za-z]+', '', cleaned)  # units such as "1/s" and "1/Ms"
    nums = re.findall(r'\b\d+\.?\d*\b', cleaned)
    if len(nums) > 1:
        return True
    return False


def _parse_scientific_notation(text: str) -> Optional[float]:
    """Parse scientific notation such as 1.74 x 10^7, 2.51e-4, or 1.74E7."""
    text = text.strip()

    # Standard Python scientific notation: 1.74e7, 2.51e-4.
    m = re.match(r'^[=≈~:]*\s*(-?\d+\.?\d*)\s*[eE]\s*([+-]?\d+)', text)
    if m:
        return float(m.group(1)) * (10 ** float(m.group(2)))

    # Text forms: 1.74 x 10^7, 1.74 x 10^(-4), 1.74x10^7.
    m = re.search(
        r'(-?\d+\.?\d*)\s*[×xX\*]\s*10\s*[\^]?\s*[\(\[]?\s*(-?\d+)\s*[\)\]]?',
        text
    )
    if m:
        return float(m.group(1)) * (10 ** float(m.group(2)))

    # Unicode superscripts, such as 10^-4.
    superscript_map = str.maketrans('⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺', '0123456789-+')
    m = re.search(r'(-?\d+\.?\d*)\s*[×xX\*]\s*10([⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺]+)', text)
    if m:
        exp_str = m.group(2).translate(superscript_map)
        return float(m.group(1)) * (10 ** float(exp_str))

    return None


def _parse_concentration(text: str) -> Optional[float]:
    """
    Parse concentration values and normalize them to nM.

    Supports examples such as "6.91 nM", "KD = 0.003 nM", "45 pM",
    "1.2 uM", and "1.74 x 10^(-9) M".
    """
    text = text.strip()

    # Try scientific notation with units first.
    sci = _parse_scientific_notation(text)
    if sci is not None:
        # Check the unit.
        unit_match = re.search(r'(pM|nM|[μµu]M|mM|M)\b', text)
        if unit_match:
            unit = unit_match.group(1)
            factor = _CONC_UNIT_TO_NM.get(unit, 1.0)
            return sci * factor
        # No explicit parsed unit, but the string ends in M, so treat it as molar.
        if re.search(r'\d\s*M\b', text) or re.search(r'\)\s*M\b', text):
            return sci * 1e9
        # Unit is unknown. Return the raw numeric value.
        return sci

    # Plain numeric value with unit: "6.91 nM", "45pM".
    m = re.search(
        r'[=≈~:]*\s*(\d+\.?\d*)\s*(pM|nM|[μµu]M|mM|M)\b',
        text
    )
    if m:
        val = float(m.group(1))
        unit = m.group(2)
        factor = _CONC_UNIT_TO_NM.get(unit, 1.0)
        return val * factor

    # Bare number. Assume nM for benchmark compatibility.
    m = re.match(r'^[=≈~:KDkdECec50]*\s*(\d+\.?\d*)\s*$', text)
    if m:
        return float(m.group(1))

    return None


def _parse_temperature(text: str) -> Optional[float]:
    """Parse temperature values such as "65.3 C", "Tm = 65.3", or "65.3 degC"."""
    text = text.strip()
    m = re.search(r'[=≈~:TtMm]*\s*(\d+\.?\d*)\s*[°℃]?\s*[Cc]?', text)
    if m:
        val = float(m.group(1))
        # Broadly plausible protein Tm range.
        if 20 <= val <= 120:
            return val
    return None


def parse_numeric_value(text: str, field_name: str) -> Optional[float]:
    """
    Parse numeric text with optional units.

    Args:
        text: raw text, such as "KD = 6.91 nM"
        field_name: benchmark field name used to select a parsing strategy

    Returns:
        Parsed numeric value in the normalized unit, or None if the text is
        ambiguous, multi-valued, or unsupported.
    """
    if not text or not text.strip():
        return None

    text = text.strip()

    # Ambiguous or multi-value text is left to the LLM judge.
    if _has_multi_values(text):
        return None

    parse_type = NUMERIC_FIELDS.get(field_name, "generic")

    if parse_type == "concentration":
        return _parse_concentration(text)
    elif parse_type == "scientific":
        return _parse_scientific_notation(text)
    elif parse_type == "temperature":
        return _parse_temperature(text)

    # Generic fallback: extract the first number.
    m = re.search(r'(-?\d+\.?\d*)', text)
    if m:
        return float(m.group(1))
    return None


def try_numeric_match(field_name: str, gt_value: str, pred_value: str) -> Optional[dict]:
    """
    Try deterministic numeric matching.

    Returns:
        A label/score/reason dict, or None when parsing fails and the caller
        should fall back to the LLM judge.

    Criteria:
        <=10% difference: exact (1.0)
        <=3x difference: partial (0.5)
        >3x difference: wrong (0.0)
    """
    if field_name not in NUMERIC_FIELDS:
        return None

    gt_num = parse_numeric_value(gt_value, field_name)
    pred_num = parse_numeric_value(pred_value, field_name)

    if gt_num is None or pred_num is None:
        return None

    # Avoid division by zero.
    if gt_num == 0 and pred_num == 0:
        return {"label": "exact", "score": 1.0, "reason": "Numeric match: both values are zero"}

    if gt_num == 0:
        return {"label": "wrong", "score": 0.0, "reason": f"Numeric mismatch: GT=0, Pred={pred_num}"}

    # Compute ratio and relative difference.
    ratio = pred_num / gt_num if gt_num != 0 else float('inf')
    fold_diff = max(ratio, 1.0 / ratio) if ratio > 0 else float('inf')
    pct_diff = abs(pred_num - gt_num) / abs(gt_num)

    if pct_diff <= 0.10:
        return {
            "label": "exact", "score": 1.0,
            "reason": f"Numeric match: GT={gt_num:.4g}, Pred={pred_num:.4g}, difference {pct_diff:.1%}"
        }
    elif fold_diff <= 3.0:
        return {
            "label": "partial", "score": 0.5,
            "reason": f"Numeric partial match: GT={gt_num:.4g}, Pred={pred_num:.4g}, {fold_diff:.1f}x difference"
        }
    else:
        return {
            "label": "wrong", "score": 0.0,
            "reason": f"Numeric mismatch: GT={gt_num:.4g}, Pred={pred_num:.4g}, {fold_diff:.1f}x difference"
        }
