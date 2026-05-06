# OCR Pipeline

This directory contains optional MinerU OCR helpers. The extraction agent reads
Markdown directly, so OCR is only needed when starting from PDFs, Office files,
or images.

## Backends

- `official-api`: MinerU official token API. The default base URL is
  `https://mineru.net`.
- `self-hosted`: a self-hosted MinerU HTTP service, invoked through the local
  `mineru -b vlm-http-client` command.

API credentials can be passed with `--api-token`, `--api-key`, or environment
variables:

```bash
export MINERU_BACKEND=official-api
export MINERU_API_TOKEN=...
export MINERU_API_KEY=...
export MINERU_API_BASE_URL=https://mineru.net
export MINERU_SELF_HOSTED_URL=http://127.0.0.1:30000
export MINERU_SELF_HOSTED_API_TOKEN=...
export MINERU_SELF_HOSTED_MODEL=mineru
```

## Entry Points

- `scripts/ocr_batch.py`: stage-1 OCR wrapper.
- `scripts/run_paper_ocr_merged.py`: merged OCR for one paper.
- `scripts/batch_paper_ocr_merged.py`: merged OCR for a batch of papers.
- `pipeline/run_two_stage_ocr_merged.sh`: shell wrapper for one paper.
- `pipeline/run_batch_papers_ocr_merged.sh`: shell wrapper for a batch.

## Examples

Single paper:

```bash
bash ocr/pipeline/run_two_stage_ocr_merged.sh \
  --input /path/to/raw_paper_dir \
  --output /path/to/ocr_output
```

Batch:

```bash
bash ocr/pipeline/run_batch_papers_ocr_merged.sh \
  --input-root /path/to/raw_papers \
  --output-root /path/to/ocr_output \
  --paper-concurrency 4
```

Single-paper output layout:

```text
<paper>/
├── <paper>.md
└── images/
```

OCR outputs are generated artifacts. Write them outside the repository, or to
ignored directories such as `runs/` or `ocr/output/`.
