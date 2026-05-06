---
name: evidence-reduction
description: "Filter long OCR markdown chunks to preserve antibody, sequence, structure, image, table, and quantitative evidence for downstream extraction."
agent: reducer
system_prompt: ../../prompts/reducer_system.txt
user_template: ../../prompts/reducer_user.txt
---

# Evidence Reduction Skill

Use this skill before skeleton extraction on long documents. It keeps original
evidence snippets and removes low-value sections without summarizing or
rewriting scientific content.
