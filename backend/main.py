from __future__ import annotations

import json
import os
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator, model_validator


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
FRONTEND_DIR = PROJECT_DIR / "frontend"
FRONTEND_DIST_DIR = FRONTEND_DIR / "dist"
DEFAULT_DATASET_PATH = PROJECT_DIR / "runs" / "dev" / "benchmark" / "eval_result_latest.json"
DATASET_PATH = Path(os.environ.get("ANNOTATION_EVAL_JSON", DEFAULT_DATASET_PATH)).expanduser()
DEFAULT_PREDICTION_PATH = PROJECT_DIR / "runs" / "dev" / "agent" / "benchmark_predictions.json"
PREDICTION_PATH = Path(os.environ.get("ANNOTATION_PRED_JSON", DEFAULT_PREDICTION_PATH)).expanduser()
REPORTS_ROOT = Path(os.environ.get("ANNOTATION_REPORTS_ROOT", PROJECT_DIR / "runs")).expanduser()
RESULT_VIEW_FILES: dict[str, dict[str, Any]] = {}
DATA_DIR = BASE_DIR / "data"
DB_PATH = Path(os.environ.get("ANNOTATION_DB_PATH", DATA_DIR / "annotation_feedback.db"))
LABEL_ORDER = ["wrong", "miss", "partial", "skip", "exact"]
SEQUENCE_FIELD_ORDER = ["CDRH3_Sequence", "vh_sequence_aa", "vl_sequence_aa"]
SEQUENCE_ISSUE_LABELS = {"wrong", "miss", "partial"}
ANNOTATION_STATUS_ORDER = ["pending", "reviewed", "ignored"]
SEVERITY_ORDER = ["high", "medium", "low"]
ERROR_TYPE_ORDER = [
    "value_mismatch",
    "missing_prediction",
    "hallucinated_value",
    "incomplete_value",
    "format_issue",
    "evidence_mismatch",
    "other",
]
ISSUE_LABELS = {"wrong", "miss", "partial"}
COMPLETED_STATUSES = {"reviewed", "ignored"}


@dataclass
class DatasetStore:
    raw_summary: dict[str, Any]
    papers_by_id: dict[str, dict[str, Any]]
    paper_summaries: list[dict[str, Any]]


def build_field_stats_payload(dataset: DatasetStore) -> dict[str, Any]:
    buckets: dict[str, dict[str, Any]] = {}

    for paper in dataset.papers_by_id.values():
        for antibody in paper["antibodies"]:
            for field in antibody["fields"]:
                field_name = field.get("field", "")
                if not field_name:
                    continue

                bucket = buckets.setdefault(
                    field_name,
                    {
                        "field": field_name,
                        "total": 0,
                        "label_counts": empty_label_counter(),
                    },
                )
                bucket["total"] += 1
                label = field.get("label", "skip")
                if label not in bucket["label_counts"]:
                    label = "skip"
                bucket["label_counts"][label] += 1

    items: list[dict[str, Any]] = []
    for field_name, bucket in buckets.items():
        total = max(bucket["total"], 1)
        label_counts = bucket["label_counts"]
        partial_count = label_counts["partial"] + label_counts["wrong"]
        mismatch_count = label_counts["miss"]
        items.append(
            {
                "field": field_name,
                "total": bucket["total"],
                "label_counts": label_counts,
                "partial_count": partial_count,
                "mismatch_count": mismatch_count,
                "exact_percent": round((label_counts["exact"] / total) * 100, 1),
                "partial_percent": round((partial_count / total) * 100, 1),
                "mismatch_percent": round((mismatch_count / total) * 100, 1),
                "skip_percent": round((label_counts["skip"] / total) * 100, 1),
            }
        )

    items.sort(
        key=lambda item: (
            -item["mismatch_percent"],
            -item["partial_percent"],
            -item["total"],
            item["field"],
        )
    )
    return {
        "total_fields": dataset.raw_summary.get("total_fields", 0),
        "field_count": len(items),
        "fields": items,
    }


