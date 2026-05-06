---
name: reviewer-qa
description: "Review validation failures and high-priority warnings, then produce field-level correction instructions."
agent: reviewer
system_prompt: ../../prompts/reviewer_system.txt
---

# Reviewer QA Skill

Use this skill after bio-validation. It compares the skeleton JSON against the
validation report, identifies root causes of all fail/warn items, and generates
concrete field-level correction instructions without inventing data. It focuses
on evidence broadcasting errors, sequence validity, entity boundaries, and
field format compliance.
