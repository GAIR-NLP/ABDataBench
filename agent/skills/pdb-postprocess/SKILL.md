---
name: pdb-postprocess
description: "Normalize PDB lookup summaries into mergeable antibody structure and sequence backfill fields."
agent: api_fetch
system_prompt: ../../prompts/pdb_postprocess_system.txt
user_template: ../../prompts/pdb_postprocess_user.txt
---

# PDB Postprocess Skill

Use this skill after external PDB lookup. It maps candidate structures and
heuristic FASTA evidence back to the current antibody entry without adding
unsupported chains, tags, linkers, or antigen sequences.