def build_sequence_issue_board_payload(dataset: DatasetStore) -> dict[str, Any]:
    buckets: dict[str, dict[str, Any]] = {
        field_name: {
            "field": field_name,
            "issue_count": 0,
            "exact_count": 0,
            "skip_count": 0,
            "wrong_count": 0,
            "miss_count": 0,
            "partial_count": 0,
            "papers": {},
            "entries": [],
        }
        for field_name in SEQUENCE_FIELD_ORDER
    }

    for paper in dataset.papers_by_id.values():
        for antibody in paper["antibodies"]:
            for field in antibody["fields"]:
                field_name = field.get("field", "")
                if field_name not in buckets:
                    continue

                label = field.get("label", "skip")
                bucket = buckets[field_name]
                if label == "exact":
                    bucket["exact_count"] += 1
                    continue
                if label == "skip":
                    bucket["skip_count"] += 1
                    continue
                if label not in SEQUENCE_ISSUE_LABELS:
                    continue

                bucket["issue_count"] += 1
                bucket[f"{label}_count"] += 1
                paper_counts = bucket["papers"]
                paper_counts[paper["paper_id"]] = paper_counts.get(paper["paper_id"], 0) + 1
                bucket["entries"].append(
                    {
                        "paper_id": paper["paper_id"],
                        "paper_accuracy": paper["accuracy"],
                        "antibody_index": antibody["antibody_index"],
                        "antibody_name": antibody["name"],
                        "label": label,
                        "score": field.get("score", 0),
                        "reason": field.get("reason", ""),
                        "gt": field.get("gt", ""),
                        "pred": field.get("pred", ""),
                    }
                )

    items: list[dict[str, Any]] = []
    total_issue_fields = 0
    total_sequence_fields = 0
    for field_name in SEQUENCE_FIELD_ORDER:
        bucket = buckets[field_name]
        total_for_field = bucket["issue_count"] + bucket["exact_count"] + bucket["skip_count"]
        total_issue_fields += bucket["issue_count"]
        total_sequence_fields += total_for_field
        paper_breakdown = [
            {"paper_id": paper_id, "issue_count": issue_count}
            for paper_id, issue_count in bucket["papers"].items()
        ]
        paper_breakdown.sort(key=lambda item: (-item["issue_count"], item["paper_id"]))
        bucket["entries"].sort(
            key=lambda item: (
                {"wrong": 0, "miss": 1, "partial": 2}.get(item["label"], 3),
                item["paper_id"],
                item["antibody_index"],
                item["antibody_name"],
            )
        )
        items.append(
            {
                "field": field_name,
                "issue_count": bucket["issue_count"],
                "exact_count": bucket["exact_count"],
                "skip_count": bucket["skip_count"],
                "wrong_count": bucket["wrong_count"],
                "miss_count": bucket["miss_count"],
                "partial_count": bucket["partial_count"],
                "paper_count": len(bucket["papers"]),
                "issue_percent": round((bucket["issue_count"] / total_for_field) * 100, 1)
                if total_for_field
                else 0.0,
                "paper_breakdown": paper_breakdown,
                "entries": bucket["entries"],
            }
        )

    items.sort(key=lambda item: (-item["issue_count"], item["field"]))
    return {
        "field_count": len(items),
        "total_sequence_fields": total_sequence_fields,
        "total_issue_fields": total_issue_fields,
        "fields": items,
    }


class FeedbackCreate(BaseModel):
    paper_id: str = Field(min_length=1, max_length=300)
    antibody_index: int = Field(ge=0)
    antibody_name: str = Field(min_length=1, max_length=300)
    field_name: str | None = Field(default=None, max_length=200)
    reviewer: str | None = Field(default="", max_length=120)
    comment: str = Field(min_length=1, max_length=4000)

    @field_validator("paper_id", "antibody_name", "field_name", "reviewer", "comment")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip()


