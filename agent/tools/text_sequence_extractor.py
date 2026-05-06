"""Extract VH/VL sequences from OCR text alignment blocks.

Handles common OCR patterns from sequence alignment figures (e.g. Figure S7A):
  - Labeled inline:  "EV35-2H QVQLVQSGAEVK..."
  - Split labels:    "EV35-6H\n...\nQVQLQQWGAGLL..."

Also detects the source image path from ``<!-- OCR extracted from ... -->``
markers so that downstream VLM verification can reference the original figure.
"""

import re
import logging

logger = logging.getLogger(__name__)

_AA_CHARS = set("ACDEFGHIKLMNPQRSTVWY")
_MIN_VR_LEN = 80
_OCR_MARKER_RE = re.compile(r"<!--\s*OCR extracted from\s+(\S+)\s*-->")


def _clean_seq(s: str) -> str:
    return re.sub(r"[^A-Z]", "", s.upper())


def _is_variable_region(seq: str) -> bool:
    cleaned = _clean_seq(seq)
    if len(cleaned) < _MIN_VR_LEN:
        return False
    non_aa = sum(1 for c in cleaned if c not in _AA_CHARS)
    return non_aa / len(cleaned) < 0.05


def _is_seq_line(line: str) -> bool:
    """Check if a line looks like a raw amino acid sequence (≥80 AA chars)."""
    cleaned = _clean_seq(line)
    if len(cleaned) < _MIN_VR_LEN:
        return False
    alpha_ratio = sum(1 for c in line.strip() if c.isalpha() or c == "-") / max(len(line.strip()), 1)
    return alpha_ratio > 0.8 and _is_variable_region(cleaned)


