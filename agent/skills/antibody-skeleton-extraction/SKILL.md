---
name: antibody-skeleton-extraction
description: "Build the primary antibody extraction skeleton from OCR markdown, regex hints, paper focus analysis, and optional sequence-image evidence."
agent: skeleton
system_prompt: ../../prompts/skeleton_system.txt
user_template: ../../prompts/skeleton_user.txt
---

# Antibody Skeleton Extraction Skill

Use this skill when the skeleton agent turns paper evidence into the normalized
antibody JSON schema. The skill keeps the extraction rules in versioned prompt
assets so agent execution receives the same prompt text as the legacy pipeline.
