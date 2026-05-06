---
name: ocr-format-repair
description: "Conservatively repair OCR-derived markdown formatting while preserving every scientific token."
agent: ocr_repair
system_prompt: ../../prompts/ocr_repair_system.txt
user_template: ../../prompts/ocr_repair_user.txt
---

# OCR Format Repair Skill

Use this skill before extraction when OCR markdown may contain broken table rows,
headers, wrappers, or line breaks. It is intentionally conservative and must not
change numeric values, sequences, residue identifiers, accessions, PDB IDs, or
scientific wording.
