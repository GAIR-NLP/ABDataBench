#!/usr/bin/env python3
"""
Benchmark evaluation engine for antibody literature extraction v3.

Key features:
1. 22 scoring fields aligned with the JSON schema
2. weighted field scoring: core 2.0, standard 1.0, auxiliary 0.5
3. order-independent antibody matching
4. continuous penalty formula: max(0, 1.0 - 0.01*NFP - 0.05*NFN)
5. numeric field pre-checks before falling back to the LLM judge
6. Final = (Σ Record_Score_i / NGS) × 100 × Penalty
"""

import re
import os
import sys
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from unit_parser import NUMERIC_FIELDS, try_numeric_match


# ==================== Data Structures ====================

@dataclass
class FieldScore:
    field_name: str
    gt_value: str
    pred_value: str
    score: float          # 0.0 / 0.5 / 1.0
    weight: float         # field weight
    weighted_score: float # score * weight
    label: str            # exact / partial / wrong / miss / skip
    reason: str = ""


@dataclass
class AntibodyScore:
    antibody_name: str
    matched: bool = True
    field_scores: List[FieldScore] = field(default_factory=list)
    total_fields: int = 0       # scored fields, excluding skip
    score_sum: float = 0.0      # raw score sum
    weight_sum: float = 0.0     # weight sum for scored fields
    weighted_score_sum: float = 0.0  # weighted score sum
    accuracy: float = 0.0       # weighted average on a 0-100 scale


@dataclass
class PaperScore:
    paper_id: str
    antibody_scores: List[AntibodyScore] = field(default_factory=list)
    gt_antibody_count: int = 0     # NGS
    pred_antibody_count: int = 0   # NWF
    matched_count: int = 0         # NTP
    false_negative_count: int = 0  # NFN = NGS - NTP
    false_positive_count: int = 0  # NFP = NWF - NTP
    unmatched_gt: List[str] = field(default_factory=list)
    extra_pred: List[str] = field(default_factory=list)
    # Scoring.
    raw_accuracy: float = 0.0     # weighted average on a 0-100 scale
    penalty_coeff: float = 1.0    # continuous penalty coefficient
    accuracy: float = 0.0         # final score


@dataclass
class BenchmarkResult:
    paper_scores: List[PaperScore] = field(default_factory=list)
    total_fields: int = 0
    total_score: float = 0.0
    total_weight: float = 0.0
    total_weighted_score: float = 0.0
    accuracy: float = 0.0         # 0-100 scale
    metadata: Dict[str, object] = field(default_factory=dict)


# ==================== Field Weights (22 Fields) ====================

# Core weight (2.0): sequences and KD.
CORE_FIELDS = {
    "CDRH3_Sequence", "vh_sequence_aa", "vl_sequence_aa", "Binding_Kinetics_KD",
}
# Standard weight (1.0): target, epitope, type, mechanism, experiment, kinetics, structure.
STANDARD_FIELDS = {
    "Target_Name", "Epitope", "Antibody_Type",
    "Mechanism_of_Action", "Experiment",
    "Binding_Kinetics_kon", "Binding_Kinetics_koff", "Binding_EC50", "Structure",
}
# Auxiliary weight (0.5): source, reference, metadata, cross-reactivity, stability, in-vivo fields.
AUXILIARY_FIELDS = {
    "source", "Reference_Source", "Target_Type", "Antibody_Isotype",
    "Cross_Reactivity", "Quantitative_Metric",
    "In_Vivo_Half_Life", "In_Vivo_Efficacy", "Thermal_Stability_Tm",
}

EVAL_FIELDS = [
    # Core (2.0)
    "CDRH3_Sequence", "vh_sequence_aa", "vl_sequence_aa", "Binding_Kinetics_KD",
    # Standard (1.0)
    "Target_Name", "Epitope", "Antibody_Type", "Mechanism_of_Action", "Experiment",
    "Binding_Kinetics_kon", "Binding_Kinetics_koff", "Binding_EC50", "Structure",
    # Auxiliary (0.5)
    "source", "Reference_Source", "Target_Type", "Antibody_Isotype",
    "Cross_Reactivity", "Quantitative_Metric",
    "In_Vivo_Half_Life", "In_Vivo_Efficacy", "Thermal_Stability_Tm",
]