class FieldAnnotationUpsert(BaseModel):
    paper_id: str = Field(min_length=1, max_length=300)
    antibody_index: int = Field(ge=0)
    antibody_name: str = Field(min_length=1, max_length=300)
    field_name: str = Field(min_length=1, max_length=200)
    original_label: Literal["wrong", "miss", "partial", "skip", "exact"]
    annotation_status: Literal["pending", "reviewed", "ignored"] = "reviewed"
    final_label: Literal["wrong", "miss", "partial", "skip", "exact"] | None = None
    error_types: list[
        Literal[
            "value_mismatch",
            "missing_prediction",
            "hallucinated_value",
            "incomplete_value",
            "format_issue",
            "evidence_mismatch",
            "other",
        ]
    ] = Field(default_factory=list)
    severity: Literal["high", "medium", "low"] = "medium"
    corrected_value: str | None = Field(default="", max_length=4000)
    note: str | None = Field(default="", max_length=4000)
    reviewer: str | None = Field(default="", max_length=120)

    @field_validator("paper_id", "antibody_name", "field_name", "corrected_value", "note", "reviewer")
    @classmethod
    def strip_annotation_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip()

    @field_validator("error_types")
    @classmethod
    def dedupe_error_types(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for item in value:
            if item not in seen:
                seen.add(item)
                result.append(item)
        return result

    @model_validator(mode="after")
    def validate_review_payload(self) -> "FieldAnnotationUpsert":
        if self.annotation_status == "reviewed" and not self.final_label:
            raise ValueError("final_label is required when annotation_status is reviewed")
        if self.final_label == "exact" and self.error_types:
            raise ValueError("error_types must be empty when final_label is exact")
        if self.annotation_status == "ignored":
            self.error_types = []
            if not self.final_label:
                self.final_label = self.original_label
        return self


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_db_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with closing(get_db_connection()) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                paper_id TEXT NOT NULL,
                antibody_index INTEGER NOT NULL,
                antibody_name TEXT NOT NULL,
                field_name TEXT,
                reviewer TEXT DEFAULT '',
                comment TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_feedback_paper_antibody
            ON feedback (paper_id, antibody_index)
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS field_annotations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                paper_id TEXT NOT NULL,
                antibody_index INTEGER NOT NULL,
                antibody_name TEXT NOT NULL,
                field_name TEXT NOT NULL,
                original_label TEXT NOT NULL,
                annotation_status TEXT NOT NULL DEFAULT 'pending',
                final_label TEXT,
                error_types TEXT NOT NULL DEFAULT '[]',
                severity TEXT NOT NULL DEFAULT 'medium',
                corrected_value TEXT DEFAULT '',
                note TEXT DEFAULT '',
                reviewer TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(paper_id, antibody_index, field_name)
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_field_annotations_paper
            ON field_annotations (paper_id, antibody_index, field_name)
            """
        )
        conn.commit()


def normalize_field(field: dict[str, Any]) -> dict[str, Any]:
    return {
        "field": field.get("field", ""),
        "weight": field.get("weight", 0),
        "gt": field.get("gt", ""),
        "pred": field.get("pred", ""),
        "score": field.get("score", 0),
        "weighted_score": field.get("weighted_score", 0),
        "label": field.get("label", "skip"),
        "reason": field.get("reason", ""),
        "provenance": {},
    }


def summarize_labels(items: list[dict[str, Any]], key: str = "label") -> dict[str, int]:
    counts = {label: 0 for label in LABEL_ORDER}
    for item in items:
        label = item.get(key, "skip")
        counts[label] = counts.get(label, 0) + 1
    return counts


def normalize_antibody_name(value: str) -> str:
    return "".join(ch.lower() for ch in str(value or "") if ch.isalnum())


def load_predictions(prediction_path: Path | None = None) -> dict[str, Any]:
    effective_path = PREDICTION_PATH if prediction_path is None else prediction_path
    if not effective_path or not effective_path.exists():
        return {}
    data = json.loads(effective_path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def build_prediction_lookup(predicted_antibodies: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    lookup: dict[str, list[dict[str, Any]]] = {}
    for antibody in predicted_antibodies:
        key = normalize_antibody_name(antibody.get("Antibody_Name", ""))
        if key:
            lookup.setdefault(key, []).append(antibody)
    return lookup


def resolve_predicted_antibody(
    lookup: dict[str, list[dict[str, Any]]],
    usage: dict[str, int],
    antibody_name: str,
) -> dict[str, Any]:
    key = normalize_antibody_name(antibody_name)
    if not key or key not in lookup:
        return {}
    offset = usage.get(key, 0)
    bucket = lookup[key]
    if offset >= len(bucket):
        return bucket[-1]
    usage[key] = offset + 1
    return bucket[offset]


def normalize_provenance(provenance: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(provenance, dict):
        return {}
    return {
        key: value
        for key, value in provenance.items()
        if value not in ("", None, [], {})
    }


def load_dataset(dataset_path: Path | None = None, prediction_path: Path | None = None) -> DatasetStore:
    effective_path = DATASET_PATH if dataset_path is None else dataset_path
    if not effective_path.exists():
        raise FileNotFoundError(f"Dataset not found: {effective_path}")

    data = json.loads(effective_path.read_text(encoding="utf-8"))
    predictions = load_predictions(prediction_path)
    papers_by_id: dict[str, dict[str, Any]] = {}
    paper_summaries: list[dict[str, Any]] = []

    for paper_index, paper in enumerate(data.get("papers", [])):
        antibodies: list[dict[str, Any]] = []
        paper_label_counts = {label: 0 for label in LABEL_ORDER}
        predicted_paper = predictions.get(paper.get("paper_id", f"paper-{paper_index}"), {})
        prediction_lookup = build_prediction_lookup(predicted_paper.get("antibodies", []))
        prediction_usage: dict[str, int] = {}

        for antibody_index, antibody in enumerate(paper.get("antibodies", [])):
            predicted_antibody = resolve_predicted_antibody(
                prediction_lookup,
                prediction_usage,
                antibody.get("name", f"Antibody {antibody_index + 1}"),
            )
            predicted_sources = predicted_antibody.get("field_sources", {})
            fields = []
            for field in antibody.get("fields", []):
                normalized_field = normalize_field(field)
                normalized_field["provenance"] = normalize_provenance(
                    predicted_sources.get(field.get("field", ""))
                )
                fields.append(normalized_field)
            field_label_counts = summarize_labels(fields)
            for label, count in field_label_counts.items():
                paper_label_counts[label] = paper_label_counts.get(label, 0) + count

            antibodies.append(
                {
                    "paper_id": paper.get("paper_id", f"paper-{paper_index}"),
                    "antibody_index": antibody_index,
                    "name": antibody.get("name", f"Antibody {antibody_index + 1}"),
                    "matched": antibody.get("matched", False),
                    "accuracy": antibody.get("accuracy", 0),
                    "total_fields": antibody.get("total_fields", len(fields)),
                    "score_sum": antibody.get("score_sum", 0),
                    "weight_sum": antibody.get("weight_sum", 0),
                    "weighted_score_sum": antibody.get("weighted_score_sum", 0),
                    "label_counts": field_label_counts,
                    "fields": fields,
                }
            )

        paper_id = paper.get("paper_id", f"paper-{paper_index}")
        detail = {
            "paper_id": paper_id,
            "gt_count": paper.get("gt_count", 0),
            "pred_count": paper.get("pred_count", 0),
            "matched": paper.get("matched", 0),
            "false_negative": paper.get("false_negative", 0),
            "false_positive": paper.get("false_positive", 0),
            "unmatched_gt": paper.get("unmatched_gt", []),
            "extra_pred": paper.get("extra_pred", []),
            "penalty_coeff": paper.get("penalty_coeff", 0),
            "raw_accuracy": paper.get("raw_accuracy", 0),
            "accuracy": paper.get("accuracy", 0),
            "antibody_count": len(antibodies),
            "label_counts": paper_label_counts,
            "antibodies": antibodies,
        }
        papers_by_id[paper_id] = detail
        paper_summaries.append(
            {
                "paper_id": paper_id,
                "paper_index": paper_index,
                "accuracy": detail["accuracy"],
                "raw_accuracy": detail["raw_accuracy"],
                "gt_count": detail["gt_count"],
                "pred_count": detail["pred_count"],
                "matched": detail["matched"],
                "false_negative": detail["false_negative"],
                "false_positive": detail["false_positive"],
                "antibody_count": detail["antibody_count"],
                "label_counts": detail["label_counts"],
            }
        )

    raw_summary = {
        "accuracy": data.get("accuracy", 0),
        "total_fields": data.get("total_fields", 0),
        "total_score": data.get("total_score", 0),
        "total_weight": data.get("total_weight", 0),
        "total_weighted_score": data.get("total_weighted_score", 0),
        "paper_count": len(paper_summaries),
        "antibody_count": sum(paper["antibody_count"] for paper in paper_summaries),
        "dataset_path": str(effective_path),
        "label_counts": summarize_labels(
            [field for paper in papers_by_id.values() for antibody in paper["antibodies"] for field in antibody["fields"]]
        ),
    }
    return DatasetStore(raw_summary=raw_summary, papers_by_id=papers_by_id, paper_summaries=paper_summaries)


def resolve_report_path(report_path: str) -> Path:
    candidate = (REPORTS_ROOT / report_path).resolve()
    root = REPORTS_ROOT.resolve()
    if candidate != root and root not in candidate.parents:
        raise HTTPException(status_code=400, detail="Invalid report path")
    if not candidate.exists() or not candidate.is_file():
        raise HTTPException(status_code=404, detail=f"Report not found: {report_path}")
    return candidate


def list_report_entries() -> list[dict[str, Any]]:
    if not REPORTS_ROOT.exists():
        return []

    entries: list[dict[str, Any]] = []
    for path in REPORTS_ROOT.rglob("eval_report*.md"):
        relative = path.relative_to(REPORTS_ROOT).as_posix()
        stat = path.stat()
        label = relative.replace("/eval_report_latest.md", "").replace("/eval_report_", " / ")
        entries.append(
            {
                "path": relative,
                "title": path.parent.name if path.parent != REPORTS_ROOT else path.stem,
                "label": label,
                "updated_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                "size_bytes": stat.st_size,
            }
        )

    entries.sort(key=lambda item: item["updated_at"], reverse=True)
    return entries


@lru_cache(maxsize=1)
def get_dataset() -> DatasetStore:
    return load_dataset(DATASET_PATH, PREDICTION_PATH)


@lru_cache(maxsize=16)
def get_dataset_for_path(dataset_path: str, prediction_path: str = "") -> DatasetStore:
    resolved_prediction_path = Path(prediction_path) if prediction_path else None
    return load_dataset(Path(dataset_path), resolved_prediction_path)


def dynamic_result_view_configs() -> dict[str, dict[str, Any]]:
    if not REPORTS_ROOT.exists():
        return {}

    configs: dict[str, dict[str, Any]] = {}
    for dataset_path in REPORTS_ROOT.rglob("eval_result_latest.json"):
        run_root = dataset_path.parent.parent if dataset_path.parent.name == "benchmark" else dataset_path.parent
        try:
            view_id = dataset_path.parent.relative_to(REPORTS_ROOT).as_posix()
        except ValueError:
            view_id = dataset_path.parent.name
        prediction_path = run_root / "agent" / "benchmark_predictions.json"
        configs[view_id] = {
            "dataset_path": dataset_path,
            "prediction_path": prediction_path if prediction_path.exists() else None,
            "title": dataset_path.parent.name,
            "label": view_id,
        }
    return configs


def resolve_result_view_config(view_id: str) -> dict[str, Any]:
    config = RESULT_VIEW_FILES.get(view_id) or dynamic_result_view_configs().get(view_id)
    if config is None:
        raise HTTPException(status_code=404, detail=f"Unknown result view: {view_id}")
    dataset_path = config["dataset_path"]
    if not dataset_path.exists():
        raise HTTPException(status_code=404, detail=f"Dataset not found for result view: {view_id}")
    return config


def list_result_views() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    configs = {**dynamic_result_view_configs(), **RESULT_VIEW_FILES}
    for view_id, config in configs.items():
        dataset_path = config["dataset_path"]
        if not dataset_path.exists():
            continue
        stat = dataset_path.stat()
        items.append(
            {
                "id": view_id,
                "title": config["title"],
                "label": config["label"],
                "updated_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                "dataset_path": str(dataset_path),
            }
        )

    items.sort(key=lambda item: item["updated_at"], reverse=True)
    return items


def get_result_view_dataset(view_id: str) -> DatasetStore:
    config = resolve_result_view_config(view_id)
    dataset_path = config["dataset_path"]
    prediction_path = config.get("prediction_path")
    return get_dataset_for_path(
        str(dataset_path),
        str(prediction_path) if prediction_path and Path(prediction_path).exists() else "",
    )


def serialize_feedback(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "paper_id": row["paper_id"],
        "antibody_index": row["antibody_index"],
        "antibody_name": row["antibody_name"],
        "field_name": row["field_name"],
        "reviewer": row["reviewer"],
        "comment": row["comment"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def parse_error_types(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    values = [str(item) for item in parsed if str(item) in ERROR_TYPE_ORDER]
    return values


def serialize_annotation(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "paper_id": row["paper_id"],
        "antibody_index": row["antibody_index"],
        "antibody_name": row["antibody_name"],
        "field_name": row["field_name"],
        "original_label": row["original_label"],
        "annotation_status": row["annotation_status"],
        "final_label": row["final_label"],
        "error_types": parse_error_types(row["error_types"]),
        "severity": row["severity"],
        "corrected_value": row["corrected_value"],
        "note": row["note"],
        "reviewer": row["reviewer"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def fetch_feedback_for_paper(paper_id: str) -> list[dict[str, Any]]:
    with closing(get_db_connection()) as conn:
        rows = conn.execute(
            """
            SELECT id, paper_id, antibody_index, antibody_name, field_name, reviewer, comment, created_at, updated_at
            FROM feedback
            WHERE paper_id = ?
            ORDER BY created_at DESC, id DESC
            """,
            (paper_id,),
        ).fetchall()
    return [serialize_feedback(row) for row in rows]


def fetch_feedback_summary() -> dict[str, Any]:
    with closing(get_db_connection()) as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS total_feedback,
                COUNT(DISTINCT paper_id) AS papers_with_feedback,
                COUNT(DISTINCT paper_id || '::' || antibody_index) AS antibodies_with_feedback
            FROM feedback
            """
        ).fetchone()
    return {
        "total_feedback": row["total_feedback"] if row else 0,
        "papers_with_feedback": row["papers_with_feedback"] if row else 0,
        "antibodies_with_feedback": row["antibodies_with_feedback"] if row else 0,
    }