def extract_text_sequences(markdown_text: str, antibody_names: list[str]) -> list[dict]:
    """Extract VH/VL sequences from OCR text alignment blocks.

    Handles two patterns:
      1. Inline label+sequence: ``mAbNameH QVQLVQ...``
      2. Orphan labels followed by orphan sequences (alignment figure OCR artifact):
         ``mAbNameH``  ← label only
         ``mAbNameH``  ← label only
         ``QVQLVQ...`` ← sequence for first label
         ``QVQLVQ...`` ← sequence for second label

    Returns list of dicts compatible with the merge pipeline (table_records format).
    """
    if not antibody_names or not markdown_text:
        return []

    lines = markdown_text.split("\n")
    records: dict[str, dict] = {}  # name -> {VH_sequence, VL_sequence}

    # -----------------------------------------------------------
    # Detect OCR image block boundaries:
    #   <!-- OCR extracted from <filename>.jpg -->
    #   ... sequence data ...
    #   <!-- end OCR -->
    # Build a mapping: line_index → source_image_filename
    # -----------------------------------------------------------
    line_source_image: dict[int, str] = {}
    current_ocr_image: str | None = None
    for i, line in enumerate(lines):
        m_ocr = _OCR_MARKER_RE.search(line)
        if m_ocr:
            current_ocr_image = m_ocr.group(1)
        elif "<!-- end OCR -->" in line:
            current_ocr_image = None
        if current_ocr_image:
            line_source_image[i] = current_ocr_image

    # Build name patterns (case-insensitive)
    name_patterns = []
    for name in sorted(set(antibody_names), key=lambda n: -len(n)):
        escaped = re.escape(name)
        # Allow optional separator (-/_/space) between name and chain letter
        name_patterns.append((name, re.compile(
            rf"^{escaped}[\s_-]*(H|L)\s*(.*)", re.IGNORECASE
        )))

    # Pass 1: Find all labeled lines and orphan labels
    labeled_entries = []  # (line_idx, name, chain, inline_seq_or_None)
    claimed_lines = set()
    # Track which source image each name's sequences came from
    name_source_images: dict[str, str] = {}

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        for name, pat in name_patterns:
            m = pat.match(stripped)
            if m:
                chain = m.group(1).upper()  # "H" or "L"
                rest = m.group(2).strip()
                inline_seq = _clean_seq(rest) if rest else ""
                if inline_seq and _is_variable_region(inline_seq):
                    labeled_entries.append((i, name, chain, inline_seq))
                else:
                    labeled_entries.append((i, name, chain, None))
                claimed_lines.add(i)
                # Track source image for this label
                if i in line_source_image and name not in name_source_images:
                    name_source_images[name] = line_source_image[i]
                break

    # Pass 2: For orphan labels (no inline sequence), find the next orphan
    # sequence lines in order. This handles the case where OCR puts:
    #   EV35-6H
    #   EV35-7H
    #   QVQLQQWGAG...  (→ EV35-6H)
    #   QVQLVESGGG...  (→ EV35-7H)
    # Group orphan labels by consecutive blocks sharing the same chain type
    orphan_groups = []  # list of (chain, [(line_idx, name), ...])
    current_group = None
    # Also track raw sequences with gaps for VLM verification
    name_raw_seqs: dict[str, dict] = {}  # name -> {"VH_raw": ..., "VL_raw": ...}
    for line_idx, name, chain, seq in labeled_entries:
        if seq is not None:
            # Already has a sequence, store directly
            records.setdefault(name, {})[f"V{chain}_sequence"] = seq
            # Store raw line for VLM verification (inline sequences still have gaps in original line)
            raw_line = lines[line_idx].strip()
            raw_match = re.search(r'[A-Z][A-Z\s\-]{20,}', raw_line)
            if raw_match:
                name_raw_seqs.setdefault(name, {})[f"V{chain}_raw"] = raw_match.group(0).strip()
            current_group = None
            continue
        if current_group is not None and current_group[0] == chain:
            current_group[1].append((line_idx, name))
        else:
            current_group = (chain, [(line_idx, name)])
            orphan_groups.append(current_group)

    # For each orphan group, scan forward from the last label to find
    # matching sequence lines
    for chain, label_list in orphan_groups:
        last_label_idx = label_list[-1][0]
        seq_lines_found = []
        for i in range(last_label_idx + 1, min(last_label_idx + 30, len(lines))):
            if i in claimed_lines:
                continue
            if _is_seq_line(lines[i]):
                seq_lines_found.append((i, _clean_seq(lines[i]), lines[i].strip()))
                claimed_lines.add(i)
                if len(seq_lines_found) == len(label_list):
                    break

        # Pair labels with sequences in order
        for j, (_, name) in enumerate(label_list):
            if j < len(seq_lines_found):
                _, seq, raw_line = seq_lines_found[j]
                records.setdefault(name, {})[f"V{chain}_sequence"] = seq
                name_raw_seqs.setdefault(name, {})[f"V{chain}_raw"] = raw_line

    # Convert to table_records format
    result = []
    for name, seqs in records.items():
        vh = seqs.get("VH_sequence", "")
        vl = seqs.get("VL_sequence", "")
        if not vh and not vl:
            continue
        rec = {
            "mAb": name,
            "_source": "text_sequence_extractor",
            "_source_category": "SEQUENCE_DATA",
            "_discovered_from_text_sequence": True,
        }
        if vh:
            rec["VH_sequence"] = vh
        if vl:
            rec["VL_sequence"] = vl
        # Attach source image path for VLM verification
        src_img = name_source_images.get(name)
        if src_img:
            rec["_ocr_source_image"] = src_img
        # Attach raw OCR sequences (with gaps/spaces) for VLM comparison
        raw = name_raw_seqs.get(name, {})
        if raw:
            rec["_ocr_raw_sequences"] = raw
        result.append(rec)
        logger.info(f"Text sequence extractor: {name} VH={len(vh) if vh else 0}aa VL={len(vl) if vl else 0}aa"
                     + (f" src_img={src_img}" if src_img else ""))

    return result