def get_field_weight(field_name: str) -> float:
    if field_name in CORE_FIELDS:
        return 2.0
    elif field_name in STANDARD_FIELDS:
        return 1.0
    elif field_name in AUXILIARY_FIELDS:
        return 0.5
    return 1.0


# ==================== Empty-Value Handling ====================

EMPTY_MARKERS = {
    "", "n/a", "n.a.", "n.d.", "nd", "not reported", "not specified",
    "未报道", "未提供", "未提及", "none", "null", "无", "-", "—",
}


def _stringify_value(value) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        ordered_keys = (
            "value", "pointer", "action", "quote",
            "metric_name", "metric_value", "germline", "confidence",
        )
        parts = [str(value.get(key, "")).strip() for key in ordered_keys if str(value.get(key, "")).strip()]
        if parts:
            return " | ".join(parts)
        return ""
    if isinstance(value, list):
        parts = [_stringify_value(item) for item in value]
        return "; ".join(part for part in parts if part)
    return str(value).strip()


def normalize(value) -> str:
    return _stringify_value(value).lower()


def has_model_output(value) -> bool:
    return bool(_stringify_value(value))


def paper_has_model_output(pred_paper: Optional[dict]) -> bool:
    """Whether a paper has any substantive model output.

    Papers with no prediction entry, empty antibody lists, or antibodies whose
    fields are all empty are excluded from benchmark averaging/reporting.
    """
    antibodies = list((pred_paper or {}).get("antibodies") or [])
    if not antibodies:
        return False
    for antibody in antibodies:
        if not isinstance(antibody, dict):
            continue
        for field_name, value in antibody.items():
            if field_name == "field_sources":
                continue
            if has_model_output(value):
                return True
    return False


def is_empty(value) -> bool:
    text = _stringify_value(value)
    n = text.lower()
    if n in EMPTY_MARKERS or not text:
        return True
    # Strip parenthetical detail before checking markers, e.g. "N/A (Light chain-devoid)" -> "n/a".
    n_no_paren = re.sub(r'\s*[\(（].*?[\)）]\s*', '', n).strip()
    if n_no_paren in EMPTY_MARKERS:
        return True
    if re.match(
        r'^(未提供|未报道|未提及|不适用|not\s+(reported|specified|provided|mentioned|applicable)'
        r'|n\.?/?[ad]\.?)$', n_no_paren
    ):
        return True
    return False


def _normalize_match_text(value) -> str:
    return re.sub(r"[^a-z0-9]+", "", normalize(value))


def _tokenize_list_field(value) -> set[str]:
    text = _stringify_value(value)
    if not text:
        return set()
    parts = re.split(r"[,;/，；、\n]+", text)
    normalized = set()
    for part in parts:
        token = _normalize_match_text(part)
        if token:
            normalized.add(token)
    return normalized


def _field_similarity(field_name: str, gt_value, pred_value) -> Optional[float]:
    if is_empty(gt_value) or is_empty(pred_value):
        return None

    gt_norm = _normalize_match_text(gt_value)
    pred_norm = _normalize_match_text(pred_value)
    if not gt_norm or not pred_norm:
        return None
    if gt_norm == pred_norm:
        return 1.0
    if gt_norm in pred_norm or pred_norm in gt_norm:
        return 0.9

    if field_name == "Experiment":
        gt_tokens = _tokenize_list_field(gt_value)
        pred_tokens = _tokenize_list_field(pred_value)
        if not gt_tokens or not pred_tokens:
            return None
        overlap = len(gt_tokens & pred_tokens)
        union = len(gt_tokens | pred_tokens)
        return overlap / union if union else None

    return SequenceMatcher(None, gt_norm, pred_norm).ratio()


def antibody_pair_similarity(gt_ab: dict, pred_ab: dict) -> float:
    name_sim = antibody_name_similarity(gt_ab.get("Antibody_Name", ""), pred_ab.get("Antibody_Name", ""))
    exact_name_match = _name_normalize(gt_ab.get("Antibody_Name", "")) == _name_normalize(
        pred_ab.get("Antibody_Name", "")
    )
    context_weights = {
        "Target_Name": 0.45,
        "Antibody_Type": 0.25,
        "Experiment": 0.15,
        "Structure": 0.10,
        "Reference_Source": 0.05,
    }
    context_score = 0.0
    context_weight_sum = 0.0
    for field_name, weight in context_weights.items():
        sim = _field_similarity(field_name, gt_ab.get(field_name, ""), pred_ab.get(field_name, ""))
        if sim is None:
            continue
        context_score += sim * weight
        context_weight_sum += weight

    if context_weight_sum == 0:
        return name_sim

    context_avg = context_score / context_weight_sum
    if exact_name_match:
        return min(1.0, 0.98 + 0.02 * context_avg)
    if name_sim >= 0.95:
        return min(1.0, 0.8 * name_sim + 0.2 * context_avg)
    return 0.85 * name_sim + 0.15 * context_avg