def fetch_all_annotations() -> list[dict[str, Any]]:
    with closing(get_db_connection()) as conn:
        rows = conn.execute(
            """
            SELECT
                id, paper_id, antibody_index, antibody_name, field_name, original_label,
                annotation_status, final_label, error_types, severity, corrected_value,
                note, reviewer, created_at, updated_at
            FROM field_annotations
            ORDER BY updated_at DESC, id DESC
            """
        ).fetchall()
    return [serialize_annotation(row) for row in rows]


def fetch_annotations_for_paper(paper_id: str) -> list[dict[str, Any]]:
    with closing(get_db_connection()) as conn:
        rows = conn.execute(
            """
            SELECT
                id, paper_id, antibody_index, antibody_name, field_name, original_label,
                annotation_status, final_label, error_types, severity, corrected_value,
                note, reviewer, created_at, updated_at
            FROM field_annotations
            WHERE paper_id = ?
            ORDER BY antibody_index ASC, field_name ASC, id DESC
            """,
            (paper_id,),
        ).fetchall()
    return [serialize_annotation(row) for row in rows]


def build_annotation_lookup(
    annotations: list[dict[str, Any]],
) -> dict[tuple[str, int, str], dict[str, Any]]:
    return {
        (annotation["paper_id"], annotation["antibody_index"], annotation["field_name"]): annotation
        for annotation in annotations
    }


