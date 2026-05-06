#!/usr/bin/env python3
"""Convert a manually annotated workbook into benchmark ground-truth JSON."""

from __future__ import annotations

import argparse
import json
import re
from collections import OrderedDict
from pathlib import Path

import pandas as pd

from dataset_partition import split_ground_truth


FIELD_ORDER = [
    "Antibody_Name",
    "Antibody_Type",
    "Antibody_Isotype",
    "source",
    "Target_Name",
    "Target_Type",
    "Cross_Reactivity",
    "Epitope",
    "Experiment",
    "Binding_Kinetics_KD",
    "Binding_Kinetics_kon",
    "Binding_Kinetics_koff",
    "Binding_EC50",
    "Mechanism_of_Action",
    "Quantitative_Metric",
    "Structure",
    "CDRH3_Sequence",
    "vh_sequence_aa",
    "vl_sequence_aa",
    "Thermal_Stability_Tm",
    "In_Vivo_Half_Life",
    "In_Vivo_Efficacy",
    "Reference_Source",
]


FIELD_ALIASES = {
    "Anitbody_Isotype": "Antibody_Isotype",
    "Mechanism_of_Action_Type": "Mechanism_of_Action",
    "Reference Source": "Reference_Source",
}


NULL_LITERALS = {
    "",
    "nan",
    "none",
    "null",
}


GROUND_TRUTH_DIR = Path(__file__).resolve().parents[1] / "ground_truth"
DEFAULT_OUTPUT = GROUND_TRUTH_DIR / "ground_truth.json"


def clean_value(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text.lower() in NULL_LITERALS:
        return ""
    return text


def normalize_reference_source(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    doi_match = re.search(r"(10\.\d{4,9}/[-._;()/:A-Z0-9]+)", text, re.IGNORECASE)
    doi = doi_match.group(1).rstrip(".,;)") if doi_match else ""
    year_match = re.search(r"\b(19|20)\d{2}\b", text)
    year = year_match.group(0) if year_match else ""
    author_match = re.search(r"\(([A-Za-z][A-Za-z'`\- ]+?)\s+et al\.?\)", text, re.IGNORECASE)
    author = author_match.group(1).strip().split()[-1] if author_match else ""
    if not author:
        author_match = re.search(r"\b([A-Z][A-Za-z'`\-]+)\s+et al\.?\b", text)
        author = author_match.group(1) if author_match else ""
    journal = text
    journal = re.sub(r"\([^)]*\)", " ", journal)
    journal = re.sub(r"doi\s*:?.*$", " ", journal, flags=re.IGNORECASE)
    if year:
        journal = journal.replace(year, " ")
    journal = re.sub(r"\bet al\.?\b", " ", journal, flags=re.IGNORECASE)
    journal = re.sub(r"[^A-Za-z0-9. ]+", " ", journal)
    tokens = [token for token in journal.split() if token]
    lowered = [token.lower() for token in tokens]
    if "et" in lowered:
        et_idx = lowered.index("et")
        tokens = tokens[et_idx + 2 :]
    journal = " ".join(tokens[:4]).strip(" ,.")
    if author and year and journal:
        normalized = f"{author} et al. {journal}, {year}"
        if doi:
            normalized += f". DOI: {doi}"
        return normalized
    return text


def convert_workbook(xlsx_path: Path) -> OrderedDict[str, OrderedDict[str, object]]:
    workbook = pd.ExcelFile(xlsx_path)
    result: OrderedDict[str, OrderedDict[str, object]] = OrderedDict()

    for sheet_name in workbook.sheet_names:
        df = workbook.parse(sheet_name)
        rows_by_field: dict[str, list[str]] = {}

        for _, row in df.iterrows():
            raw_field = clean_value(row.iloc[0])
            if not raw_field:
                continue

            field_name = FIELD_ALIASES.get(raw_field, raw_field)
            if field_name not in FIELD_ORDER:
                continue

            if field_name in rows_by_field:
                # Some sheets contain accidental duplicate row labels.
                # Keep the first occurrence to stay consistent with prior exports.
                continue

            rows_by_field[field_name] = [clean_value(value) for value in row.iloc[1:].tolist()]

        antibody_count = max((len(values) for values in rows_by_field.values()), default=0)
        antibodies: list[OrderedDict[str, str]] = []

        for idx in range(antibody_count):
            antibody = OrderedDict((field, "") for field in FIELD_ORDER)
            for field_name, values in rows_by_field.items():
                if idx < len(values):
                    antibody[field_name] = values[idx]

            antibody["Reference_Source"] = normalize_reference_source(antibody.get("Reference_Source", ""))

            if antibody["Antibody_Name"]:
                antibodies.append(antibody)

        result[sheet_name] = OrderedDict(
            [
                ("paper_id", sheet_name),
                ("title", sheet_name),
                ("antibodies", antibodies),
            ]
        )

    return result


def build_output_paths(output_path: Path) -> dict[str, Path]:
    stem = output_path.stem
    return {
        "all": output_path,
        "paper": output_path.with_name(f"{stem}_paper.json"),
        "patent": output_path.with_name(f"{stem}_patent.json"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert annotated Excel workbook to benchmark JSON.")
    parser.add_argument("--xlsx", type=Path, required=True, help="Input Excel annotation workbook path.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output JSON path.")
    parser.add_argument(
        "--write-subsets",
        action="store_true",
        default=True,
        help="Also write _paper and _patent subset JSON files.",
    )
    parser.add_argument(
        "--no-write-subsets",
        dest="write_subsets",
        action="store_false",
        help="Only write the full JSON file.",
    )
    args = parser.parse_args()

    ground_truth = convert_workbook(args.xlsx)
    split_outputs = split_ground_truth(ground_truth)
    output_paths = build_output_paths(args.output)

    args.output.parent.mkdir(parents=True, exist_ok=True)

    with output_paths["all"].open("w", encoding="utf-8") as handle:
        json.dump(split_outputs["all"], handle, ensure_ascii=False, indent=2)

    if args.write_subsets:
        for subset in ("paper", "patent"):
            with output_paths[subset].open("w", encoding="utf-8") as handle:
                json.dump(split_outputs[subset], handle, ensure_ascii=False, indent=2)

    for subset, dataset in split_outputs.items():
        if subset != "all" and not args.write_subsets:
            continue
        paper_count = len(dataset)
        antibody_count = sum(len(paper["antibodies"]) for paper in dataset.values())
        print(f"Saved {subset:>6}: {paper_count:>2} items / {antibody_count:>3} antibodies -> {output_paths[subset]}")


if __name__ == "__main__":
    main()
