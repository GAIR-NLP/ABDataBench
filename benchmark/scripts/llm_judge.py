#!/usr/bin/env python3
"""
LLM-as-judge scoring module v3.

The module combines deterministic shortcuts with an LLM judge. The LLM prompt is
aware of the 22 benchmark fields and their weight levels.
"""

import os
import json
import time
import re
import threading
from typing import List, Optional
from openai import OpenAI


DEFAULT_MODEL = "gzy/claude-4.6-sonnet"
DEFAULT_BASE_URL = "https://api.opensii.ai"

JUDGE_SYSTEM_PROMPT = """You are a biomedical information extraction quality evaluator.

Your task is to compare the model prediction with the ground truth and assign a
field-level score.

## Labels

**exact (1.0)**: semantically consistent and scientifically correct. Use exact
when:
- synonymous expressions have the same meaning, such as "mAb" and "monoclonal antibody";
- the prediction is more detailed than the ground truth but preserves the same core fact;
- the prediction is shorter but still preserves the core fact;
- numeric wording differs but the value is equivalent, such as "6.91nM" and "KD ~= 6.91 nM";
- empty markers such as "n.d.", "N/A", "ND", "None", "-", and "" are equivalent;
- the core germline gene segment is the same, such as "IGHV1-3*01" and "IGHV1-3";
- a sequence fully contains the expected core sequence.

**partial (0.5)**: partly correct, with the right direction but important
missing or shifted detail. Examples include partial numeric coverage, a correct
mechanism missing key detail, or a reference missing author or article details.

**wrong (0.0)**: contradictory or unrelated information, such as a different
gene, sequence, target, epitope, mechanism, or value off by orders of magnitude.

## Field Weights

Field importance differs:
- **Core fields (2.0)**: CDRH3_Sequence, vh_sequence_aa, vl_sequence_aa, and
  Binding_Kinetics_KD. Be strict, especially for sequences.
- **Standard fields (1.0)**: Target_Name, Epitope, Antibody_Type,
  Mechanism_of_Action, Experiment, Binding_Kinetics_kon,
  Binding_Kinetics_koff, Binding_EC50, and Structure.
- **Auxiliary fields (0.5)**: source, Reference_Source, Target_Type,
  Antibody_Isotype, Cross_Reactivity, Quantitative_Metric,
  In_Vivo_Half_Life, In_Vivo_Efficacy, and Thermal_Stability_Tm.

## Binding Kinetics

- Normalize concentration units for KD and EC50: pM, nM, uM, and M.
- Numeric difference <=10% is exact, <=3x is partial, and >3x is wrong.
- Apply the same numeric thresholds to kon, koff, and Tm when comparable.

## Structure

Structure text may include method, resolution, and PDB ID. Same method with a
similar resolution is exact. Correct method but missing or different PDB detail
is partial.

## Cross_Reactivity

Species and variant coverage matter. Broadly compatible statements may be
partial when the prediction omits specific species or variants.

## Important Notes

1. Compare semantics, not wording or language.
2. A prediction being more detailed than the ground truth is usually not a
   penalty when the core fact is correct.
3. Epitope descriptions can be exact when they refer to the same region, domain,
   groove, motif, or key residue set at a different detail level.
4. For information extraction, give high scores when the scientifically
   important fact is correct.

## Lenient Defaults for Selected Fields

- **Target_Name**: if the core target matches, missing or extra clade, subtype,
  strain, lineage, or variant qualifiers can still be exact.
- **Epitope**: descriptions of the same binding region, groove, domain, motif,
  or core residue set can be exact even at different detail levels.
- **Antibody_Type**: compatible coarse and specific types can be exact, such as
  "IgG" and "Monoclonal IgG1".
- **Experiment**: if the prediction covers the ground-truth methods and extra
  methods are still direct readout, kinetics, or binding measurements, exact is
  acceptable. Peripheral methods such as Western blot, crystallography,
  challenge models, sorting, gating, or sequencing should reduce to partial.
- **Mechanism_of_Action**: if the prediction includes a core mechanism from the
  ground truth, extra compatible mechanisms usually do not penalize it unless
  the prediction contradicts or omits the ground-truth mechanism."""