def empty_label_counter() -> dict[str, int]:
    return {label: 0 for label in LABEL_ORDER}


def empty_status_counter() -> dict[str, int]:
    return {status: 0 for status in ANNOTATION_STATUS_ORDER}


def empty_severity_counter() -> dict[str, int]:
    return {severity: 0 for severity in SEVERITY_ORDER}


def empty_error_type_counter() -> dict[str, int]:
    return {error_type: 0 for error_type in ERROR_TYPE_ORDER}


def summarize_scope(fields: list[dict[str, Any]], annotations: list[dict[str, Any]]) -> dict[str, Any]:
    total_fields = len(fields)
    issue_fields = sum(1 for field in fields if field["label"] in ISSUE_LABELS)
    annotated_fields = len(annotations)
    completed_annotations = [item for item in annotations if item["annotation_status"] in COMPLETED_STATUSES]
    reviewed_issue_fields = 0
    final_label_counts = empty_label_counter()
    status_counts = empty_status_counter()
    severity_counts = empty_severity_counter()
    error_type_counts = empty_error_type_counter()

    issue_keys = {
        (field["paper_id"], field["antibody_index"], field["field"])
        for field in fields
        if field["label"] in ISSUE_LABELS
    }

    for annotation in annotations:
        status_counts[annotation["annotation_status"]] = status_counts.get(annotation["annotation_status"], 0) + 1
        severity_counts[annotation["severity"]] = severity_counts.get(annotation["severity"], 0) + 1
        if annotation["final_label"] in final_label_counts:
            final_label_counts[annotation["final_label"]] += 1
        for error_type in annotation["error_types"]:
            error_type_counts[error_type] = error_type_counts.get(error_type, 0) + 1
        if (
            annotation["annotation_status"] in COMPLETED_STATUSES
            and (annotation["paper_id"], annotation["antibody_index"], annotation["field_name"]) in issue_keys
        ):
            reviewed_issue_fields += 1

    progress = round((reviewed_issue_fields / issue_fields) * 100, 1) if issue_fields else 100.0
    return {
        "total_fields": total_fields,
        "issue_fields": issue_fields,
        "annotated_fields": annotated_fields,
        "completed_annotations": len(completed_annotations),
        "reviewed_issue_fields": reviewed_issue_fields,
        "pending_issue_fields": max(issue_fields - reviewed_issue_fields, 0),
        "progress_percent": progress,
        "status_counts": status_counts,
        "final_label_counts": final_label_counts,
        "severity_counts": severity_counts,
        "error_type_counts": error_type_counts,
        "has_annotations": annotated_fields > 0,
        "is_completed": reviewed_issue_fields >= issue_fields,
    }


