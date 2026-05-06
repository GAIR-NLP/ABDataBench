# Agent Design

This document summarizes the current extraction architecture. Historical design
drafts and obsolete paths were removed so the document reflects the checked-in
implementation.

## Goals

- Convert OCR Markdown into benchmark-compatible antibody records.
- Preserve evidence provenance where possible.
- Keep deterministic tooling for regex, table, sequence, and API enrichment.
- Use LLM calls only for stages that require semantic extraction or review.
- Support single-paper runs, batch runs, and benchmark evaluation.

## Architecture

The orchestrator coordinates a staged pipeline:

```text
Markdown
  -> Scanner
  -> OCR repair
  -> Evidence reduction
  -> Paper focus
  -> Sequence image extraction
  -> Skeleton extraction
  -> Enrichment and merge
  -> Validation
  -> Reviewer retry when needed
  -> Finalize
```

The finalizer writes two views of the result:

- `skeleton_final.json`: detailed internal output for audit and debugging.
- `prediction.json` / `benchmark_predictions.json`: flattened output accepted
  by `benchmark/run_eval.py`.

## Prompt Loading

Prompt assets remain in `agent/prompts/`. Agent classes load them through
`agent/tools/skill_loader.py`, which reads metadata from `agent/skills/*/SKILL.md`.
This makes prompt usage explicit without changing the original prompt text.

## Configuration Precedence

Runtime configuration is assembled from:

1. CLI flags
2. environment variables
3. defaults in `agent/config.py`

API keys and tokens are never hardcoded. Use `.env` locally and keep it out of
version control.

## Data Contracts

The internal skeleton can carry richer fields such as source metadata, evidence
quotes, confidence, and validation diagnostics. Benchmark output is flattened to
the field names expected by `benchmark/ground_truth/ground_truth.json`.

The most important benchmark fields are:

- `Antibody_Name`
- `Target_Name`
- `CDRH3_Sequence`
- `vh_sequence_aa`
- `vl_sequence_aa`
- `Binding_Kinetics_KD`
- `Experiment`
- `Structure`
- `Mechanism_of_Action`
- `Reference_Source`

## Merge Policy

The pipeline merges deterministic and LLM evidence conservatively:

- authoritative API evidence can backfill structure and sequence fields;
- table evidence can fill quantitative and sequence fields when attributable;
- image evidence only fills visible and attributable values;
- OCR text sequence recovery can improve weak image fragments;
- reviewer retries provide correction instructions rather than direct patches.

## Failure Handling

- Scanner and core file-loading failures stop the run.
- Reducer chunk failures keep the original chunk and continue.
- Image extraction failures return empty enrichment instead of blocking the run.
- Skeleton JSON parse failures use defensive parsing and fallback paths where
  available.
- Reviewer failures are surfaced because they indicate an unresolved LLM or
  configuration issue.

## Scaling Notes

Batch throughput is controlled mainly by:

- `--papers-per-worker`
- `--llm-concurrency`
- model rate limits
- PDB/NCBI API limits
- input document size

Generated outputs should be placed under `runs/` so they remain ignored and can
be safely removed or regenerated.
