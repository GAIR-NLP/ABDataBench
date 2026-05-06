# Benchmark

The benchmark evaluates agent predictions against manually curated ground truth.
It uses an LLM-as-judge for semantic field matching and writes JSON, Markdown,
and HTML artifacts.

The default ground truth is `ground_truth/ground_truth.json`.

## Run Evaluation

```bash
cd benchmark
export BENCHMARK_API_KEY="$LLM_API_KEY"

python run_eval.py \
  --gt ground_truth/ground_truth.json \
  --pred ../runs/dev/agent/benchmark_predictions.json \
  --output ../runs/dev/benchmark \
  --paper-concurrency 5
```

Supported environment variables:

- `BENCHMARK_API_KEY` or `JUDGE_API_KEY`: judge API key.
- `BENCHMARK_BASE_URL` or `JUDGE_BASE_URL`: judge API base URL.
- `BENCHMARK_MODEL` or `JUDGE_MODEL`: judge model.

When benchmark-specific variables are unset, `run_eval.py` falls back to
compatible `LLM_*` variables where possible.

## Generate Dashboard

```bash
python scripts/visualize_eval.py \
  ../runs/dev/benchmark/eval_result_latest.json \
  --output ../runs/dev/benchmark/eval_dashboard.html
```

## Prediction Format

The prediction JSON is keyed by `paper_id`:

```json
{
  "paper_id": {
    "antibodies": [
      {
        "Antibody_Name": "7D6",
        "Target_Name": "SARS-CoV-2 Spike",
        "Binding_Kinetics_KD": "6.91 nM"
      }
    ]
  }
}
```

## Regenerate Ground Truth

Generate `ground_truth/ground_truth.json` from a manually annotated workbook:

```bash
python scripts/generate_ground_truth_from_workbook.py \
  --xlsx /path/to/annotations.xlsx \
  --output ground_truth/ground_truth.json
```

Evaluation outputs should be written to `runs/` or ignored
`benchmark/results*/` directories.
