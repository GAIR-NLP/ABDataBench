"""Heuristic paper-focus analysis for per-paper extraction guidance."""

from __future__ import annotations

import re


class PaperFocusBuilder:
    SUPPLEMENT_PATTERNS = (
        r"\bsupp(?:lementary|lemental)?\b",
        r"\bextended data\b",
        r"\bsupp table\b",
        r"\bsupp fig(?:ure)?\b",
    )
    STRUCTURE_PATTERNS = (
        r"\bcryo-?em\b",
        r"\bx-?ray\b",
        r"\bcrystal structure\b",
        r"\bstructure of\b",
        r"\bstructural basis\b",
        r"\bcomplex\b",
    )
    LINEAGE_PATTERNS = (
        r"\blineage\b",
        r"\bgermline\b",
        r"\bmrca\b",
        r"\bunmutated common ancestor\b",
        r"\bpublic clonotype\b",
        r"\bclonal family\b",
        r"\brevert(?:ed|ant)\b",
    )
    MULTI_TARGET_PATTERNS = (
        r"\bcross-?react",
        r"\bbroadly neutralizing\b",
        r"\bbreadth\b",
        r"\bpanel of\b",
        r"\bmultiple targets?\b",
        r"\bbispecific\b",
        r"\bdual[- ]target\b",
        r"\bcocktail\b",
    )
    CONTROL_PATTERNS = (
        r"\bcontrol\b",
        r"\bbenchmark\b",
        r"\bcomparator\b",
        r"\breference antibody\b",
        r"\bpreviously described\b",
        r"\bpreviously published\b",
        r"\bused as control\b",
    )
    ENGINEERING_PATTERNS = (
        r"\bmutant\b",
        r"\bchimera\b",
        r"\bchimeric\b",
        r"\bswap(?:ped|ping)?\b",
        r"\breversion\b",
        r"\bengineered\b",
        r"\bvariant\b",
    )
    KINETICS_PATTERNS = (
        r"\bkd\b",
        r"\bkon\b",
        r"\bkoff\b",
        r"\bec50\b",
        r"\bic50\b",
        r"\bic90\b",
        r"\bnt50\b",
        r"\bfrnt50\b",
        r"\bauc\b",
    )
    EPITOPE_PATTERNS = (
        r"\bepitope\b",
        r"\bmotif\b",
        r"\bdomain\b",
        r"\bsite\b",
        r"\bloop\b",
        r"\bpatch\b",
        r"\bcompetition\b",
        r"\bbin\b",
    )
    IN_VIVO_PATTERNS = (
        r"\bin vivo\b",
        r"\bmouse\b",
        r"\bmice\b",
        r"\bhamster\b",
        r"\bchallenge\b",
        r"\bsurvival\b",
        r"\bviral load\b",
        r"\bprotection\b",
        r"\bhalf-life\b",
        r"\bpk\b",
    )
    POSITIVE_NAME_PATTERNS = (
        r"\bisolated\b",
        r"\bidentified\b",
        r"\bcharacterized\b",
        r"\bwe (?:found|identified|isolated|characterized)\b",
        r"\bpotent\b",
        r"\bneutraliz",
        r"\bbind(?:ing)?\b",
        r"\baffinity\b",
        r"\bepitope\b",
        r"\bsequence\b",
        r"\bvh\b",
        r"\bvl\b",
        r"\bcdrh3\b",
    )
    NAME_CONTEXT_PATTERNS = (
        r"\bantibody\b",
        r"\bmab\b",
        r"\bmonoclonal\b",
        r"\bclone\b",
        r"\bbnab\b",
        r"\bigg\b",
    )
    NEGATIVE_NAME_PATTERNS = CONTROL_PATTERNS + (
        r"\bgermline\b",
        r"\bmrca\b",
        r"\bpublic clonotype\b",
    )

    def analyze(self, text: str, scan_results: dict | None) -> dict:
        scan_results = scan_results or {}
        lowered = text.lower()
        tables = (scan_results.get("tables") or {}).get("total_table_count", 0)
        pdb_ids = scan_results.get("pdb_ids") or []
        genbank = scan_results.get("genbank") or {}
        genbank_total = len(genbank.get("likely_genbank") or [])
        antibody_names = self._unique_names(scan_results.get("antibody_name_candidates") or [])
        cdr3_results = scan_results.get("cdr3_sequences") or {}

        supplement_mentions = self._count_patterns(lowered, self.SUPPLEMENT_PATTERNS)
        structure_hits = self._count_patterns(lowered, self.STRUCTURE_PATTERNS)
        lineage_hits = self._count_patterns(lowered, self.LINEAGE_PATTERNS)
        multi_target_hits = self._count_patterns(lowered, self.MULTI_TARGET_PATTERNS)
        control_hits = self._count_patterns(lowered, self.CONTROL_PATTERNS)
        engineering_hits = self._count_patterns(lowered, self.ENGINEERING_PATTERNS)
        figure_mentions = len(re.findall(r"\bfig(?:ure)?\.?\s*[0-9a-z]", lowered))
        image_mentions = len(re.findall(r"images/", text))
        kinetics_hits = self._count_patterns(lowered, self.KINETICS_PATTERNS)
        epitope_hits = self._count_patterns(lowered, self.EPITOPE_PATTERNS)
        in_vivo_hits = self._count_patterns(lowered, self.IN_VIVO_PATTERNS)

        priority_names, deprioritized_names = self._rank_names(text, antibody_names)

        paper_type = []
        if tables >= 3:
            paper_type.append("table-heavy")
        if supplement_mentions >= 2:
            paper_type.append("supplement-heavy")
        if pdb_ids or structure_hits >= 2:
            paper_type.append("structure-heavy")
        if lineage_hits >= 2 or (scan_results.get("germline_genes") or {}).get("IMGT_V_genes"):
            paper_type.append("lineage-focused")
        if multi_target_hits >= 2:
            paper_type.append("multi-target or breadth-focused")
        if not paper_type:
            paper_type.append("discovery / characterization")

        evidence_carriers = []
        if tables:
            evidence_carriers.append("table-led")
        if supplement_mentions:
            evidence_carriers.append("supplement-led")
        if figure_mentions >= 4 or image_mentions:
            evidence_carriers.append("figure-caption-led")
        if (cdr3_results.get("CDRH3_candidates") or []) or (cdr3_results.get("CDRL3_candidates") or []):
            evidence_carriers.append("sequence-led")
        if pdb_ids or structure_hits >= 2:
            evidence_carriers.append("structure-led")
        if not evidence_carriers:
            evidence_carriers.append("narrative-led")
        if len(evidence_carriers) > 1:
            evidence_carriers.insert(0, "mixed")

        activated_modules = ["Candidate antibody identification"]
        if tables:
            activated_modules.append("Table row extraction")
        if figure_mentions >= 4 or image_mentions:
            activated_modules.append("Figure-caption quantitative extraction")
        if (
            (cdr3_results.get("CDRH3_candidates") or [])
            or (cdr3_results.get("CDRL3_candidates") or [])
            or genbank_total
            or re.search(r"\bvh\b|\bvl\b|\bcdrh3\b|\bsequence\b", lowered)
        ):
            activated_modules.append("Sequence extraction")
        if kinetics_hits:
            activated_modules.append("Kinetics / potency extraction")
        if pdb_ids or structure_hits >= 2:
            activated_modules.append("Structure evidence")
        if epitope_hits:
            activated_modules.append("Epitope extraction")
        if in_vivo_hits:
            activated_modules.append("In-vivo effect extraction")
        if control_hits or deprioritized_names:
            activated_modules.append("Reference antibody retention check")
        if pdb_ids or genbank_total:
            activated_modules.append("Missing-value backfill clues")

        primary_evidence_sources = []
        if tables:
            primary_evidence_sources.append(f"Main and supplementary tables ({tables} detected)")
        if supplement_mentions:
            primary_evidence_sources.append("Supplementary sections and extended data")
        if pdb_ids or genbank_total:
            primary_evidence_sources.append("Accession-backed evidence from PDB / GenBank")
        if figure_mentions >= 6 or image_mentions:
            primary_evidence_sources.append("Figure captions and sequence / alignment figures")
        if (cdr3_results.get("CDRH3_candidates") or []) or (cdr3_results.get("CDRL3_candidates") or []):
            primary_evidence_sources.append("Inline CDR3-like sequence mentions")
        if not primary_evidence_sources:
            primary_evidence_sources.append("Narrative results sections in the main text")

        extraction_priority = []
        if tables:
            extraction_priority.append("Start from the most local table rows and supplementary table rows before using prose summaries.")
        if figure_mentions >= 4 or image_mentions:
            extraction_priority.append("Use figure captions or panel-local statements only when they bind a value to one antibody-target-condition unit.")
        if genbank_total or pdb_ids:
            extraction_priority.append("Use accession / PDB pointers as recovery paths when exact sequence or structure values are not printed directly.")
        extraction_priority.append("Only fall back to narrative results text after checking structured or panel-local evidence.")

        entity_risks = []
        if control_hits or deprioritized_names:
            entity_risks.append("Comparator / control / previously published antibodies may be mixed into the paper narrative")
        if lineage_hits:
            entity_risks.append("Germline, MRCA, lineage, or reverted constructs may look like extractable antibodies but often are lineage context")
        if engineering_hits:
            entity_risks.append("Engineered, swapped-chain, mutant, or chimeric variants may need separation from the parent antibody")
        if multi_target_hits:
            entity_risks.append("Target breadth or multi-target constructs may require separate records when evidence differs by target")
        if not entity_risks:
            entity_risks.append("Main risk is over-merging repeated assay mentions into duplicate antibody records")

        evidence_unit_policy = (
            "One record should capture one evidence unit: antibody name + target/object + condition/background + assay/readout + directly attributable quantitative value."
        )
        sequence_focus = [
            "Prefer explicit full-chain VH/VL or CDRH3 evidence from tables, supplements, and accession-backed records over prose mentions.",
        ]
        if tables or supplement_mentions:
            sequence_focus.append("Check supplementary tables and table-like sections before relying on narrative discussion.")
        if pdb_ids or genbank_total:
            sequence_focus.append("Use PDB / GenBank IDs as confirmation or recovery paths when the text points to deposited sequences.")
        if lineage_hits:
            sequence_focus.append("Do not treat germline, MRCA, or reverted lineage nodes as core antibodies unless the paper assigns direct paper-specific measurements to them.")
        if control_hits or deprioritized_names:
            sequence_focus.append("Keep benchmark or control antibodies out unless they carry paper-specific sequence or quantitative evidence.")
        if image_mentions or figure_mentions >= 6:
            sequence_focus.append("Use figure captions and sequence-alignment figures as secondary evidence, not as the first source when tables exist.")

        if multi_target_hits or engineering_hits:
            split_policy = (
                "Split records when the paper reports distinct target pairing, engineered chain combination, condition/background, or variant-specific quantitative data."
            )
        elif len(priority_names) >= 4 or len(antibody_names) >= 8:
            split_policy = (
                "Keep one record per paper-specific antibody identity only when target, condition, assay, and directly bound value remain the same evidence unit."
            )
        else:
            split_policy = (
                "Split when local evidence changes target, condition, assay, construct, or value attribution; keep KD/kon/koff together only if they belong to the same local row or panel."
            )

        value_binding_policy = (
            "Every non-null value, pointer, and quote must map to the same local evidence. If a local table/panel gives an exact value, copy the exact value and unit. If only a locator is visible, leave value null and keep the pointer."
        )

        difficulty_flags = []
        if len(antibody_names) >= 8:
            difficulty_flags.append("many antibody candidates")
        if tables >= 4:
            difficulty_flags.append("many tables")
        if supplement_mentions >= 4:
            difficulty_flags.append("supplement-heavy")
        if lineage_hits >= 2:
            difficulty_flags.append("lineage terminology")
        if multi_target_hits >= 2:
            difficulty_flags.append("multi-target / breadth cues")
        if engineering_hits >= 2:
            difficulty_flags.append("engineered-variant cues")
        if control_hits >= 2:
            difficulty_flags.append("comparator / control cues")

        focus = {
            "paper_type": paper_type,
            "evidence_carriers": self._unique_names(evidence_carriers),
            "activated_modules": activated_modules,
            "primary_evidence_sources": primary_evidence_sources[:5],
            "extraction_priority": extraction_priority[:4],
            "evidence_unit_policy": evidence_unit_policy,
            "entity_risks": entity_risks[:5],
            "sequence_focus": sequence_focus[:5],
            "split_policy": split_policy,
            "value_binding_policy": value_binding_policy,
            "priority_antibody_names": priority_names[:6],
            "deprioritized_antibody_names": deprioritized_names[:6],
            "difficulty_flags": difficulty_flags,
            "hard_paper": len(difficulty_flags) >= 3,
            "counts": {
                "antibody_candidates": len(antibody_names),
                "tables": tables,
                "supplement_mentions": supplement_mentions,
                "figure_mentions": figure_mentions,
                "pdb_ids": len(pdb_ids),
                "genbank_ids": genbank_total,
            },
        }
        focus["paper_focus_text"] = self.format_focus(focus)
        return focus

    def format_focus(self, focus: dict | None) -> str:
        if not isinstance(focus, dict):
            return "No paper-level focus analysis available."
        lines = []
        lines.append("- Paper profile: " + "; ".join(focus.get("paper_type") or ["unknown"]))
        carriers = focus.get("evidence_carriers") or []
        if carriers:
            lines.append("- Evidence carriers: " + "; ".join(carriers))
        modules = focus.get("activated_modules") or []
        if modules:
            lines.append("- Activated modules: " + "; ".join(modules[:6]))
        lines.append(
            "- Prioritize evidence: "
            + "; ".join(focus.get("primary_evidence_sources") or ["main text narrative"])
        )
        priorities = focus.get("extraction_priority") or []
        if priorities:
            lines.append("- Extraction order: " + " ".join(priorities))
        lines.append(
            "- Evidence-unit rule: "
            + (focus.get("evidence_unit_policy") or "Use one record per local evidence unit.")
        )
        lines.append(
            "- Sequence extraction focus: "
            + " ".join(focus.get("sequence_focus") or ["Prefer direct sequence evidence."])
        )
        lines.append(
            "- Entity risks: "
            + "; ".join(focus.get("entity_risks") or ["no special entity risks detected"])
        )
        lines.append("- Split policy: " + (focus.get("split_policy") or "Use default split policy."))
        lines.append(
            "- Value / pointer discipline: "
            + (focus.get("value_binding_policy") or "Keep value, pointer, and quote aligned to the same local evidence.")
        )
        priority = focus.get("priority_antibody_names") or []
        if priority:
            lines.append("- Priority antibody names: " + ", ".join(priority))
        deprioritized = focus.get("deprioritized_antibody_names") or []
        if deprioritized:
            lines.append("- Deprioritize unless paper-specific evidence appears: " + ", ".join(deprioritized))
        flags = focus.get("difficulty_flags") or []
        if flags:
            lines.append("- Difficulty flags: " + ", ".join(flags))
        return "\n".join(lines)

    @staticmethod
    def _count_patterns(text: str, patterns: tuple[str, ...]) -> int:
        return sum(len(re.findall(pattern, text, re.IGNORECASE)) for pattern in patterns)

    @staticmethod
    def _unique_names(names: list[str]) -> list[str]:
        seen = set()
        ordered = []
        for name in names:
            clean = (name or "").strip()
            key = clean.lower()
            if not clean or key in seen:
                continue
            seen.add(key)
            ordered.append(clean)
        return ordered

    def _rank_names(self, text: str, names: list[str]) -> tuple[list[str], list[str]]:
        lowered = text.lower()
        sentences = [segment.strip().lower() for segment in re.split(r"(?<=[.!?])\s+", text) if segment.strip()]
        scored = []
        for name in names[:25]:
            idx = lowered.find(name.lower())
            if idx < 0:
                continue
            sentence_hits = [sentence for sentence in sentences if name.lower() in sentence]
            window = " ".join(sentence_hits[:2]) or lowered[max(0, idx - 100): idx + len(name) + 100]
            if self._count_patterns(window, self.NAME_CONTEXT_PATTERNS) == 0:
                continue
            score = 0
            score += self._count_patterns(window, self.POSITIVE_NAME_PATTERNS)
            score -= 2 * self._count_patterns(window, self.NEGATIVE_NAME_PATTERNS)
            if "table" in window or "supp" in window:
                score += 1
            scored.append((name, score))

        priority = [name for name, score in scored if score >= 1]
        deprioritized = [name for name, score in scored if score <= -1]
        return self._unique_names(priority), self._unique_names(deprioritized)
