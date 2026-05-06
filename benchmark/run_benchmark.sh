#!/bin/bash
# Benchmark run helper. Configure paths and API credentials with environment variables.
set -e

OUTDIR="${BENCHMARK_OUTPUT_DIR:-results/manual}"
LOGFILE="${OUTDIR}.log"
GT_PATH="${BENCHMARK_GT_PATH:-ground_truth/ground_truth.json}"
PRED_PATH="${BENCHMARK_PRED_PATH:?Set BENCHMARK_PRED_PATH to the prediction JSON path}"
JUDGE_API_KEY="${BENCHMARK_API_KEY:-${ANTHROPIC_AUTH_TOKEN:-${LLM_API_KEY:-}}}"
JUDGE_BASE_URL="${BENCHMARK_BASE_URL:-${ANTHROPIC_BASE_URL:-https://api.opensii.ai}}"
JUDGE_MODEL="${BENCHMARK_MODEL:-gzy/claude-4.6-sonnet}"

if [[ -z "$JUDGE_API_KEY" ]]; then
  echo "Set BENCHMARK_API_KEY, ANTHROPIC_AUTH_TOKEN, or LLM_API_KEY before running." >&2
  exit 1
fi

cd "$(dirname "$0")"
mkdir -p "$OUTDIR"

echo "=== Benchmark started at $(date) ===" | tee "$LOGFILE"
echo "Output dir: $OUTDIR" | tee -a "$LOGFILE"
echo "Log file: $LOGFILE" | tee -a "$LOGFILE"
echo "" | tee -a "$LOGFILE"

python run_eval.py \
  --gt "$GT_PATH" \
  --pred "$PRED_PATH" \
  --api-key "$JUDGE_API_KEY" \
  --base-url "$JUDGE_BASE_URL" \
  --model "$JUDGE_MODEL" \
  --output "$OUTDIR" \
  2>&1 | tee -a "$LOGFILE"

echo "" | tee -a "$LOGFILE"
echo "=== Benchmark finished at $(date) ===" | tee -a "$LOGFILE"