# ==================== Antibody Matching (Order Independent) ====================

def _name_normalize(name: str) -> str:
    """Normalize antibody names by removing spaces, dashes, and underscores."""
    return normalize(name).replace(" ", "").replace("-", "").replace("–", "").replace("_", "")


def _has_compact_variant_suffix(gt_name: str, pred_name: str) -> bool:
    """Detect compact derivative names like L9K vs L9 and prefer exact-name matches."""
    raw_gt = str(gt_name or "").strip()
    raw_pred = str(pred_name or "").strip()
    if not raw_gt or not raw_pred:
        return False
    if any(re.search(r"[\s\-_–/]", value) for value in (raw_gt, raw_pred)):
        return False

    gt_norm = _name_normalize(raw_gt)
    pred_norm = _name_normalize(raw_pred)
    if not gt_norm or not pred_norm or gt_norm == pred_norm:
        return False

    shorter, longer = sorted((gt_norm, pred_norm), key=len)
    if not longer.startswith(shorter):
        return False

    suffix = longer[len(shorter):]
    return 0 < len(suffix) <= 2 and suffix.isalnum()


def antibody_name_similarity(gt_name: str, pred_name: str) -> float:
    """Compute antibody name similarity in [0, 1]."""
    g = _name_normalize(gt_name)
    p = _name_normalize(pred_name)
    if not g or not p:
        return 0.0
    if g == p:
        return 1.0
    if _has_compact_variant_suffix(gt_name, pred_name):
        return 0.85
    if g in p or p in g:
        return 0.95
    return SequenceMatcher(None, g, p).ratio()


def match_antibodies_optimal(gt_antibodies: list, pred_antibodies: list):
    """
    Order-independent antibody matching using Hungarian assignment when available.

    Returns: (matched_pairs, unmatched_gt, extra_pred)
    matched_pairs: [(gt_ab, pred_ab), ...]
    """
    n_gt = len(gt_antibodies)
    n_pred = len(pred_antibodies)

    if n_gt == 0:
        return [], [], list(pred_antibodies)
    if n_pred == 0:
        return [], list(gt_antibodies), []

    # Build the similarity matrix.
    sim_matrix = []
    for i, gt_ab in enumerate(gt_antibodies):
        row = []
        gt_name = gt_ab.get("Antibody_Name", "")
        for j, pred_ab in enumerate(pred_antibodies):
            pred_name = pred_ab.get("Antibody_Name", "")
            sim = antibody_pair_similarity(gt_ab, pred_ab)
            row.append(sim)
        sim_matrix.append(row)

    # Use scipy's Hungarian algorithm when available.
    try:
        from scipy.optimize import linear_sum_assignment
        import numpy as np
        # Convert to a cost matrix: maximize similarity by minimizing 1 - similarity.
        max_dim = max(n_gt, n_pred)
        cost = np.zeros((max_dim, max_dim))
        for i in range(n_gt):
            for j in range(n_pred):
                cost[i][j] = 1.0 - sim_matrix[i][j]
        row_ind, col_ind = linear_sum_assignment(cost)

        matched_pairs = []
        used_gt = set()
        used_pred = set()
        for r, c in zip(row_ind, col_ind):
            if r < n_gt and c < n_pred and sim_matrix[r][c] >= 0.5:
                matched_pairs.append((gt_antibodies[r], pred_antibodies[c]))
                used_gt.add(r)
                used_pred.add(c)

        unmatched_gt = [gt_antibodies[i] for i in range(n_gt) if i not in used_gt]
        extra_pred = [pred_antibodies[j] for j in range(n_pred) if j not in used_pred]
        return matched_pairs, unmatched_gt, extra_pred

    except ImportError:
        # Fall back to greedy matching.
        return _greedy_match(gt_antibodies, pred_antibodies, sim_matrix)


