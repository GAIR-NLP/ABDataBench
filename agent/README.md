# Agent

The agent package implements the multi-stage antibody extraction pipeline. It
accepts OCR Markdown, extracts benchmark-compatible antibody records, and writes
both detailed audit artifacts and flattened prediction JSON.

## Pipeline Stages

1. `ScannerAgent` collects regex hints from text.
2. `OCRRepairAgent` optionally repairs OCR formatting while preserving tokens.
3. `ReducerAgent` filters long papers to keep extraction-relevant evidence.
4. `PaperFocusAgent` builds a compact strategy for difficult papers.
5. `SequenceImageTool` extracts sequence evidence from alignment images.
6. `SkeletonAgent` builds the primary antibody JSON skeleton.
7. Enrichment tools backfill PDB/NCBI, table, text-sequence, and image evidence.
8. `ValidatorAgent` checks biological and schema-level constraints.
9. `ReviewerAgent` produces correction instructions when validation fails.
10. The orchestrator writes final JSON and benchmark-compatible predictions.

## Skills and Prompts

Prompts are loaded through `agent/tools/skill_loader.py`. Each skill lives under
`agent/skills/<skill>/SKILL.md` and points to the original prompt files in
`agent/prompts/`.

Built-in skills:

- `ocr-format-repair`
- `evidence-reduction`
- `paper-focus-analysis`
- `sequence-image-extraction`
- `figure-vlm-extraction`
- `antibody-skeleton-extraction`
- `pdb-postprocess`
- `reviewer-qa`

The skill layer provides metadata and prompt indirection only. It does not
rewrite prompt content, which keeps behavior compatible with the original
pipeline.

## Configuration

The agent reads settings from environment variables and CLI flags. The most
important variables are:

```bash
export LLM_API_BASE="https://api.opensii.ai"
export LLM_API_KEY="your-llm-key"
export LLM_MODEL="gzy/claude-4.6-sonnet"

export VLM_API_BASE=""
export VLM_API_KEY=""
export VLM_MODEL="gzy/gemini-3.1-pro-thinking"

export SEQUENCE_VLM_API_BASE=""
export SEQUENCE_VLM_API_KEY=""
export SEQUENCE_VLM_MODEL="gzy/gemini-3.1-pro-thinking"

export NCBI_EMAIL=""
export NCBI_API_KEY=""
```

If VLM keys or base URLs are unset, image extraction falls back to the text LLM
configuration where supported.

## Single Paper

```bash
cd agent
python main.py /path/to/paper.md -o ../runs/dev/agent_single --trace
```

## Batch Run

```bash
cd agent
python main.py --batch ../dataset -o ../runs/dev/agent --trace
```

Batch mode discovers Markdown files in this order:

1. `<paper>/images_ocr_merged.md`
2. `<paper>/*_enhanced.md`
3. `<paper>/vlm/<paper>.md`
4. `<paper>/<paper>.md`
5. Standalone `.md` files directly under the batch root

## Mock Smoke Test

```bash
cd agent
python main.py --mock-llm ../dataset/Chem\ Sci\ 2020/Chem\ Sci\ 2020.md -o ../runs/dev/mock
```

`--mock-llm` mocks the text LLM path and part of external API fetching. For a
fully offline test, use input without image references or disable image
extraction from Python by setting `config.enable_image_extract = False`.

## Trace Visualization

```bash
cd agent
python main.py --batch ../dataset -o ../runs/dev/agent --trace
python tools/visualize_trace.py ../runs/dev/agent/trace_events.json
```

## Outputs

For each paper, the agent may write:

- `regex_hints.json`
- `ocr_repaired.md`
- `reduced_text.md`
- `reduced_text_report.json`
- `sequence_image_extracted.json`
- `skeleton_v1.json`
- `figure_extracted.json`
- `image_extracted.json`
- `validation_report.json`
- `skeleton_final.json`
- `prediction.json`
- `run_log.json`

Batch mode additionally writes:

- `predictions.json`
- `benchmark_predictions.json`
- `batch_summary.json`

Only generated run directories should contain these artifacts.

## Benchmark Integration

```bash
cd agent
python main.py --batch ../dataset -o ../runs/dev/agent --trace

cd ../benchmark
python run_eval.py \
  --gt ground_truth/ground_truth.json \
  --pred ../runs/dev/agent/benchmark_predictions.json \
  --output ../runs/dev/benchmark
```

## Tests

```bash
cd agent
python -m pytest tests -q
```

The test suite covers batch discovery, prompt skill loading, LLM JSON parsing,
OCR repair, reduction, paper focus, regex scanning, table parsing, sequence
image handling, PDB/GenBank backfill, orchestration, validation, and benchmark
helpers.
