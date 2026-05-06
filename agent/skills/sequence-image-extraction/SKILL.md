---
name: sequence-image-extraction
description: "Read antibody heavy/light chain and CDRH3 sequences from sequence alignment or sequence block images."
agent: sequence_image_extract
system_prompt: ../../prompts/sequence_image_extract_system.txt
---

# Sequence Image Extraction Skill

Use this skill for image-only sequence evidence. It transcribes visible amino
acid characters from alignment figures or sequence block images, handles
alignment-reference rows conservatively, and keeps partial or unassigned
fragments out of full VH/VL fields.