def _greedy_match(gt_antibodies, pred_antibodies, sim_matrix):
    """Greedy fallback when scipy is unavailable."""
    n_gt = len(gt_antibodies)
    n_pred = len(pred_antibodies)

    # Collect and sort all viable (similarity, gt_idx, pred_idx) candidates.
    candidates = []
    for i in range(n_gt):
        for j in range(n_pred):
            if sim_matrix[i][j] >= 0.5:
                candidates.append((sim_matrix[i][j], i, j))
    candidates.sort(key=lambda x: -x[0])

    matched_pairs = []
    used_gt = set()
    used_pred = set()
    for sim, i, j in candidates:
        if i not in used_gt and j not in used_pred:
            matched_pairs.append((gt_antibodies[i], pred_antibodies[j]))
            used_gt.add(i)
            used_pred.add(j)

    unmatched_gt = [gt_antibodies[i] for i in range(n_gt) if i not in used_gt]
    extra_pred = [pred_antibodies[j] for j in range(n_pred) if j not in used_pred]
    return matched_pairs, unmatched_gt, extra_pred


# ==================== Continuous Penalty Formula ====================

def compute_penalty(ngs: int, ntp: int, nfn: int, nfp: int) -> float:
    """
    Penalty formula v3.1.

    penalty = max(0, 1.0 - 0.01*floor(NFP/5) - 0.05*NFN)

    Special cases:
    - NGS=0, NWF=0 -> 1.0 (correctly recognized a paper with no records)
    - NGS=0, NWF>0 -> 0.0 (hallucinated records)
    - NTP=0        -> 0.0 (no matched records)
    """
    nwf = ntp + nfp
    if ngs == 0:
        return 1.0 if nwf == 0 else 0.0
    if ntp == 0:
        return 0.0
    fp_penalty_steps = nfp // 5
    return max(0.0, 1.0 - 0.01 * fp_penalty_steps - 0.05 * nfn)


# ==================== Core Evaluation ====================

def evaluate_antibody(gt_ab: dict, pred_ab: dict, llm_judge,
                      field_pbar=None) -> AntibodyScore:
    """Evaluate one matched antibody using numeric pre-checks before the LLM judge."""
    ab_name = gt_ab.get("Antibody_Name", "unknown")
    result = AntibodyScore(antibody_name=ab_name, matched=True)

    for field_name in EVAL_FIELDS:
        gt_val = _stringify_value(gt_ab.get(field_name, ""))
        pred_val = _stringify_value(pred_ab.get(field_name, ""))
        weight = get_field_weight(field_name)

        gt_empty = is_empty(gt_val)
        pred_empty = is_empty(pred_val)
        pred_has_output = has_model_output(pred_val)

        # Both sides empty: exact because the model correctly left the field blank.
        if gt_empty and pred_empty:
            weighted_s = 1.0 * weight
            result.field_scores.append(FieldScore(
                field_name, gt_val, pred_val, 1.0, weight, weighted_s, "exact",
                "Both values are empty; the model correctly recognized no data"
            ))
            result.total_fields += 1
            result.score_sum += 1.0
            result.weight_sum += weight
            result.weighted_score_sum += weighted_s
            if field_pbar:
                field_pbar.update(1)
            continue

        # Empty GT with model output: skip, neither reward nor penalty.
        if gt_empty and not pred_empty:
            result.field_scores.append(FieldScore(
                field_name, gt_val, pred_val, 0.0, weight, 0.0, "skip",
                "Ground truth is empty; skipped for scoring"
            ))
            if field_pbar:
                field_pbar.update(1)
            continue

        # Non-empty GT with empty model output: miss with weight counted.
        if not gt_empty and not pred_has_output:
            result.field_scores.append(FieldScore(
                field_name, gt_val, pred_val, 0.0, weight, 0.0, "miss",
                "Model did not output a value"
            ))
            result.total_fields += 1
            result.weight_sum += weight
            if field_pbar:
                field_pbar.update(1)
            continue

        # Both sides have values: try numeric pre-check before falling back to the LLM.
        numeric_result = None
        if field_name in NUMERIC_FIELDS:
            numeric_result = try_numeric_match(field_name, gt_val, pred_val)

        if numeric_result is not None:
            # Numeric match succeeded; skip the LLM judge.
            score = numeric_result["score"]
            weighted_s = score * weight
            fs = FieldScore(
                field_name, gt_val, pred_val,
                score, weight, weighted_s,
                numeric_result["label"], numeric_result["reason"]
            )
            result.field_scores.append(fs)
            result.total_fields += 1
            result.score_sum += score
            result.weight_sum += weight
            result.weighted_score_sum += weighted_s
            if field_pbar:
                icon = {"exact": "✅", "partial": "⚠️", "wrong": "❌"}.get(fs.label, "?")
                field_pbar.set_postfix_str(f"{icon} {ab_name}/{field_name}={score:.1f} [NUM]")
                field_pbar.update(1)
            continue

        # LLM Judge
        if field_pbar:
            w_tag = {2.0: "🔴", 1.0: "🟡", 0.5: "🟢"}.get(weight, "")
            field_pbar.set_postfix_str(f"{w_tag} {ab_name}/{field_name} → LLM")
        llm_result = llm_judge.judge_field(field_name, gt_val, pred_val)
        score = llm_result["score"]
        weighted_s = score * weight

        fs = FieldScore(
            field_name, gt_val, pred_val,
            score, weight, weighted_s,
            llm_result["label"], llm_result["reason"]
        )
        result.field_scores.append(fs)
        result.total_fields += 1
        result.score_sum += score
        result.weight_sum += weight
        result.weighted_score_sum += weighted_s

        if field_pbar:
            icon = {"exact": "✅", "partial": "⚠️", "wrong": "❌"}.get(fs.label, "?")
            field_pbar.set_postfix_str(f"{icon} {ab_name}/{field_name}={score:.1f}")
            field_pbar.update(1)

    # Weighted average on a 0-100 scale.
    if result.weight_sum > 0:
        result.accuracy = (result.weighted_score_sum / result.weight_sum) * 100

    return result


