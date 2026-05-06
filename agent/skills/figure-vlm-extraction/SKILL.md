---
name: figure-vlm-extraction
description: "Triage paper figures and extract antibody sequence, kinetics, quantitative table, and efficacy evidence from relevant images."
agent: image_extract
triage_prompt: ../../prompts/vlm_triage_system.txt
extract_prompt: ../../prompts/vlm_extract_system.txt
---

# Figure VLM Extraction Skill

Use this skill for targeted VLM image supplementation when structured extraction
leaves sequence, kinetics, quantitative, or efficacy gaps. It first triages each
figure into a relevance category, then extracts antibody-level data from relevant
images only.
