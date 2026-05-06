"""VLM-based verification and correction of OCR-extracted antibody sequences.

Takes OCR-extracted sequences + source image path, asks VLM to compare
against the original figure, and returns corrected sequences.

Strategy: "correction mode" — give VLM the OCR text as reference and ask it
to spot and fix character-level errors (insertions, deletions, swaps).
This is more reliable than asking VLM to read sequences from scratch because
the VLM tends to truncate long sequences (~70aa) when reading from zero.
"""

import asyncio
import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert at verifying amino acid sequences from alignment images.
You will receive OCR-extracted sequences and must compare them against the actual image.
Focus on character-level errors: inserted/deleted/swapped/misread characters.
Pay special attention to:
- Adjacent similar letters (H vs HH, VT vs TV, IT vs I)
- Similar-looking letters in the image (I/L, D/E, G/C, R/K)
- Missing or extra characters
Output ONLY valid JSON as specified."""

_CLEAN_RE = re.compile(r"[^A-Z]")


def _clean_seq(s: str) -> str:
    return _CLEAN_RE.sub("", s.upper())


async def verify_sequences_with_vlm(
    vlm_client,
    image_dir: str,
    records: list[dict],
) -> list[dict]:
    """Verify and correct OCR-extracted sequences using VLM.

    Args:
        vlm_client: VLMClient instance
        image_dir: Base directory for resolving relative image paths
        records: List of text_sequence_extractor records with
                 _ocr_source_image and _ocr_raw_sequences fields

    Returns:
        The same records with VH_sequence/VL_sequence corrected where VLM
        found errors. Records without source images are returned unchanged.
    """
    # Group records by source image to minimize VLM calls
    image_groups: dict[str, list[dict]] = {}
    no_image_records = []
    for rec in records:
        src_img = rec.get("_ocr_source_image")
        if src_img:
            image_groups.setdefault(src_img, []).append(rec)
        else:
            no_image_records.append(rec)

    if not image_groups:
        return records

    tasks = []
    for img_file, group_recs in image_groups.items():
        img_path = str(Path(image_dir) / img_file)
        if not Path(img_path).exists():
            logger.warning(f"VLM verify: image not found: {img_path}")
            no_image_records.extend(group_recs)
            continue
        tasks.append(_verify_image_group(vlm_client, img_path, group_recs))

    if tasks:
        await asyncio.gather(*tasks)

    return records  # records are modified in-place


def resolve_sequence_image_record_path(paper_dir: str, record: dict) -> str:
    """Resolve a sequence-image record back to its original source/crop image."""
    base_dir = Path(paper_dir)
    crop_name = str(record.get("_source_crop_image") or "").strip()
    source_image = str(record.get("_source_image") or "").strip()

    if crop_name and source_image:
        source_stem = Path(source_image).stem
        crop_path = base_dir / "images_ocr" / source_stem / "vlm" / "images" / crop_name
        if crop_path.exists():
            return str(crop_path)

    if source_image:
        source_path = base_dir / source_image
        if source_path.exists():
            return str(source_path)

    return ""


async def verify_sequence_image_records_with_vlm(
    vlm_client,
    paper_dir: str,
    records: list[dict],
) -> list[dict]:
    """Verify sequence-image records against the original figure/crop images."""
    tasks = []
    for record in records:
        image_path = resolve_sequence_image_record_path(paper_dir, record)
        if not image_path:
            continue
        tasks.append(_verify_sequence_image_record(vlm_client, image_path, record))

    if tasks:
        await asyncio.gather(*tasks)

    return records


async def _verify_image_group(vlm_client, image_path: str, recs: list[dict]):
    """Verify all sequences from a single source image."""
    # Build per-antibody verification requests
    for rec in recs:
        name = rec.get("mAb", "")
        raw_seqs = rec.get("_ocr_raw_sequences", {})
        if not raw_seqs:
            continue

        for chain_key in ("VH", "VL"):
            raw_key = f"{chain_key}_raw"
            seq_key = f"{chain_key}_sequence"
            ocr_raw = raw_seqs.get(raw_key)
            if not ocr_raw:
                continue

            chain_label = f"{name}{'H' if chain_key == 'VH' else 'L'}"
            chain_desc = "heavy chain (VH)" if chain_key == "VH" else "light chain (VL)"

            try:
                corrected = await _verify_single_sequence(
                    vlm_client, image_path, chain_label, chain_desc, ocr_raw
                )
                if corrected:
                    old_clean = _clean_seq(rec.get(seq_key, ""))
                    new_clean = _clean_seq(corrected)
                    if new_clean != old_clean and len(new_clean) >= 80:
                        logger.info(
                            f"VLM verify: {name} {chain_key} corrected "
                            f"({len(old_clean)}aa → {len(new_clean)}aa)"
                        )
                        rec[seq_key] = new_clean
                        rec.setdefault("_vlm_corrections", {})[chain_key] = {
                            "ocr_len": len(old_clean),
                            "vlm_len": len(new_clean),
                        }
            except Exception as e:
                logger.warning(f"VLM verify failed for {name} {chain_key}: {e}")


async def _verify_sequence_image_record(vlm_client, image_path: str, record: dict):
    name = record.get("mAb", "") or record.get("Antibody_Name", "")
    if not name:
        return

    for chain_key, seq_key in (("VH", "VH_sequence"), ("VL", "VL_sequence")):
        current = _clean_seq(record.get(seq_key, ""))
        if len(current) < 80:
            continue

        chain_desc = "heavy chain (VH)" if chain_key == "VH" else "light chain (VL)"
        try:
            corrected = await _verify_single_sequence(
                vlm_client,
                image_path,
                str(name),
                chain_desc,
                current,
            )
        except Exception as exc:
            logger.warning(f"VLM verify failed for sequence-image {name} {chain_key}: {exc}")
            continue

        corrected_clean = _clean_seq(corrected or "")
        if corrected_clean and len(corrected_clean) >= 80 and corrected_clean != current:
            logger.info(
                "Sequence-image VLM verify: %s %s corrected (%saa -> %saa)",
                name,
                chain_key,
                len(current),
                len(corrected_clean),
            )
            record[seq_key] = corrected_clean
            record.setdefault("_vlm_corrections", {})[chain_key] = {
                "ocr_len": len(current),
                "vlm_len": len(corrected_clean),
                "mode": "sequence_image_verify",
            }


async def _verify_single_sequence(
    vlm_client, image_path: str, label: str, chain_desc: str, ocr_raw: str,
) -> str | None:
    """Ask VLM to verify one sequence against the image and return corrected version."""
    user_text = f"""Compare this OCR-extracted sequence for {label} ({chain_desc}) against the image.

