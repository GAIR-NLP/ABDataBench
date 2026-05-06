# Document Sequence Extraction

Document Sequence Extraction is a multi-agent pipeline for extracting structured
antibody information from OCR Markdown. It targets antibody names, targets,
sequences, binding kinetics, assays, structures, mechanisms, references, and
related benchmark fields.

The repository contains the extraction agent, benchmark evaluator, static
evaluation dashboard, optional annotation backend, optional frontend source, and
optional OCR utilities.

## Features

- Multi-stage extraction: OCR repair, evidence reduction, sequence-image
  supplementation, skeleton extraction, PDB/NCBI backfill, validation, and
  reviewer correction.
- Skill-backed prompts: `agent/skills/*/SKILL.md` provides stage metadata and
  points to the original prompt assets in `agent/prompts/`. Runtime loading
  preserves the previous prompt text and extraction behavior.
- Environment-based secrets: API keys, base URLs, judge settings, and OCR tokens
  are read from environment variables or explicit CLI flags.
- Automated benchmark: `benchmark/run_eval.py` compares predictions against
  `benchmark/ground_truth/ground_truth.json` and writes JSON, Markdown, and HTML
  reports.
- One-command pipeline: `scripts/run_pipeline.py` runs extraction, benchmark
  scoring, dashboard generation, and optional local serving.

## Repository Layout

```text
agent/                  Multi-agent extraction system
agent/prompts/          Versioned prompt assets
agent/skills/           Skill metadata loaded by the agents
dataset/                Default OCR benchmark dataset
benchmark/              Ground truth, evaluator, and visualization tools
ocr/                    Optional OCR helper scripts
frontend/               Optional React frontend for annotation/review
backend/                Optional FastAPI backend for annotation/review
scripts/run_pipeline.py End-to-end extraction, evaluation, and dashboard entry
```

## Installation

```bash
cd Document-Sequence-Extraction
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create a local environment file:

```bash
cp .env.example .env
```

Set at least these values:

```bash
LLM_API_BASE=https://api.opensii.ai
LLM_API_KEY=your_api_key
LLM_MODEL=gzy/claude-4.6-sonnet
BENCHMARK_API_KEY=your_api_key
```

`.env`, generated runs, logs, caches, databases, OCR outputs, and frontend build
artifacts are ignored by git.

## Input Data

The default benchmark OCR dataset is checked in under `dataset/`. Each direct
child directory is one paper or patent. To use another dataset, pass `--ocr-dir`
to the pipeline or agent command.

The agent automatically discovers these layouts:

```text
<ocr-dir>/<paper_id>/vlm/<paper_id>.md
<ocr-dir>/<paper_id>/<paper_id>.md
<ocr-dir>/<paper_id>.md
```

The default benchmark ground truth is:

```text
benchmark/ground_truth/ground_truth.json
```

## End-to-End Run

This command runs extraction, scores the benchmark, builds the HTML dashboard,
and serves it locally:

```bash
cd Document-Sequence-Extraction
source .venv/bin/activate
set -a; source .env; set +a

python scripts/run_pipeline.py \
  --output-root runs \
  --papers-per-worker 4 \
  --llm-concurrency 8 \
  --paper-concurrency 5 \
  --trace \
  --serve \
  --host 0.0.0.0 \
  --port 8000
```

Outputs are written to `runs/<run_name>/`:

- Predictions: `runs/<run_name>/agent/benchmark_predictions.json`
- Evaluation JSON: `runs/<run_name>/benchmark/eval_result_latest.json`
- Evaluation report: `runs/<run_name>/benchmark/eval_report_latest.md`
- Dashboard: `http://localhost:8000/eval_dashboard.html`

On a remote server, replace `localhost` with the server IP or domain.

## Common Commands

Run extraction only:

```bash
python scripts/run_pipeline.py --skip-eval --output-root runs
```

Run benchmark only:

```bash
cd benchmark
python run_eval.py \
  --gt ground_truth/ground_truth.json \
  --pred ../runs/dev/agent/benchmark_predictions.json \
  --output ../runs/dev/benchmark
```

Generate a benchmark dashboard:

```bash
python benchmark/scripts/visualize_eval.py \
  runs/dev/benchmark/eval_result_latest.json \
  --output runs/dev/benchmark/eval_dashboard.html
```

Run tests:

```bash
cd agent
python -m pytest tests -q
```

## Configuration

See `.env.example` for the full environment surface:

- `LLM_API_BASE`, `LLM_API_KEY`, `LLM_MODEL`: text extraction model.
- `LLM_REVIEW_MODEL`: optional reviewer model. Defaults to `LLM_MODEL`.
- `VLM_API_BASE`, `VLM_API_KEY`, `VLM_MODEL`: image extraction model. Defaults
  to the text model settings when key/base are unset.
- `SEQUENCE_VLM_API_BASE`, `SEQUENCE_VLM_API_KEY`, `SEQUENCE_VLM_MODEL`:
  sequence-image model. Defaults to the text model settings when key/base are
  unset.
- `PDF_EXTRACT_API_BASE`, `PDF_EXTRACT_API_KEY`, `PDF_EXTRACT_MODEL`: optional
  direct-PDF helper settings. Defaults to the text model settings when unset.
- `BENCHMARK_API_KEY`, `BENCHMARK_BASE_URL`, `BENCHMARK_MODEL`: benchmark judge
  model settings.
- `NCBI_EMAIL`, `NCBI_API_KEY`: optional NCBI/PDB lookup settings.
- `MINERU_*`: optional OCR API settings.

## Skills

`agent/tools/skill_loader.py` loads prompt paths from `agent/skills/<skill>/SKILL.md`
for each agent stage. Built-in skills:

- `ocr-format-repair`
- `evidence-reduction`
- `paper-focus-analysis`
- `sequence-image-extraction`
- `figure-vlm-extraction`
- `antibody-skeleton-extraction`
- `pdb-postprocess`
- `reviewer-qa`

Skills provide metadata and prompt indirection only. They do not rewrite the
original prompt content, so the runtime extraction path stays compatible with
the previous pipeline.

## Open-Source Hygiene

The repository keeps source code, prompt/skill assets, the default OCR benchmark
fixture, ground truth, and documentation. Generated outputs, logs, OCR
intermediates, local PDFs/Excel workbooks, `node_modules`, frontend build
artifacts, SQLite databases, API keys, and `.env` files are excluded.