JUDGE_USER_TEMPLATE = """Judge the match for this field.

**Field**: {field_name} - {field_description}
**Weight level**: {weight_level}
**Field-specific rule**: {field_guidance}
**Ground truth**: {gt_value}
**Model prediction**: {pred_value}

Return raw JSON only, without code fences:
{{"label": "exact"/"partial"/"wrong", "score": 1.0/0.5/0.0, "reason": "one-sentence English explanation"}}"""

FIELD_DESCRIPTIONS = {
    "Antibody_Type": "antibody format or type, such as IgG, IgG1, IgG4, VHH, scFv-Fc, or mAb",
    "Antibody_Isotype": "antibody isotype, such as IgG1, IgG2, IgG4, IgA, or IgM",
    "Target_Name": "target name, such as SARS-CoV-2 Spike, RBD, or PD-L1",
    "Target_Type": "target type, such as viral spike protein, receptor, or cytokine",
    "Epitope": "epitope description, binding site, or key residues",
    "Experiment": "experimental method list, such as SPR, ELISA, or Cryo-EM",
    "Binding_Kinetics_KD": "dissociation constant KD, such as 6.91 nM or 45 pM",
    "Binding_Kinetics_kon": "association rate constant kon, usually in scientific notation",
    "Binding_Kinetics_koff": "dissociation rate constant koff, usually in scientific notation",
    "Binding_EC50": "half-maximal effective concentration EC50",
    "Mechanism_of_Action": "mechanism of action, such as neutralization, receptor blocking, or ADCC",
    "Quantitative_Metric": "quantitative metric, such as IC50, IC90, or neutralization titer",
    "Structure": "structure information, such as Cryo-EM 3.2 A, X-ray crystal structure, or PDB ID",
    "CDRH3_Sequence": "CDR-H3 amino-acid sequence or related information",
    "vh_sequence_aa": "heavy-chain sequence or germline gene information",
    "vl_sequence_aa": "light-chain sequence or germline gene information",
    "Cross_Reactivity": "cross-reactivity, such as cross-species binding or variant neutralization",
    "Thermal_Stability_Tm": "thermal stability Tm value",
    "In_Vivo_Half_Life": "in-vivo half-life value",
    "In_Vivo_Efficacy": "in-vivo efficacy data, such as protection rate or viral-load reduction",
    "source": "antibody source species or derivation method",
    "Reference_Source": "reference source, such as author, year, and journal",
}

FIELD_WEIGHT_LEVELS = {
    "CDRH3_Sequence": "Core (2.0) - sequence field, score strictly",
    "vh_sequence_aa": "Core (2.0) - sequence field, score strictly",
    "vl_sequence_aa": "Core (2.0) - sequence field, score strictly",
    "Binding_Kinetics_KD": "Core (2.0) - dissociation constant, score strictly",
    "Target_Name": "Standard (1.0)",
    "Epitope": "Standard (1.0)",
    "Antibody_Type": "Standard (1.0)",
    "Mechanism_of_Action": "Standard (1.0)",
    "Experiment": "Standard (1.0)",
    "Binding_Kinetics_kon": "Standard (1.0) - association rate constant",
    "Binding_Kinetics_koff": "Standard (1.0) - dissociation rate constant",
    "Binding_EC50": "Standard (1.0) - half-maximal effective concentration",
    "Structure": "Standard (1.0) - structure information",
    "source": "Auxiliary (0.5) - allow broader wording",
    "Reference_Source": "Auxiliary (0.5) - allow broader wording",
    "Target_Type": "Auxiliary (0.5) - allow broader wording",
    "Antibody_Isotype": "Auxiliary (0.5) - allow broader wording",
    "Cross_Reactivity": "Auxiliary (0.5) - allow broader wording",
    "Quantitative_Metric": "Auxiliary (0.5) - allow broader wording",
    "In_Vivo_Half_Life": "Auxiliary (0.5) - allow broader wording",
    "In_Vivo_Efficacy": "Auxiliary (0.5) - allow broader wording",
    "Thermal_Stability_Tm": "Auxiliary (0.5) - allow broader wording",
}
SEQUENCE_FIELDS = {"CDRH3_Sequence", "vh_sequence_aa", "vl_sequence_aa"}
AA_ALPHABET = set("ACDEFGHIKLMNPQRSTVWYX")
EMPTY_EQUIVALENTS = {"", "n/a", "na", "nd", "n.d.", "none", "-", "not reported", "未报道", "未提供"}

