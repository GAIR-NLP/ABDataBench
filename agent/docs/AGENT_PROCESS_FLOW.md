# Agent Process Flow

This document describes the runtime flow for the checked-in agent.

## 1. Input Discovery

Single-paper mode accepts one Markdown file. Batch mode scans each direct child
directory and chooses the best Markdown candidate in this order:

1. `images_ocr_merged.md`
2. `*_enhanced.md`
3. `vlm/<paper>.md`
4. `<paper>.md`
5. standalone Markdown files under the batch root

## 2. Scan

`ScannerAgent` extracts deterministic regex hints such as antibody names,
sequence-like strings, accession IDs, PDB IDs, and quantitative clues. These
hints are passed to later stages as supporting evidence.

## 3. OCR Repair

`OCRRepairAgent` can repair broken Markdown tables, wrapped rows, and OCR
formatting issues. It is conservative: scientific tokens, numeric values,
sequences, accessions, and residue identifiers must be preserved.

## 4. Evidence Reduction

`ReducerAgent` chunks long Markdown files and keeps evidence relevant to
antibody extraction. It avoids summarizing scientific content because downstream
agents need source-like text.

## 5. Paper Focus

`PaperFocusAgent` creates a short extraction strategy for hard papers. It helps
separate primary antibodies from controls, comparators, public clonotypes, and
reference-only mentions.

## 6. Sequence Image Extraction

The sequence image tool inspects alignment or sequence-block images when OCR
text alone is insufficient. It returns visible heavy-chain, light-chain, and
CDRH3 evidence only when attributable.

## 7. Skeleton Extraction

`SkeletonAgent` builds the primary normalized antibody records. Long outputs can
be paginated so each LLM response stays parseable.

## 8. Enrichment

The orchestrator merges additional evidence from:

- PDB and NCBI lookup
- deterministic table parsing
- OCR text sequence recovery
- targeted figure/image extraction

Merge rules prefer attributable, authoritative, and complete evidence over weak
or partial fragments.

## 9. Validation and Review

`ValidatorAgent` checks biological plausibility and schema constraints. If
high-priority failures remain, `ReviewerAgent` returns correction instructions.
The orchestrator can rerun skeleton extraction with those instructions up to the
configured retry limit.

## 10. Finalization

Finalization removes internal-only fields and writes:

- `skeleton_final.json`
- `prediction.json`
- `run_log.json`

Batch mode also writes `predictions.json`, `benchmark_predictions.json`, and
`batch_summary.json`.