def build_paper_detail_with_annotations(
    paper: dict[str, Any],
    annotation_lookup: dict[tuple[str, int, str], dict[str, Any]],
) -> dict[str, Any]:
    antibodies: list[dict[str, Any]] = []
    flat_fields: list[dict[str, Any]] = []
    flat_annotations: list[dict[str, Any]] = []

    for antibody in paper["antibodies"]:
        fields: list[dict[str, Any]] = []
        antibody_annotations: list[dict[str, Any]] = []

        for field in antibody["fields"]:
            field_key = (paper["paper_id"], antibody["antibody_index"], field["field"])
            annotation = annotation_lookup.get(field_key)
            field_payload = {
                **field,
                "paper_id": paper["paper_id"],
                "antibody_index": antibody["antibody_index"],
                "antibody_name": antibody["name"],
                "annotation": annotation,
            }
            fields.append(field_payload)
            flat_fields.append(field_payload)
            if annotation:
                antibody_annotations.append(annotation)
                flat_annotations.append(annotation)

        antibody_summary = summarize_scope(fields, antibody_annotations)
        antibodies.append(
            {
                **antibody,
                "fields": fields,
                "annotation_summary": antibody_summary,
            }
        )

    detail_summary = summarize_scope(flat_fields, flat_annotations)
    return {
        **paper,
        "antibodies": antibodies,
        "annotation_summary": detail_summary,
        "annotations": flat_annotations,
    }


def build_dataset_annotation_summary(dataset: DatasetStore, all_annotations: list[dict[str, Any]]) -> dict[str, Any]:
    all_fields = [
        {
            **field,
            "paper_id": paper["paper_id"],
            "antibody_index": antibody["antibody_index"],
        }
        for paper in dataset.papers_by_id.values()
        for antibody in paper["antibodies"]
        for field in antibody["fields"]
    ]
    base_summary = summarize_scope(all_fields, all_annotations)
    started_papers = len({annotation["paper_id"] for annotation in all_annotations})
    completed_papers = 0

    annotation_lookup = build_annotation_lookup(all_annotations)
    for paper in dataset.papers_by_id.values():
        detail = build_paper_detail_with_annotations(paper, annotation_lookup)
        if detail["annotation_summary"]["is_completed"]:
            completed_papers += 1

    return {
        **base_summary,
        "started_papers": started_papers,
        "completed_papers": completed_papers,
    }


def fetch_annotation_summary() -> dict[str, Any]:
    dataset = get_dataset()
    all_annotations = fetch_all_annotations()
    return build_dataset_annotation_summary(dataset, all_annotations)


def build_readonly_dataset_payload(dataset: DatasetStore) -> dict[str, Any]:
    annotation_summary = build_dataset_annotation_summary(dataset, [])
    return {
        **dataset.raw_summary,
        "annotation_summary": annotation_summary,
        "feedback": {
            "total_feedback": 0,
            "papers_with_feedback": 0,
            "antibodies_with_feedback": 0,
        },
    }