OCR sequence (with alignment gaps as '-'):
{ocr_raw}

Instructions:
1. Find the row labeled '{label}' in the image
2. Read the COMPLETE sequence character by character
3. Compare with the OCR text above and identify any errors
4. Return the FULL corrected sequence (gaps removed, pure amino acids only)

Output ONLY a JSON object:
{{"corrected_sequence": "<full corrected amino acid sequence, no gaps>", "changes": <number of corrections made>}}"""

    resp = await vlm_client.chat_with_image(
        system=SYSTEM_PROMPT,
        user_text=user_text,
        image_path=image_path,
        temperature=0.0,
        max_tokens=4096,
    )

    text = resp.content.strip()
    # Extract JSON from possible markdown code blocks
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]

    # Try to find JSON object in text
    json_match = re.search(r'\{[^{}]*"corrected_sequence"\s*:\s*"[A-Z]+', text)
    if not json_match:
        # Fallback: try to extract just the sequence
        seq_match = re.search(r'"corrected_sequence"\s*:\s*"([A-Z]+)"', text)
        if seq_match:
            return seq_match.group(1)
        logger.warning(f"VLM verify: could not parse response for {label}")
        return None

    # Try parsing from the match position
    json_start = json_match.start()
    # Find the closing brace
    brace_depth = 0
    for i in range(json_start, len(text)):
        if text[i] == '{':
            brace_depth += 1
        elif text[i] == '}':
            brace_depth -= 1
            if brace_depth == 0:
                try:
                    data = json.loads(text[json_start:i+1])
                    seq = data.get("corrected_sequence", "")
                    if seq and len(_clean_seq(seq)) >= 80:
                        changes = data.get("changes", "?")
                        logger.info(f"VLM verify {label}: {changes} correction(s)")
                        return _clean_seq(seq)
                except json.JSONDecodeError:
                    pass
                break

    # Last resort: extract longest AA sequence from response
    seq_match = re.search(r'"corrected_sequence"\s*:\s*"([A-Z]+)', text)
    if seq_match:
        seq = seq_match.group(1)
        if len(seq) >= 80:
            logger.info(f"VLM verify {label}: extracted partial corrected sequence ({len(seq)}aa)")
            return seq

    logger.warning(f"VLM verify: incomplete response for {label}")
    return None
