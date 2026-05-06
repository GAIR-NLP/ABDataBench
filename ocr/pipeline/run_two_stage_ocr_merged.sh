#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

INPUT_PATH=""
OUTPUT_DIR=""
CONCURRENCY=30
PAGE_CONCURRENCY=100
BACKEND="${MINERU_BACKEND:-official-api}"
SERVER_URL="${MINERU_API_BASE_URL:-${MINERU_SELF_HOSTED_URL:-}}"
API_TOKEN="${MINERU_API_TOKEN:-${MINERU_SELF_HOSTED_API_TOKEN:-}}"
MODEL_NAME="${MINERU_SELF_HOSTED_MODEL:-}"

usage() {
  cat <<'EOF'
Usage:
  run_two_stage_ocr_merged.sh --input PATH --output DIR [--concurrency N] [--page-concurrency N] [--backend official-api|self-hosted] [--server-url URL] [--api-token TOKEN] [--model-name NAME]

Current workflow:
  1. Read only top-level raw files from one paper directory (or one file)
  2. Run one-pass OCR on each top-level source PDF/file
  3. Merge all stage-1 Markdown into <paper>.md
  4. Collect all */vlm/images into one root images/
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --input)
      INPUT_PATH="$2"
      shift 2
      ;;
    --output)
      OUTPUT_DIR="$2"
      shift 2
      ;;
    --concurrency)
      CONCURRENCY="$2"
      shift 2
      ;;
    --page-concurrency)
      PAGE_CONCURRENCY="$2"
      shift 2
      ;;
    --backend)
      BACKEND="$2"
      shift 2
      ;;
    --server-url)
      SERVER_URL="$2"
      shift 2
      ;;
    --api-token)
      API_TOKEN="$2"
      shift 2
      ;;
    --model-name)
      MODEL_NAME="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$INPUT_PATH" || -z "$OUTPUT_DIR" ]]; then
  usage
  exit 1
fi

python3 "$REPO_ROOT/ocr/scripts/run_paper_ocr_merged.py" \
  --input "$INPUT_PATH" \
  --output "$OUTPUT_DIR" \
  --concurrency "$CONCURRENCY" \
  --page-concurrency "$PAGE_CONCURRENCY" \
  --backend "$BACKEND" \
  ${SERVER_URL:+--server-url "$SERVER_URL"} \
  ${API_TOKEN:+--api-token "$API_TOKEN"} \
  ${MODEL_NAME:+--model-name "$MODEL_NAME"}
