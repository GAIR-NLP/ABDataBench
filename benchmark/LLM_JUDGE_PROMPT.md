# Benchmark LLM Judge Prompt

The live benchmark judge prompt is defined in
[`scripts/llm_judge.py`](scripts/llm_judge.py).

Default judge model:

- `gzy/claude-4.6-sonnet`

Evaluation does not send every field directly to the LLM. Empty-value handling,
miss/skip logic, selected numeric fields, selected sequence fields,
`Experiment`, `Antibody_Type`, and `Reference_Source` use deterministic rules
first. The LLM judge is called only when those rules cannot decide.

## System Prompt Summary

The judge is instructed to compare a model prediction against the ground truth
and return one of:

- `exact` with score `1.0`
- `partial` with score `0.5`
- `wrong` with score `0.0`

It is told to compare semantics rather than wording, normalize common unit
differences, treat compatible antibody type descriptions leniently, and score
sequence fields strictly.

## User Prompt Template

```text
Judge the match for this field.

**Field**: {field_name} - {field_description}
**Weight level**: {weight_level}
**Field-specific rule**: {field_guidance}
**Ground truth**: {gt_value}
**Model prediction**: {pred_value}

Return raw JSON only, without code fences:
{"label": "exact"/"partial"/"wrong", "score": 1.0/0.5/0.0, "reason": "one-sentence English explanation"}
```

## Rule-Based Shortcuts Before LLM

- Sequence fields: `CDRH3_Sequence`, `vh_sequence_aa`, `vl_sequence_aa`
- Experiment method field: `Experiment`
- Antibody type field: `Antibody_Type`
- Reference field: `Reference_Source`
- Numeric pre-check fields:
  - `Binding_Kinetics_KD`
  - `Binding_Kinetics_kon`
  - `Binding_Kinetics_koff`
  - `Binding_EC50`
  - `Thermal_Stability_Tm`

## Code Entry Points

- Evaluation entry: [`run_eval.py`](run_eval.py)
- Judge implementation: [`scripts/llm_judge.py`](scripts/llm_judge.py)
- Field scoring flow: [`scripts/evaluator.py`](scripts/evaluator.py)