def build_readonly_paper_summaries(dataset: DatasetStore) -> list[dict[str, Any]]:
    papers: list[dict[str, Any]] = []
    for summary in dataset.paper_summaries:
        paper = dataset.papers_by_id[summary["paper_id"]]
        detail = build_paper_detail_with_annotations(paper, {})
        papers.append(
            {
                **summary,
                "annotation_summary": detail["annotation_summary"],
            }
        )
    return papers


def build_readonly_paper_detail(dataset: DatasetStore, paper_id: str) -> dict[str, Any]:
    paper = dataset.papers_by_id.get(paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail=f"Unknown paper_id: {paper_id}")

    return {
        **build_paper_detail_with_annotations(paper, {}),
        "feedback": [],
    }


def validate_annotation_payload(payload: FieldAnnotationUpsert, dataset: DatasetStore) -> dict[str, Any]:
    paper = dataset.papers_by_id.get(payload.paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail=f"Unknown paper_id: {payload.paper_id}")

    if payload.antibody_index >= len(paper["antibodies"]):
        raise HTTPException(status_code=400, detail="Invalid antibody_index")

    antibody = paper["antibodies"][payload.antibody_index]
    if antibody["name"] != payload.antibody_name:
        raise HTTPException(status_code=400, detail="antibody_name does not match antibody_index")

    field = next((item for item in antibody["fields"] if item["field"] == payload.field_name), None)
    if not field:
        raise HTTPException(status_code=400, detail="Unknown field_name for this antibody")

    if field["label"] != payload.original_label:
        raise HTTPException(status_code=400, detail="original_label does not match dataset label")

    return {
        "paper": paper,
        "antibody": antibody,
        "field": field,
    }


app = FastAPI(title="Document Sequence Annotation App")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    get_dataset()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/summary")
def get_summary() -> dict[str, Any]:
    dataset = get_dataset()
    return {
        **dataset.raw_summary,
        "annotation_summary": fetch_annotation_summary(),
        "feedback": fetch_feedback_summary(),
    }


@app.get("/api/papers")
def get_papers() -> dict[str, Any]:
    dataset = get_dataset()
    all_annotations = fetch_all_annotations()
    annotation_lookup = build_annotation_lookup(all_annotations)
    papers: list[dict[str, Any]] = []

    for summary in dataset.paper_summaries:
        paper = dataset.papers_by_id[summary["paper_id"]]
        detail = build_paper_detail_with_annotations(paper, annotation_lookup)
        papers.append(
            {
                **summary,
                "annotation_summary": detail["annotation_summary"],
            }
        )

    return {"papers": papers}


@app.get("/api/papers/{paper_id:path}")
def get_paper_detail(paper_id: str) -> dict[str, Any]:
    dataset = get_dataset()
    paper = dataset.papers_by_id.get(paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail=f"Unknown paper_id: {paper_id}")

    annotations = fetch_annotations_for_paper(paper_id)
    detail = build_paper_detail_with_annotations(paper, build_annotation_lookup(annotations))
    return {
        **detail,
        "feedback": fetch_feedback_for_paper(paper_id),
    }


@app.get("/api/annotations/summary")
def get_annotation_summary() -> dict[str, Any]:
    return fetch_annotation_summary()


@app.get("/api/field-stats")
def get_field_stats() -> dict[str, Any]:
    return build_field_stats_payload(get_dataset())


@app.get("/api/sequence-issue-board")
def get_sequence_issue_board() -> dict[str, Any]:
    return build_sequence_issue_board_payload(get_dataset())


@app.get("/api/result-views")
def get_result_views() -> dict[str, Any]:
    views = list_result_views()
    return {
        "views": views,
        "default_id": views[0]["id"] if views else "",
    }


@app.get("/api/result-views/{view_id}/summary")
def get_result_view_summary(view_id: str) -> dict[str, Any]:
    dataset = get_result_view_dataset(view_id)
    return build_readonly_dataset_payload(dataset)


@app.get("/api/result-views/{view_id}/papers")
def get_result_view_papers(view_id: str) -> dict[str, Any]:
    dataset = get_result_view_dataset(view_id)
    return {"papers": build_readonly_paper_summaries(dataset)}


@app.get("/api/result-views/{view_id}/papers/{paper_id:path}")
def get_result_view_paper_detail(view_id: str, paper_id: str) -> dict[str, Any]:
    dataset = get_result_view_dataset(view_id)
    return build_readonly_paper_detail(dataset, paper_id)


@app.get("/api/result-views/{view_id}/field-stats")
def get_result_view_field_stats(view_id: str) -> dict[str, Any]:
    return build_field_stats_payload(get_result_view_dataset(view_id))


@app.get("/api/result-views/{view_id}/sequence-issue-board")
def get_result_view_sequence_issue_board(view_id: str) -> dict[str, Any]:
    return build_sequence_issue_board_payload(get_result_view_dataset(view_id))