FIELD_SPECIAL_GUIDANCE = {
    "Target_Name": "If the core target matches, missing or extra clade/subtype/strain/lineage/variant qualifiers can still be exact.",
    "Epitope": "If both values describe the same binding region, groove, domain, motif, or core residue set, different detail levels can still be exact.",
    "Antibody_Type": "If coarse and specific types are compatible, such as IgG vs Monoclonal IgG1 or mAb vs monoclonal antibody, exact is acceptable.",
    "Mechanism_of_Action": "If the prediction includes any core mechanism from the ground truth, compatible extra mechanisms usually do not penalize it.",
    "Experiment": "If the prediction covers the ground-truth method and extra methods are direct binding/readout/kinetics methods, exact is acceptable; peripheral methods such as Western blot should reduce to partial.",
    "Reference_Source": "If DOI matches, or author/year/journal core information matches with formatting differences only, exact is acceptable.",
}

DIRECT_EXPERIMENT_METHODS = {
    "elisa", "itc", "spr", "bli", "flowcytometry", "facs", "neutralizationassay",
    "microneutralizationassay", "pseudovirusneutralization", "livevirusneutralization",
    "beacon", "biolayerinterferometry", "surfaceplasmonresonance", "ilsda",
}
PERIPHERAL_EXPERIMENT_METHODS = {
    "westernblot", "wb", "xray", "xraycrystallography", "cryoem", "cryoelectronmicroscopy",
    "crystallography", "sequencing", "vdjsequencing", "bcellsorting", "sorting", "gating",
    "expressionqc", "mousemodel", "invivomousemodel", "challenge", "mosquitobitechallenge",
    "lcms", "massspectrometry", "immunoprecipitation", "trailglidingassay", "glidingassay",
}
EXPERIMENT_CANONICAL_PATTERNS = (
    (r"\bflow cytometry\b|\bfacs\b", "flowcytometry"),
    (r"\belisa\b", "elisa"),
    (r"\bitc\b|isothermal titration calorimetry", "itc"),
    (r"\bbli\b|biolayer interferometry", "bli"),
    (r"\bspr\b|surface plasmon resonance", "spr"),
    (r"microneutralization", "microneutralizationassay"),
    (r"neutralization", "neutralizationassay"),
    (r"\bbeacon\b", "beacon"),
    (r"\bilsda\b", "ilsda"),
    (r"western blot|\bwb\b", "westernblot"),
    (r"x-ray|xray|crystallography", "xraycrystallography"),
    (r"cryo-?em|cryo electron microscopy", "cryoem"),
    (r"sorting", "sorting"),
    (r"gating", "gating"),
    (r"sequencing", "sequencing"),
    (r"challenge", "challenge"),
    (r"mouse model|in vivo", "mousemodel"),
    (r"lc-?ms|mass spectrometry", "lcms"),
    (r"immunoprecipitation", "immunoprecipitation"),
    (r"gliding assay|trail-gliding assay", "glidingassay"),
)
ANTIBODY_TYPE_PATTERNS = (
    (r"\bbispecific\b", "bispecific"),
    (r"\bvhh\b|nanobody", "vhh"),
    (r"\bscfv\b", "scfv"),
    (r"\bfab\b", "fab"),
    (r"\biga\b", "iga"),
    (r"\bigm\b", "igm"),
    (r"\bige\b", "ige"),
    (r"\bigd\b", "igd"),
    (r"\bigg(?:[1-4])?\b", "igg"),
    (r"monoclonal antibody|\bmab\b", "mab"),
)


