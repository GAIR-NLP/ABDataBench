---
name: reviewer-qa
description: "Review validation failures and high-priority warnings, then produce field-level correction instructions."
agent: reviewer
system_prompt: ../../prompts/reviewer_system.txt
---

# Reviewer QA Skill

Use this skill after bio-validation. It focuses on failures, high-priority
warnings, field boundaries, sequence validity, and evidence broadcasting errors
without inventing data.
