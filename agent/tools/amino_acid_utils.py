"""Utilities for normalizing amino-acid sequences from OCR / LLM output."""

from __future__ import annotations

import re


STANDARD_AA = set("ACDEFGHIKLMNPQRSTVWY")

THREE_TO_ONE = {
    "ALA": "A",
    "ARG": "R",
    "ASN": "N",
    "ASP": "D",
    "CYS": "C",
    "GLN": "Q",
    "GLU": "E",
    "GLY": "G",
    "HIS": "H",
    "ILE": "I",
    "LEU": "L",
    "LYS": "K",
    "MET": "M",
    "PHE": "F",
    "PRO": "P",
    "SER": "S",
    "THR": "T",
    "TRP": "W",
    "TYR": "Y",
    "VAL": "V",
    "ASX": "B",
    "GLX": "Z",
    "XAA": "X",
    "SEC": "U",
    "PYL": "O",
}

_THREE_LETTER_TOKEN_RE = re.compile(r"[A-Za-z]{3}")
_RUN_DELIMITER_RE = re.compile(r"^[\s,;:/|+\-_.()\[\]{}<>~*]+$")


def replace_three_letter_aa_runs(text: str, min_run_tokens: int = 3) -> str:
    """Replace contiguous three-letter amino-acid token runs with one-letter code.

    Example:
      "Asp Leu Pro Gly" -> "DLPG"

    Only runs of at least ``min_run_tokens`` tokens are converted, which avoids
    corrupting ordinary prose that happens to contain isolated three-letter words
    like "His" or "Met".
    """

    raw = str(text or "")
    matches = list(_THREE_LETTER_TOKEN_RE.finditer(raw))
    if not matches:
        return raw

    runs: list[list[tuple[re.Match[str], str]]] = []
    current: list[tuple[re.Match[str], str]] = []

    for match in matches:
        mapped = THREE_TO_ONE.get(match.group(0).upper())
        if not mapped:
            if len(current) >= min_run_tokens:
                runs.append(current)
            current = []
            continue

        if current:
            gap = raw[current[-1][0].end() : match.start()]
            if _RUN_DELIMITER_RE.fullmatch(gap or ""):
                current.append((match, mapped))
                continue
            if len(current) >= min_run_tokens:
                runs.append(current)
        current = [(match, mapped)]

    if len(current) >= min_run_tokens:
        runs.append(current)

    if not runs:
        return raw

    rebuilt: list[str] = []
    cursor = 0
    for run in runs:
        start = run[0][0].start()
        end = run[-1][0].end()
        rebuilt.append(raw[cursor:start])
        rebuilt.append("".join(code for _, code in run))
        cursor = end
    rebuilt.append(raw[cursor:])
    return "".join(rebuilt)


def normalize_aa_sequence(text: str, min_three_letter_run: int = 3) -> str:
    """Normalize a possible amino-acid sequence into compact one-letter code."""

    converted = replace_three_letter_aa_runs(text, min_run_tokens=min_three_letter_run)
    return re.sub(r"[^A-Za-z]", "", converted or "").upper()
