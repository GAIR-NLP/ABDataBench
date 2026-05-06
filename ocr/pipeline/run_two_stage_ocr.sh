#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

INPUT_PATH=""
OUTPUT_DIR=""
CONCURRENCY=4
PAGE_CONCURRENCY=100
FINAL_MERGE=""
BACKEND="${MINERU_BACKEND:-official-api}"
SERVER_URL="${MINERU_API_BASE_URL:-${MINERU_SELF_HOSTED_URL:-}}"
API_TOKEN="${MINERU_API_TOKEN:-${MINERU_SELF_HOSTED_API_TOKEN:-}}"
MODEL_NAME="${MINERU_SELF_HOSTED_MODEL:-}"

usage() {
  cat <<'EOF'
Usage:
  run_two_stage_ocr.sh --input PATH --output DIR [--concurrency N] [--page-concurrency N] [--final-merge FILE] [--backend official-api|self-hosted] [--server-url URL] [--api-token TOKEN] [--model-name NAME]

Pipeline:
  1. Stage 1 MinerU OCR for pdf/doc/docx/ppt/pptx
  2. Stage 2 image OCR postprocess for each generated stage-1 markdown
  3. Optional merge of all *_enhanced.md files
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
    --final-merge)
      FINAL_MERGE="$2"
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

mkdir -p "$OUTPUT_DIR"

python "$REPO_ROOT/ocr/scripts/ocr_batch.py" \
  --input "$INPUT_PATH" \
  --output "$OUTPUT_DIR" \
  --concurrency "$CONCURRENCY" \
  --page-concurrency "$PAGE_CONCURRENCY" \
  --backend "$BACKEND" \
  ${SERVER_URL:+--server-url "$SERVER_URL"} \
  ${API_TOKEN:+--api-token "$API_TOKEN"} \
  ${MODEL_NAME:+--model-name "$MODEL_NAME"}

mapfile -t STAGE1_MDS < <(find "$OUTPUT_DIR" -path '*/vlm/*.md' -type f | sort)

if [[ ${#STAGE1_MDS[@]} -eq 0 ]]; then
  echo "No stage-1 markdown outputs found under $OUTPUT_DIR" >&2
  exit 1
fi

for md in "${STAGE1_MDS[@]}"; do
  python "$REPO_ROOT/ocr/scripts/ocr_images_postprocess.py" \
    --md "$md" \
    --concurrency "$CONCURRENCY" \
    --page-concurrency "$PAGE_CONCURRENCY" \
    --backend "$BACKEND" \
    ${SERVER_URL:+--server-url "$SERVER_URL"} \
    ${API_TOKEN:+--api-token "$API_TOKEN"} \
    ${MODEL_NAME:+--model-name "$MODEL_NAME"}
done

if [[ -n "$FINAL_MERGE" ]]; then
  python - "$OUTPUT_DIR" "$FINAL_MERGE" <<'PY'
import sys
from pathlib import Path

root = Path(sys.argv[1])
out = Path(sys.argv[2])
files = sorted(root.rglob("*_enhanced.md"))
if not files:
    raise SystemExit("No *_enhanced.md files found to merge")

parts = []
for path in files:
    parts.append(f"# {path.stem}\n\n{path.read_text(encoding='utf-8')}")

out.write_text("\n\n---\n\n".join(parts), encoding="utf-8")
print(f"Merged {len(files)} enhanced markdown files -> {out}")
PY
fi

echo "Two-stage OCR pipeline completed."
