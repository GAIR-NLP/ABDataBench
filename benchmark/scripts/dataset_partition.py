#!/usr/bin/env python3
"""Helpers for partitioning benchmark datasets into paper/patent subsets."""

from __future__ import annotations

import re
from collections import OrderedDict


PATENT_ID_RE = re.compile(r"^(WO|US|EP|CN|JP|KR|AU|CA|DE|FR|GB|IN)\d", re.IGNORECASE)
SUBSET_ALIASES = {
    "all": "all",
    "paper": "paper",
    "papers": "paper",
    "literature": "paper",
    "patent": "patent",
    "patents": "patent",
}


def infer_category(paper_id: str) -> str:
    text = str(paper_id or "").strip()
    if PATENT_ID_RE.match(text):
        return "patent"
    return "paper"


def normalize_subset(subset: str | None) -> str:
    key = str(subset or "all").strip().lower()
    if key not in SUBSET_ALIASES:
        valid = ", ".join(sorted(set(SUBSET_ALIASES.values())))
        raise ValueError(f"Unsupported subset '{subset}'. Expected one of: {valid}")
    return SUBSET_ALIASES[key]


def annotate_categories(ground_truth: dict) -> OrderedDict[str, OrderedDict[str, object]]:
    annotated: OrderedDict[str, OrderedDict[str, object]] = OrderedDict()
    for paper_id, paper in ground_truth.items():
        paper_entry = OrderedDict(paper)
        paper_entry["category"] = str(paper_entry.get("category") or infer_category(paper_id))
        annotated[paper_id] = paper_entry
    return annotated


def filter_ground_truth(ground_truth: dict, subset: str | None) -> OrderedDict[str, OrderedDict[str, object]]:
    normalized_subset = normalize_subset(subset)
    annotated = annotate_categories(ground_truth)
    if normalized_subset == "all":
        return annotated
    return OrderedDict(
        (paper_id, paper)
        for paper_id, paper in annotated.items()
        if paper.get("category") == normalized_subset
    )


def split_ground_truth(ground_truth: dict) -> dict[str, OrderedDict[str, OrderedDict[str, object]]]:
    annotated = annotate_categories(ground_truth)
    return {
        "all": annotated,
        "paper": filter_ground_truth(annotated, "paper"),
        "patent": filter_ground_truth(annotated, "patent"),
    }