def evaluate_unmatched(gt_ab: dict) -> AntibodyScore:
    """Evaluate an unmatched ground-truth antibody as missing for all non-empty fields."""
    ab_name = gt_ab.get("Antibody_Name", "unknown")
    result = AntibodyScore(antibody_name=ab_name, matched=False)

    for field_name in EVAL_FIELDS:
        gt_val = _stringify_value(gt_ab.get(field_name, ""))
        weight = get_field_weight(field_name)
        if is_empty(gt_val):
            result.field_scores.append(FieldScore(
                field_name, gt_val, "", 0.0, weight, 0.0, "skip",
                "Ground truth is empty"
            ))
        else:
            result.field_scores.append(FieldScore(
                field_name, gt_val, "", 0.0, weight, 0.0, "miss",
                "Ground-truth antibody was not identified by the model"
            ))
            result.total_fields += 1
            result.weight_sum += weight

    result.accuracy = 0.0
    return result


def evaluate_paper(paper_id: str, gt_abs: list, pred_abs: list, llm_judge,
                   field_pbar=None) -> PaperScore:
    """
    Evaluate one paper.

    Scoring formula:
    Record_Score_i = weighted_score_sum_i / weight_sum_i for each matched antibody
    Unmatched ground-truth antibodies contribute Record_Score = 0
    Final = (Σ Record_Score_i / NGS) × 100 × Penalty_Multiplier
    """
    result = PaperScore(paper_id=paper_id)
    result.gt_antibody_count = len(gt_abs)
    result.pred_antibody_count = len(pred_abs)

    # Order-independent optimal matching.
    matched, unmatched_gt, extra_pred = match_antibodies_optimal(gt_abs, pred_abs)

    result.matched_count = len(matched)                    # NTP
    result.false_negative_count = len(unmatched_gt)        # NFN
    result.false_positive_count = len(extra_pred)          # NFP
    result.unmatched_gt = [ab.get("Antibody_Name", "?") for ab in unmatched_gt]
    result.extra_pred = [ab.get("Antibody_Name", "?") for ab in extra_pred]

    # Score matched antibody pairs.
    for gt_ab, pred_ab in matched:
        ab_score = evaluate_antibody(gt_ab, pred_ab, llm_judge, field_pbar)
        result.antibody_scores.append(ab_score)

    # Add unmatched ground-truth antibodies.
    for gt_ab in unmatched_gt:
        ab_score = evaluate_unmatched(gt_ab)
        result.antibody_scores.append(ab_score)
        # Unmatched antibodies still consume field slots in the progress bar.
        if field_pbar:
            field_pbar.update(len(EVAL_FIELDS))

    # Paper-level raw score: (sum Record_Score_i / NGS) * 100.
    ngs = result.gt_antibody_count
    if ngs > 0:
        # Each antibody record_score = weighted_score_sum / weight_sum (0 to 1).
        record_score_sum = 0.0
        for ab in result.antibody_scores:
            if ab.weight_sum > 0:
                record_score_sum += ab.weighted_score_sum / ab.weight_sum
            # else: 0 contribution (all skip)
        result.raw_accuracy = (record_score_sum / ngs) * 100
    else:
        result.raw_accuracy = 0.0

    # Compute the continuous penalty coefficient.
    ntp = result.matched_count
    nfn = result.false_negative_count
    nfp = result.false_positive_count
    result.penalty_coeff = compute_penalty(ngs, ntp, nfn, nfp)

    # Final score = raw_accuracy * penalty_coeff.
    result.accuracy = result.raw_accuracy * result.penalty_coeff

    return result


