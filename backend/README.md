# Annotation Backend

This optional FastAPI service serves benchmark evaluation data and records
field-level human review feedback in SQLite.

## Start

```bash
cd Document-Sequence-Extraction
uvicorn backend.main:app --host 0.0.0.0 --port 8001
```

## Environment Variables

- `ANNOTATION_EVAL_JSON`: evaluation JSON path. Defaults to
  `runs/dev/benchmark/eval_result_latest.json`.
- `ANNOTATION_PRED_JSON`: agent prediction JSON path. Defaults to
  `runs/dev/agent/benchmark_predictions.json`.
- `ANNOTATION_REPORTS_ROOT`: root directory scanned for generated evaluation
  runs. Defaults to `runs/`.
- `ANNOTATION_DB_PATH`: SQLite feedback database path.