def extract_json_object(text: str) -> dict:
    """Parse a JSON object from raw model text, tolerating explanation text around it."""
    if text is None:
        raise json.JSONDecodeError("empty content", "", 0)

    content = text.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[-1]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    last_good: Optional[dict] = None
    for idx, ch in enumerate(content):
        if ch != "{":
            continue
        try:
            candidate, end = decoder.raw_decode(content[idx:])
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict):
            trailing = content[idx + end :].strip()
            if not trailing:
                return candidate
            last_good = candidate
    if last_good is not None:
        return last_good
    raise json.JSONDecodeError("no JSON object found", content, 0)



class LLMJudge:
    def __init__(self, api_key=None, base_url=None, model=None,
                 max_retries=3, requests_per_minute=120):
        self.api_key = api_key or os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
        self.base_url = base_url or os.environ.get("ANTHROPIC_BASE_URL", DEFAULT_BASE_URL)
        self.model = model or DEFAULT_MODEL
        self.max_retries = max_retries
        self.min_interval = 60.0 / requests_per_minute
        self.last_request_time = 0
        self.call_count = 0
        self.cache = {}

        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        self.cache_hit = 0

        # Thread-safety locks.
        self._cache_lock = threading.Lock()
        self._rate_lock = threading.Lock()
        self._stats_lock = threading.Lock()

    def _rate_limit(self):
        with self._rate_lock:
            elapsed = time.time() - self.last_request_time
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            self.last_request_time = time.time()

    @staticmethod
    def _normalize_empty(value) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @classmethod
    def _is_empty_value(cls, value) -> bool:
        return cls._normalize_empty(value).lower() in EMPTY_EQUIVALENTS

    @staticmethod
    def _normalize_sequence_text(value: str) -> str:
        return re.sub(r"[^A-Z]", "", value.upper())

    @staticmethod
    def _normalize_free_text(value) -> str:
        if value is None:
            return ""
        return str(value).strip().lower()

    @staticmethod
    def _normalize_compact_text(value) -> str:
        return re.sub(r"[^a-z0-9]+", "", LLMJudge._normalize_free_text(value))

    @classmethod
    def _looks_like_aa_sequence(cls, value: str) -> bool:
        compact = re.sub(r"\s+", "", value).upper()
        if not compact:
            return False
        if any(ch not in AA_ALPHABET and ch not in {"-", "."} for ch in compact):
            return False
        letters = compact.replace("-", "").replace(".", "")
        return len(letters) >= 8 and set(letters) <= AA_ALPHABET

    @staticmethod
    def _levenshtein_distance(a: str, b: str) -> int:
        if a == b:
            return 0
        if not a:
            return len(b)
        if not b:
            return len(a)
        if len(a) < len(b):
            a, b = b, a
        previous = list(range(len(b) + 1))
        for i, ca in enumerate(a, start=1):
            current = [i]
            for j, cb in enumerate(b, start=1):
                insert_cost = current[j - 1] + 1
                delete_cost = previous[j] + 1
                replace_cost = previous[j - 1] + (ca != cb)
                current.append(min(insert_cost, delete_cost, replace_cost))
            previous = current
        return previous[-1]

    @classmethod
    def _rule_based_sequence_score(cls, field_name: str, gt_value: str, pred_value: str) -> Optional[dict]:
        if field_name not in SEQUENCE_FIELDS:
            return None

        gt_text = cls._normalize_empty(gt_value)
        pred_text = cls._normalize_empty(pred_value)

        if cls._is_empty_value(gt_text) and cls._is_empty_value(pred_text):
            return {"label": "exact", "score": 1.0, "reason": "Both sequence values are empty"}
        if cls._is_empty_value(gt_text):
            return {"label": "wrong", "score": 0.0, "reason": "Ground truth is empty but the model output a sequence"}
        if cls._is_empty_value(pred_text):
            return {"label": "wrong", "score": 0.0, "reason": "Ground truth has a sequence but the model did not output one"}

        if not (cls._looks_like_aa_sequence(gt_text) and cls._looks_like_aa_sequence(pred_text)):
            return None

        gt_seq = cls._normalize_sequence_text(gt_text)
        pred_seq = cls._normalize_sequence_text(pred_text)
        if gt_seq == pred_seq:
            return {"label": "exact", "score": 1.0, "reason": "Rule-based sequence match: exact sequence identity"}
        if gt_seq in pred_seq or pred_seq in gt_seq:
            return {"label": "exact", "score": 1.0, "reason": "Rule-based sequence match: one sequence fully contains the other"}

        dist = cls._levenshtein_distance(gt_seq, pred_seq)
        max_len = max(len(gt_seq), len(pred_seq), 1)
        diff_ratio = dist / max_len
        if diff_ratio <= 0.10:
            return {
                "label": "partial",
                "score": 0.5,
                "reason": f"Rule-based sequence match: highly similar with local differences (edit distance {dist}/{max_len})",
            }
        return {
            "label": "wrong",
            "score": 0.0,
            "reason": f"Rule-based sequence mismatch: large sequence difference (edit distance {dist}/{max_len})",
        }

    @classmethod
    def _extract_experiment_methods(cls, value: str) -> set[str]:
        text = cls._normalize_free_text(value)
        methods = set()
        for pattern, canonical in EXPERIMENT_CANONICAL_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                methods.add(canonical)
        if methods:
            return methods
        fallback = set()
        for part in re.split(r"[,;/，；、\n]+", text):
            token = cls._normalize_compact_text(part)
            if token:
                fallback.add(token)
        return fallback

    @classmethod
    def _rule_based_experiment_score(cls, gt_value: str, pred_value: str) -> Optional[dict]:
        gt_methods = cls._extract_experiment_methods(gt_value)
        pred_methods = cls._extract_experiment_methods(pred_value)
        if not gt_methods or not pred_methods:
            return None

        missing = gt_methods - pred_methods
        overlap = gt_methods & pred_methods
        extra = pred_methods - gt_methods
        peripheral_extra = {method for method in extra if method in PERIPHERAL_EXPERIMENT_METHODS}
        direct_extra = {method for method in extra if method in DIRECT_EXPERIMENT_METHODS}

        if not missing and not extra:
            return {"label": "exact", "score": 1.0, "reason": "Rule-based experiment match: method sets are identical"}
        if not missing and peripheral_extra:
            return {
                "label": "partial",
                "score": 0.5,
                "reason": "Rule-based experiment partial: ground-truth methods are covered but peripheral methods were added",
            }
        if not missing and extra and extra == direct_extra:
            return {
                "label": "exact",
                "score": 1.0,
                "reason": "Rule-based experiment match: ground-truth methods are covered and extra methods are direct readout/kinetics methods",
            }
        if overlap:
            return {"label": "partial", "score": 0.5, "reason": "Rule-based experiment partial: method sets overlap"}
        return {"label": "wrong", "score": 0.0, "reason": "Rule-based experiment mismatch"}

    @classmethod
    def _extract_antibody_type_tags(cls, value: str) -> set[str]:
        text = cls._normalize_free_text(value)
        tags = set()
        for pattern, tag in ANTIBODY_TYPE_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                tags.add(tag)
        return tags

    @classmethod
    def _rule_based_antibody_type_score(cls, gt_value: str, pred_value: str) -> Optional[dict]:
        gt_tags = cls._extract_antibody_type_tags(gt_value)
        pred_tags = cls._extract_antibody_type_tags(pred_value)
        if not gt_tags or not pred_tags:
            return None
        if gt_tags == pred_tags:
            return {"label": "exact", "score": 1.0, "reason": "Rule-based antibody type match: tags are identical"}
        if "igg" in gt_tags and "igg" in pred_tags:
            return {"label": "exact", "score": 1.0, "reason": "Rule-based antibody type match: both belong to the IgG family"}
        if gt_tags & pred_tags:
            return {"label": "exact", "score": 1.0, "reason": "Rule-based antibody type match: compatible type tags overlap"}
        if gt_tags <= {"mab"} and pred_tags <= {"mab", "igg"}:
            return {"label": "exact", "score": 1.0, "reason": "Rule-based antibody type match: monoclonal antibody and mAb/IgG are compatible"}
        return {"label": "wrong", "score": 0.0, "reason": "Rule-based antibody type mismatch"}

    @staticmethod
    def _extract_doi(value: str) -> str:
        match = re.search(r"(10\.\d{4,9}/[-._;()/:A-Z0-9]+)", str(value or ""), re.IGNORECASE)
        return match.group(1).lower().rstrip(".,;)") if match else ""

    @staticmethod
    def _extract_year(value: str) -> str:
        match = re.search(r"\b(19|20)\d{2}\b", str(value or ""))
        return match.group(0) if match else ""

    @staticmethod
    def _extract_first_author(value: str) -> str:
        text = str(value or "")
        match = re.search(r"\(([A-Za-z][A-Za-z'`\- ]+?)\s+et al\.?\)", text, re.IGNORECASE)
        if match:
            author = match.group(1).strip().split()[-1]
            return re.sub(r"[^a-z]", "", author.lower())
        match = re.search(r"\b([A-Z][A-Za-z'`\-]+)\s+et al\.?\b", text)
        if match:
            return re.sub(r"[^a-z]", "", match.group(1).lower())
        return ""

    @classmethod
    def _extract_journal_token(cls, value: str) -> str:
        text = cls._normalize_free_text(value)
        if not text:
            return ""
        text = re.sub(r"\([^)]*\)", " ", text)
        text = re.sub(r"doi\s*:?.*$", " ", text).strip()
        year = cls._extract_year(text)
        if year:
            text = text.replace(year, " ")
        text = re.sub(r"\bet al\.?\b", " ", text)
        text = re.sub(r"[^a-z0-9. ]+", " ", text)
        tokens = [token for token in text.split() if token not in {"and"}]
        return "".join(tokens[:4])

    @classmethod
    def _rule_based_reference_source_score(cls, gt_value: str, pred_value: str) -> Optional[dict]:
        gt_doi = cls._extract_doi(gt_value)
        pred_doi = cls._extract_doi(pred_value)
        if gt_doi and pred_doi and gt_doi == pred_doi:
            return {"label": "exact", "score": 1.0, "reason": "Rule-based reference match: DOI is identical"}

        gt_author = cls._extract_first_author(gt_value)
        pred_author = cls._extract_first_author(pred_value)
        gt_year = cls._extract_year(gt_value)
        pred_year = cls._extract_year(pred_value)
        gt_journal = cls._extract_journal_token(gt_value)
        pred_journal = cls._extract_journal_token(pred_value)

        if gt_author and pred_author and gt_year and pred_year and gt_author == pred_author and gt_year == pred_year:
            if gt_doi and pred_doi and gt_doi != pred_doi:
                return {"label": "partial", "score": 0.5, "reason": "Rule-based reference partial: author and year match but DOI conflicts"}
            if gt_journal and pred_journal and (gt_journal in pred_journal or pred_journal in gt_journal):
                return {"label": "exact", "score": 1.0, "reason": "Rule-based reference match: author, year, and journal match"}
            if gt_doi or pred_doi:
                return {"label": "exact", "score": 1.0, "reason": "Rule-based reference match: author and year match and one side provides DOI"}
            return {"label": "partial", "score": 0.5, "reason": "Rule-based reference partial: author and year match but journal or title is incomplete"}
        return None

    @classmethod
    def _rule_based_field_score(cls, field_name: str, gt_value: str, pred_value: str) -> Optional[dict]:
        sequence_result = cls._rule_based_sequence_score(field_name, gt_value, pred_value)
        if sequence_result is not None:
            return sequence_result
        if field_name == "Experiment":
            return cls._rule_based_experiment_score(gt_value, pred_value)
        if field_name == "Antibody_Type":
            return cls._rule_based_antibody_type_score(gt_value, pred_value)
        if field_name == "Reference_Source":
            return cls._rule_based_reference_source_score(gt_value, pred_value)
        return None

    def judge_field(self, field_name: str, gt_value: str, pred_value: str) -> dict:
        """Judge a single field with thread-safe cache and rate limiting."""
        # Include the model name in the cache key to avoid cross-model reuse.
        cache_key = f"{self.model}||{field_name}||{gt_value}||{pred_value}"

        rule_result = self._rule_based_field_score(field_name, gt_value, pred_value)
        if rule_result is not None:
            with self._cache_lock:
                self.cache[cache_key] = rule_result
            return rule_result

        with self._cache_lock:
            if cache_key in self.cache:
                self.cache_hit += 1
                return self.cache[cache_key]

        weight_level = FIELD_WEIGHT_LEVELS.get(field_name, "Standard (1.0)")
        field_guidance = FIELD_SPECIAL_GUIDANCE.get(
            field_name,
            "Use the general rule: assign a high score when the core semantics match.",
        )

        user_msg = JUDGE_USER_TEMPLATE.format(
            field_name=field_name,
            field_description=FIELD_DESCRIPTIONS.get(field_name, field_name),
            weight_level=weight_level,
            field_guidance=field_guidance,
            gt_value=gt_value,
            pred_value=pred_value,
        )

        for attempt in range(self.max_retries):
            try:
                self._rate_limit()

                # Build request parameters and disable reasoning/thinking where supported.
                create_kwargs = dict(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                        {"role": "user", "content": user_msg},
                    ],
                    temperature=0.0,
                    max_tokens=1024,
                )

                # Disable reasoning/thinking for provider-specific model families where supported.
                model_lower = self.model.lower()
                if "gemini" in model_lower:
                    # Gemini: disable thinking through extra_body.
                    create_kwargs["extra_body"] = {
                        "reasoning_effort": "none",
                    }
                elif "gpt" in model_lower or "openai" in model_lower:
                    # OpenAI: temperature=0 is enough for non-o-series models.
                    # o-series models can be controlled through reasoning_effort when needed.
                    pass
                elif "claude" in model_lower:
                    # Claude: no extra handling is needed here.
                    pass

                resp = self.client.chat.completions.create(**create_kwargs)
                with self._stats_lock:
                    self.call_count += 1
                content = resp.choices[0].message.content
                if not content:
                    # Some models may put generated text in reasoning rather than content.
                    if attempt < self.max_retries - 1:
                        time.sleep(1)
                        continue
                    return {"label": "wrong", "score": 0.0, "reason": "LLM returned empty content"}
                result = extract_json_object(content)

                # Validate and force score mapping.
                if result.get("label") not in ("exact", "partial", "wrong"):
                    result["label"] = "wrong"
                score_map = {"exact": 1.0, "partial": 0.5, "wrong": 0.0}
                result["score"] = score_map.get(result["label"], 0.0)
                result.setdefault("reason", "LLM judgment")

                with self._cache_lock:
                    self.cache[cache_key] = result
                return result

            except json.JSONDecodeError:
                if attempt < self.max_retries - 1:
                    time.sleep(1)
                    continue
                return {"label": "wrong", "score": 0.0, "reason": "LLM returned invalid JSON"}
            except Exception as e:
                if attempt < self.max_retries - 1:
                    print(f"    LLM retry ({attempt+1}): {str(e)[:60]}")
                    time.sleep(2 ** attempt)
                    continue
                return {"label": "wrong", "score": 0.0, "reason": f"API error: {str(e)[:40]}"}

    def save_cache(self, path):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.cache, f, ensure_ascii=False, indent=2)

    def load_cache(self, path):
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                self.cache = json.load(f)
            print(f"  Loaded judge cache entries: {len(self.cache)}")