def _count_total_fields(ground_truth: dict, predictions: dict) -> int:
    """Precompute total evaluated field slots for the progress bar."""
    total = 0
    for paper_id, gt_paper in ground_truth.items():
        gt_abs = gt_paper.get("antibodies", [])
        pred_abs = predictions.get(paper_id, {}).get("antibodies", [])
        matched, unmatched_gt, _ = match_antibodies_optimal(gt_abs, pred_abs)
        # Each matched pair contributes one slot per eval field.
        total += len(matched) * len(EVAL_FIELDS)
        # Each unmatched GT antibody contributes one slot per eval field.
        total += len(unmatched_gt) * len(EVAL_FIELDS)
    return total


def evaluate_benchmark(ground_truth: dict, predictions: dict, llm_judge,
                       paper_concurrency: int = 5) -> BenchmarkResult:
    """Evaluate the benchmark with paper-level concurrency."""
    result = BenchmarkResult()
    paper_items_all = list(ground_truth.items())
    skipped_no_output_papers = [
        paper_id for paper_id, _ in paper_items_all
        if not paper_has_model_output(predictions.get(paper_id))
    ]
    paper_items = [
        (paper_id, gt_paper) for paper_id, gt_paper in paper_items_all
        if paper_id not in skipped_no_output_papers
    ]
    filtered_ground_truth = {paper_id: gt_paper for paper_id, gt_paper in paper_items}

    n_papers = len(filtered_ground_truth)
    total_fields = _count_total_fields(filtered_ground_truth, predictions)
    result.metadata["total_ground_truth_papers"] = len(ground_truth)
    result.metadata["evaluated_papers"] = n_papers
    result.metadata["skipped_no_output_papers"] = skipped_no_output_papers

    # Global field progress bar, updated through a thread-safe wrapper.
    field_pbar = tqdm(
        total=total_fields,
        desc="Field scoring",
        unit="field",
        bar_format="{l_bar}{bar:30}{r_bar}",
        colour="cyan",
        file=sys.stderr,
    )
    pbar_lock = threading.Lock()

    # Paper-level progress.
    paper_pbar = tqdm(
        total=n_papers,
        desc="Paper progress",
        unit="paper",
        bar_format="{l_bar}{bar:30}{r_bar}",
        colour="green",
        file=sys.stderr,
    )

    # Thread-safe field_pbar wrapper.
    class ThreadSafeFieldPbar:
        def update(self, n=1):
            with pbar_lock:
                field_pbar.update(n)
        def set_postfix_str(self, s):
            with pbar_lock:
                field_pbar.set_postfix_str(s)

    ts_field_pbar = ThreadSafeFieldPbar()

    def _eval_one_paper(paper_id, gt_paper):
        gt_abs = gt_paper.get("antibodies", [])
        pred_abs = predictions.get(paper_id, {}).get("antibodies", [])
        ps = evaluate_paper(paper_id, gt_abs, pred_abs, llm_judge, ts_field_pbar)
        return ps

    # Process papers concurrently.
    paper_scores_map = {}

    with ThreadPoolExecutor(max_workers=paper_concurrency) as executor:
        future_to_pid = {
            executor.submit(_eval_one_paper, pid, gt_paper): pid
            for pid, gt_paper in paper_items
        }
        for future in as_completed(future_to_pid):
            pid = future_to_pid[future]
            try:
                ps = future.result()
                paper_scores_map[pid] = ps
                with pbar_lock:
                    paper_pbar.update(1)
                    paper_pbar.set_postfix_str(
                        f"{pid} → {ps.accuracy:.1f}"
                    )
            except Exception as exc:
                print(f"\n  {pid} evaluation failed: {exc}", file=sys.stderr)
                with pbar_lock:
                    paper_pbar.update(1)

    field_pbar.close()
    paper_pbar.close()

    # Collect results in the original order.
    for pid, _ in paper_items:
        if pid in paper_scores_map:
            ps = paper_scores_map[pid]
            result.paper_scores.append(ps)
            for ab in ps.antibody_scores:
                result.total_fields += ab.total_fields
                result.total_score += ab.score_sum
                result.total_weight += ab.weight_sum
                result.total_weighted_score += ab.weighted_score_sum

    # Overall score is averaged only across papers with model output.
    if result.paper_scores:
        result.accuracy = sum(ps.accuracy for ps in result.paper_scores) / len(result.paper_scores)

    return result


