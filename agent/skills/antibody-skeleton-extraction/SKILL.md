---
name: antibody-skeleton-extraction
description: "Build the primary antibody extraction skeleton from OCR markdown, regex hints, paper focus analysis, and optional sequence-image evidence."
agent: skeleton
system_prompt: ../../prompts/skeleton_system.txt
user_template: ../../prompts/skeleton_user.txt
---

# Antibody Skeleton Extraction Skill

Use this skill when the skeleton agent turns paper evidence into the normalized
antibody JSON schema. This is the core extraction stage of the pipeline. It
applies evidence-unit-first logic, strict inclusion/exclusion rules, and
anti-hallucination guards to produce structured antibody records from immunology
literature.
