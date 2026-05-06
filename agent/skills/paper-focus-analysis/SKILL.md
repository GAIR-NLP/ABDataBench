---
name: paper-focus-analysis
description: "Create a short paper-level extraction strategy for hard immunology papers without producing final antibody JSON."
agent: paper_focus
system_prompt: ../../prompts/paper_focus_system.txt
---

# Paper Focus Analysis Skill

Use this skill for hard papers where entity boundaries, comparator/control
records, sequence sources, or split-record decisions need a compact extraction
brief before skeleton generation. It identifies core vs. reference antibodies,
flags record-split scenarios, and recommends evidence priority order.