# ==================== Report Output ====================

def generate_markdown_report(result: BenchmarkResult) -> str:
    lines = []
    lines.append("# Antibody Literature Extraction Benchmark Report (v3 Weighted + Continuous Penalty)\n")

    metadata = result.metadata or {}
    if metadata:
        lines.append("## Evaluation Scope\n")
        lines.append("| Item | Value |")
        lines.append("|------|-----|")
        if metadata.get("subset"):
            lines.append(f"| subset | {metadata['subset']} |")
        if metadata.get("gt_path"):
            lines.append(f"| ground truth | {metadata['gt_path']} |")
        if metadata.get("pred_path"):
            lines.append(f"| prediction | {metadata['pred_path']} |")
        if metadata.get("total_ground_truth_papers") is not None:
            lines.append(f"| ground truth papers | {metadata['total_ground_truth_papers']} |")
        if metadata.get("evaluated_papers") is not None:
            lines.append(f"| evaluated papers | {metadata['evaluated_papers']} |")
        if metadata.get("skipped_no_output_papers"):
            lines.append(f"| skipped no-output papers | {', '.join(metadata['skipped_no_output_papers'])} |")
        lines.append("")

    # === Overall score ===
    lines.append("## Overall Score\n")
    lines.append(f"### **{result.accuracy:.1f} / 100**\n")
    lines.append("| Metric | Value |")
    lines.append("|------|-----|")
    lines.append(f"| Evaluated papers | {len(result.paper_scores)} |")
    lines.append(f"| Scored fields | {result.total_fields} |")
    lines.append(f"| Raw score sum | {result.total_score:.1f} / {result.total_fields} |")
    lines.append(f"| Weighted score sum | {result.total_weighted_score:.1f} / {result.total_weight:.1f} |")
    lines.append("")

    # === Weight policy ===
    lines.append("## Field Weight Policy\n")
    lines.append("| Weight level | Weight | Fields |")
    lines.append("|----------|--------|----------|")
    lines.append(f"| 🔴 Core | 2.0 | {', '.join(sorted(CORE_FIELDS))} |")
    lines.append(f"| 🟡 Standard | 1.0 | {', '.join(sorted(STANDARD_FIELDS))} |")
    lines.append(f"| 🟢 Auxiliary | 0.5 | {', '.join(sorted(AUXILIARY_FIELDS))} |")
    lines.append("")

    # === Penalty formula ===
    lines.append("## Penalty Formula\n")
    lines.append("```")
    lines.append("Penalty = max(0, 1.0 - 0.01 × floor(NFP / 5) - 0.05 × NFN)")
    lines.append("Final = (Σ Record_Score_i / NGS) × 100 × Penalty")
    lines.append("```\n")

    # === Paper-level scores ===
    lines.append("## Paper-Level Scores\n")
    lines.append("| Paper ID | GT | Matched | Missing | Extra | Penalty | Raw Score | Final Score | Unmatched GT |")
    lines.append("|--------|-----|------|------|------|----------|--------|--------|----------|")
    for ps in result.paper_scores:
        unm = ', '.join(ps.unmatched_gt) if ps.unmatched_gt else '-'
        lines.append(
            f"| {ps.paper_id} | {ps.gt_antibody_count} | "
            f"{ps.matched_count} | {ps.false_negative_count} | {ps.false_positive_count} | "
            f"{ps.penalty_coeff:.2f} | "
            f"{ps.raw_accuracy:.1f} | **{ps.accuracy:.1f}** | {unm} |"
        )
    lines.append("")

    # === Per-paper detail ===
    for ps in result.paper_scores:
        lines.append(f"---\n## {ps.paper_id}\n")
        lines.append(f"- **NGS/NTP/NFN/NFP**: {ps.gt_antibody_count} / "
                     f"{ps.matched_count} / {ps.false_negative_count} / "
                     f"{ps.false_positive_count}")
        lines.append(f"- **Penalty**: {ps.penalty_coeff:.2f}")
        lines.append(f"- **Raw weighted average**: {ps.raw_accuracy:.1f}")
        lines.append(f"- **Final score**: **{ps.accuracy:.1f}**\n")

        if ps.extra_pred:
            lines.append(f"Extra predicted antibodies: {', '.join(ps.extra_pred)}\n")

        for ab in ps.antibody_scores:
            status = "matched" if ab.matched else "unmatched"
            lines.append(f"### {ab.antibody_name} {status} - {ab.accuracy:.1f} pts\n")
            lines.append("| Field | Weight | Ground Truth | Prediction | Score | Weighted | Reason |")
            lines.append("|------|------|---------|---------|------|------|------|")
            for fs in ab.field_scores:
                icon = {"exact": "✅", "partial": "⚠️", "wrong": "❌",
                        "miss": "🔲", "skip": "➖"}.get(fs.label, "?")
                gt_s = _truncate(fs.gt_value, 50)
                pr_s = _truncate(fs.pred_value, 50)
                w_tag = {2.0: "🔴", 1.0: "🟡", 0.5: "🟢"}.get(fs.weight, "")
                lines.append(
                    f"| {fs.field_name} | {w_tag}{fs.weight} | {gt_s} | {pr_s} | "
                    f"{icon} {fs.score:.1f} | {fs.weighted_score:.1f} | {fs.reason} |"
                )
            lines.append("")

    return "\n".join(lines)


