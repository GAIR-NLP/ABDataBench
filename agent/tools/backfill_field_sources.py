#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from agents.skeleton_agent import SkeletonAgent
from orchestrator import Orchestrator


FIELD_MAPPINGS = [
    (("CDRH3", "CDRH3_Sequence"), "CDRH3_Sequence"),
    (("KD", "Binding_Kinetics_KD"), "Binding_Kinetics_KD"),
    (("EC50", "Binding_EC50"), "Binding_EC50"),
    (("kon", "Binding_Kinetics_kon"), "Binding_Kinetics_kon"),
    (("koff", "Binding_Kinetics_koff"), "Binding_Kinetics_koff"),
    (("Tm", "Thermal_Stability_Tm"), "Thermal_Stability_Tm"),
    (("VH_sequence", "vh_sequence_aa"), "vh_sequence_aa"),
    (("VL_sequence", "vl_sequence_aa"), "vl_sequence_aa"),
    (("IC50", "Quantitative_Metric"), "Quantitative_Metric"),
    (("In_Vivo_Efficacy",), "In_Vivo_Efficacy"),
    (("Structure",), "Structure"),
]
SEQUENCE_FIELDS = {"CDRH3_Sequence", "vh_sequence_aa", "vl_sequence_aa"}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def group_by_name(antibodies: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for antibody in antibodies:
        name = str(antibody.get("Antibody_Name") or "").strip().lower()
        if name:
            grouped.setdefault(name, []).append(antibody)
    return grouped


def bootstrap_field_sources(final_antibodies: list[dict], skeleton_v1_antibodies: list[dict]) -> None:
    by_name = group_by_name(skeleton_v1_antibodies)
    offsets: dict[str, int] = {}
    for antibody in final_antibodies:
        name = str(antibody.get("Antibody_Name") or "").strip().lower()
        if not name or name not in by_name:
            continue
        bucket = by_name[name]
        idx = offsets.get(name, 0)
        source_ab = bucket[min(idx, len(bucket) - 1)]
        offsets[name] = idx + 1
        field_sources = copy.deepcopy(source_ab.get("field_sources") or {})
        if not field_sources:
            field_sources = SkeletonAgent._build_field_sources_from_hints(source_ab)
        if field_sources:
            existing = antibody.get("field_sources") if isinstance(antibody.get("field_sources"), dict) else {}
            antibody["field_sources"] = {**field_sources, **existing}


def normalize_sequence(value: str) -> str:
    return Orchestrator._normalize_aa_sequence(value)


def matches_field_value(field_name: str, current_value: str, incoming_value: str, derived_cdrh3: str = "") -> bool:
    current = str(current_value or "").strip()
    incoming = str(incoming_value or "").strip()
    if not current or not incoming:
        return False
    if field_name in {"vh_sequence_aa", "vl_sequence_aa"}:
        return normalize_sequence(current) == normalize_sequence(incoming)
    if field_name == "CDRH3_Sequence":
        current_norm = normalize_sequence(current)
        incoming_norm = normalize_sequence(incoming)
        derived_norm = normalize_sequence(derived_cdrh3)
        return current_norm == incoming_norm or (derived_norm and current_norm in {derived_norm, f"C{derived_norm}"})
    return current == incoming


def annotate_antibody_from_records(antibody: dict, records: list[dict]) -> None:
    for record in records:
        vh_raw = Orchestrator._extract_record_value(record, ("VH_sequence", "vh_sequence_aa"))
        vh_norm = normalize_sequence(vh_raw)
        derived_cdrh3 = ""
        if vh_norm:
            derived_cdrh3 = Orchestrator._normalize_aa_sequence(
                Orchestrator._derive_cdrh3_from_vh(vh_norm) or ""
            )
        for src_keys, field_name in FIELD_MAPPINGS:
            incoming_value = Orchestrator._extract_record_value(record, src_keys)
            if not incoming_value:
                continue
            note = ""
            if field_name == "CDRH3_Sequence" and derived_cdrh3:
                incoming_value = derived_cdrh3
                note = "Derived from VH variable-region sequence."
            current_value = str(antibody.get(field_name) or "").strip()
            if not matches_field_value(field_name, current_value, incoming_value, derived_cdrh3):
                continue
            Orchestrator._set_field_source_from_record(antibody, field_name, record, note=note)


def backfill_paper_dir(paper_dir: Path) -> tuple[str, int]:
    final_path = paper_dir / "skeleton_final.json"
    prediction_path = paper_dir / "prediction.json"
    if not final_path.exists():
        return paper_dir.name, 0

    final_payload = read_json(final_path)
    paper_id = next(iter(final_payload.keys()))
    final_antibodies = final_payload.get(paper_id, {}).get("antibodies", [])
    if not final_antibodies:
        return paper_id, 0

    skeleton_v1_path = paper_dir / "skeleton_v1.json"
    if skeleton_v1_path.exists():
        skeleton_v1 = read_json(skeleton_v1_path)
        bootstrap_field_sources(
            final_antibodies,
            skeleton_v1.get(paper_id, {}).get("antibodies", []),
        )

    records_by_name: dict[str, list[dict]] = {}
    for candidate in [paper_dir / "sequence_image_extracted.json", paper_dir / "figure_extracted.json", paper_dir / "image_extracted.json"]:
        if not candidate.exists():
            continue
        payload = read_json(candidate)
        for record in payload.get("table_records", []):
            name = str(record.get("mAb") or record.get("Antibody_Name") or "").strip().lower()
            if name:
                records_by_name.setdefault(name, []).append(record)

    annotated_fields = 0
    for antibody in final_antibodies:
        before = len((antibody.get("field_sources") or {}).keys()) if isinstance(antibody.get("field_sources"), dict) else 0
        name = str(antibody.get("Antibody_Name") or "").strip().lower()
        annotate_antibody_from_records(antibody, records_by_name.get(name, []))
        after = len((antibody.get("field_sources") or {}).keys()) if isinstance(antibody.get("field_sources"), dict) else 0
        annotated_fields += max(after - before, 0)

    write_json(final_path, final_payload)
    write_json(prediction_path, final_payload)
    return paper_id, annotated_fields


def backfill_batch(output_dir: Path) -> None:
    merged_predictions: dict[str, dict] = {}
    summaries = []
    for paper_dir in sorted(path for path in output_dir.iterdir() if path.is_dir()):
        paper_id, annotated_fields = backfill_paper_dir(paper_dir)
        final_path = paper_dir / "skeleton_final.json"
        if final_path.exists():
            payload = read_json(final_path)
            merged_predictions.update(payload)
        summaries.append((paper_id, annotated_fields))

    write_json(output_dir / "predictions.json", merged_predictions)

    for paper_id, annotated_fields in summaries:
        print(f"{paper_id}: field_sources updated for {annotated_fields} field(s)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill field_sources into historical agent outputs.")
    parser.add_argument("output_dir", help="Batch output directory, e.g. runs/dev/agent")
    args = parser.parse_args()
    backfill_batch(Path(args.output_dir).resolve())


if __name__ == "__main__":
    main()