@app.get("/api/reports")
def get_reports() -> dict[str, Any]:
    reports = list_report_entries()
    return {
        "reports": reports,
        "default_path": reports[0]["path"] if reports else "",
        "reports_root": str(REPORTS_ROOT),
    }


@app.get("/api/reports/content")
def get_report_content(path: str) -> dict[str, Any]:
    report_path = resolve_report_path(path)
    relative = report_path.relative_to(REPORTS_ROOT).as_posix()
    stat = report_path.stat()
    return {
        "path": relative,
        "title": report_path.parent.name if report_path.parent != REPORTS_ROOT else report_path.stem,
        "updated_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        "size_bytes": stat.st_size,
        "content": report_path.read_text(encoding="utf-8"),
    }


@app.post("/api/annotations")
def upsert_annotation(payload: FieldAnnotationUpsert) -> dict[str, Any]:
    dataset = get_dataset()
    validate_annotation_payload(payload, dataset)
    now = utc_now_iso()

    with closing(get_db_connection()) as conn:
        conn.execute(
            """
            INSERT INTO field_annotations (
                paper_id, antibody_index, antibody_name, field_name, original_label,
                annotation_status, final_label, error_types, severity,
                corrected_value, note, reviewer, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(paper_id, antibody_index, field_name) DO UPDATE SET
                antibody_name = excluded.antibody_name,
                original_label = excluded.original_label,
                annotation_status = excluded.annotation_status,
                final_label = excluded.final_label,
                error_types = excluded.error_types,
                severity = excluded.severity,
                corrected_value = excluded.corrected_value,
                note = excluded.note,
                reviewer = excluded.reviewer,
                updated_at = excluded.updated_at
            """,
            (
                payload.paper_id,
                payload.antibody_index,
                payload.antibody_name,
                payload.field_name,
                payload.original_label,
                payload.annotation_status,
                payload.final_label,
                json.dumps(payload.error_types, ensure_ascii=False),
                payload.severity,
                payload.corrected_value or "",
                payload.note or "",
                payload.reviewer or "",
                now,
                now,
            ),
        )
        conn.commit()
        row = conn.execute(
            """
            SELECT
                id, paper_id, antibody_index, antibody_name, field_name, original_label,
                annotation_status, final_label, error_types, severity, corrected_value,
                note, reviewer, created_at, updated_at
            FROM field_annotations
            WHERE paper_id = ? AND antibody_index = ? AND field_name = ?
            """,
            (payload.paper_id, payload.antibody_index, payload.field_name),
        ).fetchone()

    return {
        "annotation": serialize_annotation(row),
        "annotation_summary": fetch_annotation_summary(),
        "paper_annotation_summary": get_paper_detail(payload.paper_id)["annotation_summary"],
    }


@app.post("/api/feedback")
def create_feedback(payload: FeedbackCreate) -> dict[str, Any]:
    dataset = get_dataset()
    paper = dataset.papers_by_id.get(payload.paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail=f"Unknown paper_id: {payload.paper_id}")

    if payload.antibody_index >= len(paper["antibodies"]):
        raise HTTPException(status_code=400, detail="Invalid antibody_index")

    antibody = paper["antibodies"][payload.antibody_index]
    if antibody["name"] != payload.antibody_name:
        raise HTTPException(status_code=400, detail="antibody_name does not match antibody_index")

    if payload.field_name:
        valid_fields = {field["field"] for field in antibody["fields"]}
        if payload.field_name not in valid_fields:
            raise HTTPException(status_code=400, detail="Unknown field_name for this antibody")

    if not payload.comment.strip():
        raise HTTPException(status_code=400, detail="comment is required")

    now = utc_now_iso()
    with closing(get_db_connection()) as conn:
        cursor = conn.execute(
            """
            INSERT INTO feedback (
                paper_id, antibody_index, antibody_name, field_name, reviewer, comment, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.paper_id,
                payload.antibody_index,
                payload.antibody_name,
                payload.field_name,
                payload.reviewer or "",
                payload.comment,
                now,
                now,
            ),
        )
        conn.commit()
        feedback_id = cursor.lastrowid

    with closing(get_db_connection()) as conn:
        row = conn.execute(
            """
            SELECT id, paper_id, antibody_index, antibody_name, field_name, reviewer, comment, created_at, updated_at
            FROM feedback
            WHERE id = ?
            """,
            (feedback_id,),
        ).fetchone()

    return {
        "feedback": serialize_feedback(row),
        "feedback_summary": fetch_feedback_summary(),
    }


if (FRONTEND_DIST_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST_DIR / "assets"), name="assets")


@app.get("/")
def serve_index() -> RedirectResponse:
    return RedirectResponse(url="/reports", status_code=307)


@app.get("/{full_path:path}")
def serve_spa(full_path: str) -> FileResponse:
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not found")

    direct_file = FRONTEND_DIST_DIR / full_path
    if direct_file.exists() and direct_file.is_file():
        return FileResponse(direct_file)

    index_path = FRONTEND_DIST_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Frontend dist/index.html not found")
    return FileResponse(index_path)