def _truncate(s: str, maxlen: int) -> str:
    if not s:
        return ""
    # Escape pipes to keep Markdown tables valid.
    s = s.replace("|", "\\|")
    if len(s) > maxlen:
        return s[:maxlen] + "..."
    return s


# ==================== Serialization ====================

def result_to_dict(result: BenchmarkResult) -> dict:
    payload = {
        "accuracy": round(result.accuracy, 2),
        "total_fields": result.total_fields,
        "total_score": round(result.total_score, 2),
        "total_weight": round(result.total_weight, 2),
        "total_weighted_score": round(result.total_weighted_score, 2),
        "papers": [_paper_to_dict(ps) for ps in result.paper_scores],
    }
    if result.metadata:
        payload["metadata"] = result.metadata
    return payload


def _paper_to_dict(ps: PaperScore) -> dict:
    return {
        "paper_id": ps.paper_id,
        "gt_count": ps.gt_antibody_count,
        "pred_count": ps.pred_antibody_count,
        "matched": ps.matched_count,
        "false_negative": ps.false_negative_count,
        "false_positive": ps.false_positive_count,
        "unmatched_gt": ps.unmatched_gt,
        "extra_pred": ps.extra_pred,
        "penalty_coeff": round(ps.penalty_coeff, 4),
        "raw_accuracy": round(ps.raw_accuracy, 2),
        "accuracy": round(ps.accuracy, 2),
        "antibodies": [_antibody_to_dict(ab) for ab in ps.antibody_scores],
    }


def _antibody_to_dict(ab: AntibodyScore) -> dict:
    return {
        "name": ab.antibody_name,
        "matched": ab.matched,
        "accuracy": round(ab.accuracy, 2),
        "total_fields": ab.total_fields,
        "score_sum": round(ab.score_sum, 2),
        "weight_sum": round(ab.weight_sum, 2),
        "weighted_score_sum": round(ab.weighted_score_sum, 2),
        "fields": [
            {
                "field": f.field_name,
                "weight": f.weight,
                "gt": f.gt_value,
                "pred": f.pred_value,
                "score": f.score,
                "weighted_score": round(f.weighted_score, 2),
                "label": f.label,
                "reason": f.reason,
            }
            for f in ab.field_scores
        ],
    }
