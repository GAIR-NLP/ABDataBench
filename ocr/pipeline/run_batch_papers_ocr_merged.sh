#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

INPUT_ROOT=""
OUTPUT_ROOT=""
PAPER_CONCURRENCY=10
IMAGE_CONCURRENCY=30
PAGE_CONCURRENCY=100
BACKEND="${MINERU_BACKEND:-official-api}"
SERVER_URL="${MINERU_API_BASE_URL:-${MINERU_SELF_HOSTED_URL:-}}"
API_KEY="${MINERU_API_KEY:-}"
API_TOKEN="${MINERU_API_TOKEN:-${MINERU_SELF_HOSTED_API_TOKEN:-}}"
MODEL_NAME="${MINERU_SELF_HOSTED_MODEL:-}"
FORCE=""

usage() {
  cat <<'EOF'
Usage:
  run_batch_papers_ocr_merged.sh --input-root DIR --output-root DIR [--paper-concurrency N] [--image-concurrency N] [--page-concurrency N] [--backend official-api|self-hosted] [--server-url URL] [--api-key KEY] [--api-token TOKEN] [--model-name NAME] [--force]

Current workflow:
  1. Treat each top-level subdirectory under input-root as one paper
  2. For each paper, OCR only top-level raw files once
  3. Produce <paper>.md and images/
  4. Write batch summary files under output-root
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --input-root)
      INPUT_ROOT="$2"
      shift 2
      ;;
    --output-root)
      OUTPUT_ROOT="$2"
      shift 2
      ;;
    --paper-concurrency)
      PAPER_CONCURRENCY="$2"
      shift 2
      ;;
    --image-concurrency)
      IMAGE_CONCURRENCY="$2"
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
    --api-key)
      API_KEY="$2"
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
    --force)
      FORCE="--force"
      shift 1
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

if [[ -z "$INPUT_ROOT" || -z "$OUTPUT_ROOT" ]]; then
  usage
  exit 1
fi

python3 "$REPO_ROOT/ocr/scripts/batch_paper_ocr_merged.py" \
  --input-root "$INPUT_ROOT" \
  --output-root "$OUTPUT_ROOT" \
  --paper-concurrency "$PAPER_CONCURRENCY" \
  --image-concurrency "$IMAGE_CONCURRENCY" \
  --page-concurrency "$PAGE_CONCURRENCY" \
  --backend "$BACKEND" \
  ${SERVER_URL:+--server-url "$SERVER_URL"} \
  ${API_KEY:+--api-key "$API_KEY"} \
  ${API_TOKEN:+--api-token "$API_TOKEN"} \
  ${MODEL_NAME:+--model-name "$MODEL_NAME"} \
  $FORCE
