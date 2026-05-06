# OCR Pipeline Notes

The current OCR utilities provide a reproducible merged workflow:

1. Read raw files from the top level of a paper directory.
2. Run MinerU OCR once for each supported file.
3. Merge generated Markdown into `<paper>.md`.
4. Collect extracted images into `images/`.

Main scripts:

- `scripts/run_paper_ocr_merged.py`: one paper.
- `scripts/batch_paper_ocr_merged.py`: many papers.
- `pipeline/run_two_stage_ocr_merged.sh`: one-paper shell wrapper.
- `pipeline/run_batch_papers_ocr_merged.sh`: batch shell wrapper.

All credentials must be supplied through CLI arguments or environment
variables. OCR outputs are generated artifacts and should not be committed.
