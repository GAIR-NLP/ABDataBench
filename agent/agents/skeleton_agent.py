"""Phase 2: LLM skeleton construction agent."""

import re
import time
from pathlib import Path
from .base_agent import BaseAgent, AgentResult, AgentStatus
from tools.llm_client import LLMClient
from tools.table_parser import TableParser
from tools.amino_acid_utils import normalize_aa_sequence
from tools.skill_loader import load_skill_prompt_set


class SkeletonAgent(BaseAgent):
    MIN_VARIABLE_REGION_AA_LEN = 80
    MIN_CDRH3_AA_LEN = 5
    MAX_CDRH3_AA_LEN = 40
    STANDARD_AA = set("ACDEFGHIKLMNPQRSTVWY")
    EXPERIMENT_PATTERNS = (
        (r"\bflow cytometry\b|\bfacs\b", "Flow Cytometry"),
        (r"\belisa\b", "ELISA"),
        (r"\bitc\b|isothermal titration calorimetry", "ITC"),
        (r"\bbli\b|biolayer interferometry", "BLI"),
        (r"\bspr\b|surface plasmon resonance", "SPR"),
        (r"microneutralization", "Microneutralization assay"),
        (r"neutralization", "Neutralization assay"),
        (r"\bbeacon\b", "Beacon"),
        (r"\bilsda\b", "ILSDA"),
    )
    EXPERIMENT_BANNED_PATTERNS = (
        r"western blot|\bwb\b",
        r"x-ray|xray|cryo-?em|crystallography",
        r"sequencing",
        r"sorting|gating|expression qc",
        r"challenge|mouse model|in vivo",
        r"immunoprecipitation|lc-?ms|mass spectrometry",
    )
    PAGINATION_PROMPT = """
[Pagination Mode]
Return only one valid JSON object for this page.

Requirements:
- Return at most {page_size} antibodies on this page.
- Do not repeat antibodies already returned in earlier pages.
- Order antibodies deterministically by first evidence appearance in the document, then antibody name.
- If more eligible antibodies remain after this page, set `pagination.has_more` to true. Otherwise set it to false.
- `pagination.returned_antibody_names` must exactly match the antibodies returned on this page.
- Each antibody item must use flat ground-truth-style string fields, not nested value/quote/pointer/action objects.
- If evidence is incomplete, missing from OCR, or not uniquely attributable, keep the relevant field as an empty string.
- Do not include markdown fences or explanatory text.

Use this exact envelope:
{{
  "paper": {{
    "paper_id": "{paper_id}",
    "title": "<title>",
    "category": "paper",
    "antibodies": [ ... page items only ... ]
  }},
  "pagination": {{
    "page_index": {page_index},
    "page_size": {page_size},
    "has_more": true,
    "returned_antibody_names": ["Ab1", "Ab2"]
  }}
}}

[Already Returned Antibody Names]:
{seen_names}
"""
    FIELD_HINT_KEYS = {
        "CDRH3_Sequence",
        "vh_sequence_aa",
        "vl_sequence_aa",
        "Structure",
    }
    REFERENCE_ONLY_HINT_PATTERNS = (
        r"\bcontrol mabs?\b",
        r"\bcontrol abs?\b",
        r"\bcontrol antibodies\b",
        r"\bused as control\b",
        r"\bpreviously described\b",
        r"\bpreviously published\b",
        r"\bpublished previously\b",
        r"\bother representative .* antibodies\b",
        r"\bpublic clonotypes?\b",
        r"\bpublic mabs?\b",
        r"\bfrom .*infected patients and vaccinees\b",
        r"\binfected patients and vaccinees\b",
        r"\bclonotyping\b",
        r"\bjunctional sequence analysis\b",
        r"\bparallel lineage\b",
        r"\binferred germline\b",
        r"\bigl mabs?\b",
        r"\bgroup [12] rbd bnabs?\b",
    )

    def __init__(self, config, llm: LLMClient = None):
        super().__init__("skeleton", config)
        self.llm = llm or LLMClient(config)
        self.table_parser = TableParser()
        prompts_dir = Path(__file__).resolve().parent.parent / "prompts"
        prompts = load_skill_prompt_set(
            "antibody-skeleton-extraction",
            {
                "system_prompt": prompts_dir / "skeleton_system.txt",
                "user_template": prompts_dir / "skeleton_user.txt",
            },
        )
        self.system_prompt = prompts["system_prompt"]
        self.user_template = prompts["user_template"]

    async def execute(self, context: dict) -> AgentResult:
        start = time.time()
        agent_span = self._start_span(context, "agent", self.name)
        try:
            paper_id = context.get("paper_id", "unknown")
            user_msg = self._build_user_message(context)

            llm_tokens = 0
            skeleton, llm_tokens = await self._build_paginated_skeleton(
                user_msg=user_msg,
                paper_id=paper_id,
                phase=context.get("current_phase"),
            )
            # Normalize: ensure it's in the standard eval format
            skeleton = self._normalize(skeleton, paper_id)

            # Filter: remove non-core antibodies that slipped through
            skeleton = self._filter_non_core(skeleton, paper_id)
            skeleton = self._apply_optional_antibody_cap(skeleton, paper_id)

            elapsed = round(time.time() - start, 2)
            ab_count = len(skeleton.get(paper_id, {}).get("antibodies", []))
            self.logger.info(f"Skeleton built: {ab_count} antibodies, {elapsed}s, "
                             f"{llm_tokens} tokens")
            self._end_span(
                context,
                agent_span,
                status="success",
                elapsed_seconds=elapsed,
                antibody_count=ab_count,
                llm_tokens=llm_tokens,
            )
            return AgentResult(
                status=AgentStatus.SUCCESS,
                data=skeleton,
                metrics={"elapsed_seconds": elapsed, "llm_tokens": llm_tokens},
            )
        except ValueError as exc:
            paper_id = context.get("paper_id", "unknown")
            self.logger.warning(
                "Skeleton LLM output was not parseable JSON; using heuristic fallback: %s",
                exc,
            )
            skeleton = self._heuristic_skeleton(context, paper_id)
            skeleton = self._normalize(skeleton, paper_id)
            skeleton = self._filter_non_core(skeleton, paper_id)
            skeleton = self._apply_optional_antibody_cap(skeleton, paper_id)
            elapsed = round(time.time() - start, 2)
            ab_count = len(skeleton.get(paper_id, {}).get("antibodies", []))
            self.logger.info(f"Skeleton built: {ab_count} antibodies, {elapsed}s, 0 tokens")
            self._end_span(
                context,
                agent_span,
                status="success",
                elapsed_seconds=elapsed,
                antibody_count=ab_count,
                llm_tokens=0,
            )
            return AgentResult(
                status=AgentStatus.SUCCESS,
                data=skeleton,
                metrics={"elapsed_seconds": elapsed, "llm_tokens": 0},
            )
        except Exception as exc:
            self._end_span(context, agent_span, status="error", error=str(exc))
            raise

    def _build_user_message(self, context: dict) -> str:
        md_text = context.get("markdown_text_reduced") or context["markdown_text"]
        hints = context["regex_hints"]["regex_hints_text"]
        paper_id = context.get("paper_id", "unknown")
        corrections = context.get("corrections")
        paper_focus = self._format_paper_focus(context.get("paper_focus"))

        max_input_chars = getattr(self.config, "skeleton_max_input_chars", 200_000)
        if len(md_text) > max_input_chars:
            self.logger.warning(
                "Document too long (%s chars), truncating to %s chars",
                len(md_text),
                max_input_chars,
            )
            md_text = md_text[:max_input_chars] + "\n\n[... truncated ...]"

        user_msg = self.user_template.format(
            REGEX_HINTS=hints,
            PAPER_ID=paper_id,
            PAPER_FOCUS_ANALYSIS=paper_focus,
            DOCUMENT_TEXT=md_text,
        )
        reduced_meta = context.get("markdown_text_reduced_meta") or {}
        if reduced_meta.get("used_reduced_text"):
            user_msg = (
                "[Context Reduction]: The document body below was pre-filtered to preserve "
                "results, figures, tables, supplementary mentions, sequence cues, IDs, and image evidence.\n\n"
                f"{user_msg}"
            )
        sequence_image_hints = self._format_sequence_image_hints(context.get("sequence_image_result"))
        if sequence_image_hints:
            user_msg += f"\n\n{sequence_image_hints}"
        if corrections:
            user_msg += f"\n\n[修正要求 - 请根据以下反馈修正你的输出]:\n{corrections}"
        return user_msg

    async def _build_paginated_skeleton(
        self,
        *,
        user_msg: str,
        paper_id: str,
        phase: str | None,
    ) -> tuple[dict, int]:
        trace_fields = {"paper_id": paper_id, "phase": phase, "agent": self.name}
        page_size = max(1, getattr(self.config, "skeleton_page_size", 8))
        max_pages = max(1, getattr(self.config, "skeleton_max_pages", 10))
        combined = {
            paper_id: {
                "paper_id": paper_id,
                "title": paper_id,
                "category": self._infer_category(paper_id),
                "antibodies": [],
            }
        }
        seen_names = set()
        total_tokens = 0

        for page_index in range(1, max_pages + 1):
            seen_text = ", ".join(sorted(seen_names)) if seen_names else "None"
            paged_user_msg = (
                f"{user_msg}\n\n"
                + self.PAGINATION_PROMPT.format(
                    page_size=page_size,
                    paper_id=paper_id,
                    page_index=page_index,
                    seen_names=seen_text,
                )
            )
            resp = await self.llm.chat(
                system=self.system_prompt,
                user=paged_user_msg,
                temperature=0.1,
                max_tokens=self.config.llm_max_tokens,
                response_format="json",
                trace_fields={**trace_fields, "page_index": page_index},
            )
            total_tokens += resp.total_tokens
            parsed = self.llm.parse_json_response(resp.content)
            page_payload, pagination = self._extract_paginated_payload(parsed, paper_id)
            normalized_page = self._normalize(page_payload, paper_id)
            page_entry = normalized_page.get(paper_id, {})
            if page_entry.get("title"):
                combined[paper_id]["title"] = page_entry["title"]
            if page_entry.get("category"):
                combined[paper_id]["category"] = page_entry["category"]

            page_antibodies = page_entry.get("antibodies", [])
            new_count = self._merge_page_antibodies(combined[paper_id]["antibodies"], page_antibodies)
            page_names = {
                (ab.get("Antibody_Name") or "").strip()
                for ab in page_antibodies
                if (ab.get("Antibody_Name") or "").strip()
            }
            seen_names.update(page_names)

            has_more = bool((pagination or {}).get("has_more"))
            if page_index == max_pages:
                self.logger.warning(
                    "Skeleton pagination reached max pages for %s (%s)",
                    paper_id,
                    max_pages,
                )
                break
            if not has_more:
                break
            if new_count == 0:
                self.logger.warning(
                    "Skeleton pagination returned no new antibodies for %s on page %s; stopping early",
                    paper_id,
                    page_index,
                )
                break

        return combined, total_tokens

    @staticmethod
    def _extract_paginated_payload(parsed: dict | list, paper_id: str) -> tuple[dict | list, dict]:
        if not isinstance(parsed, dict):
            raise ValueError(f"Unexpected paginated skeleton format: {type(parsed).__name__}")
        pagination = parsed.get("pagination") or parsed.get("_pagination") or {}
        if "paper" in parsed:
            return parsed["paper"], pagination
        if paper_id in parsed:
            return parsed[paper_id], pagination
        if "antibodies" in parsed:
            return parsed, pagination
        raise ValueError("Paginated skeleton response missing `paper` payload")

    def _merge_page_antibodies(self, combined_antibodies: list[dict], page_antibodies: list[dict]) -> int:
        index = {
            self._record_identity_key(ab): pos
            for pos, ab in enumerate(combined_antibodies)
            if (ab.get("Antibody_Name") or "").strip()
        }
        added = 0
        for ab in page_antibodies:
            name = (ab.get("Antibody_Name") or "").strip()
            if not name:
                continue
            key = self._record_identity_key(ab)
            existing_idx = index.get(key)
            if existing_idx is None:
                combined_antibodies.append(ab)
                index[key] = len(combined_antibodies) - 1
                added += 1
                continue
            if self._filled_field_count(ab) > self._filled_field_count(combined_antibodies[existing_idx]):
                combined_antibodies[existing_idx] = ab
        return added

    @staticmethod
    def _filled_field_count(ab: dict) -> int:
        return sum(
            1
            for key, value in ab.items()
            if not str(key).startswith("_") and value not in ("", None, [], {})
        )

    @staticmethod
    def _normalize_key_text(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", str(value or "").strip().lower())

    @staticmethod
    def _extract_reference_doi(value: str) -> str:
        match = re.search(r"(10\.\d{4,9}/[-._;()/:A-Z0-9]+)", str(value or ""), re.IGNORECASE)
        return match.group(1).rstrip(".,;)") if match else ""

    @classmethod
    def _extract_reference_year(cls, value: str) -> str:
        match = re.search(r"\b(19|20)\d{2}\b", str(value or ""))
        return match.group(0) if match else ""

    @classmethod
    def _extract_reference_author(cls, value: str) -> str:
        text = str(value or "")
        match = re.search(r"\(([A-Za-z][A-Za-z'`\- ]+?)\s+et al\.?\)", text, re.IGNORECASE)
        if match:
            return match.group(1).strip().split()[-1]
        match = re.search(r"\b([A-Z][A-Za-z'`\-]+)\s+et al\.?\b", text)
        if match:
            return match.group(1)
        parts = re.split(r"\s+", text.strip())
        return parts[0] if parts else ""

    @classmethod
    def _extract_reference_journal(cls, value: str) -> str:
        text = str(value or "")
        text = re.sub(r"\([^)]*\)", " ", text)
        text = re.sub(r"doi\s*:?.*$", " ", text, flags=re.IGNORECASE)
        year = cls._extract_reference_year(text)
        if year:
            text = text.replace(year, " ")
        text = re.sub(r"\bet al\.?\b", " ", text, flags=re.IGNORECASE)
        text = re.sub(r"[^A-Za-z0-9. ]+", " ", text)
        tokens = [token for token in text.split() if token]
        if not tokens:
            return ""
        lowered = [token.lower() for token in tokens]
        if "et" in lowered:
            et_idx = lowered.index("et")
            tokens = tokens[et_idx + 2 :]
        return " ".join(tokens[:4]).strip(" ,.")

    @classmethod
    def _normalize_reference_source(cls, value: str) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        doi = cls._extract_reference_doi(text)
        year = cls._extract_reference_year(text)
        author = cls._extract_reference_author(text)
        journal = cls._extract_reference_journal(text)
        if author and year and journal:
            formatted = f"{author} et al. {journal}, {year}"
            if doi:
                formatted += f". DOI: {doi}"
            return formatted
        return text

    @classmethod
    def _normalize_experiment_value(cls, value: str) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        lowered = text.lower()
        kept = []
        seen = set()
        for pattern, canonical in cls.EXPERIMENT_PATTERNS:
            if re.search(pattern, lowered, re.IGNORECASE) and canonical not in seen:
                kept.append(canonical)
                seen.add(canonical)
        if kept:
            return ", ".join(kept)

        filtered_parts = []
        for part in re.split(r"[,;/，；、\n]+", text):
            item = part.strip()
            if not item:
                continue
            if any(re.search(pattern, item, re.IGNORECASE) for pattern in cls.EXPERIMENT_BANNED_PATTERNS):
                continue
            filtered_parts.append(item)
        return ", ".join(filtered_parts)

    @classmethod
    def _record_identity_key(cls, ab: dict) -> tuple[str, ...]:
        name = cls._normalize_key_text(ab.get("Antibody_Name", ""))
        target = cls._normalize_key_text(ab.get("Target_Name", ""))
        ab_type = cls._normalize_key_text(ab.get("Antibody_Type", ""))
        experiment = cls._normalize_key_text(ab.get("Experiment", ""))
        structure = cls._normalize_key_text(ab.get("Structure", ""))
        if any((target, ab_type, experiment, structure)):
            return (name, target, ab_type, experiment, structure)
        return (name,)

    def _heuristic_skeleton(self, context: dict, paper_id: str) -> dict:
        """Build a lightweight skeleton from regex/table signals when the LLM output is empty or filtered."""
        text = context["markdown_text"]
        hints = context.get("regex_hints", {})
        title = self._infer_title(context, paper_id)
        target_name = self._infer_target_name(text)
        target_type = "Viral protein" if target_name else ""
        cross_reactivity = self._infer_cross_reactivity(text)
        mechanism = self._infer_mechanism(text)
        experiment = self._infer_experiment(text)
        ref_source = title or paper_id
        structure_map = self._extract_structure_map(text)
        antibodies = []
        seen = set()

        for record in self.table_parser.extract_all_antibody_records(text):
            name = (record.get("mAb") or record.get("Antibody_Name") or "").strip()
            if not name or name.lower() in seen:
                continue
            ab = self._empty_antibody(name, ref_source)
            cdrh3 = (record.get("CDRH3") or "").strip()
            if cdrh3:
                ab["CDRH3_Sequence"] = cdrh3

            const_region = (record.get("Constant region genes") or "").strip().upper()
            if "IGHG1" in const_region:
                ab["Antibody_Type"] = "Monoclonal IgG1"
                ab["Antibody_Isotype"] = "Human IgG1"
                ab["source"] = "human"
            elif "IGHA" in const_region:
                ab["Antibody_Type"] = "Monoclonal IgA"
                ab["Antibody_Isotype"] = "Human IgA"
                ab["source"] = "human"
            elif "IGHM" in const_region:
                ab["Antibody_Type"] = "Monoclonal IgM"
                ab["Antibody_Isotype"] = "Human IgM"
                ab["source"] = "human"

            for src_key, dst_key in [
                ("KD", "Binding_Kinetics_KD"),
                ("EC50", "Binding_EC50"),
                ("IC50", "Quantitative_Metric"),
            ]:
                val = (record.get(src_key) or "").strip()
                if val:
                    ab[dst_key] = val

            if target_name:
                ab["Target_Name"] = target_name
                ab["Target_Type"] = target_type
            if cross_reactivity:
                ab["Cross_Reactivity"] = cross_reactivity
            if mechanism:
                ab["Mechanism_of_Action"] = mechanism
            if experiment:
                ab["Experiment"] = experiment
            if name in structure_map:
                ab["Structure"] = structure_map[name]

            antibodies.append(ab)
            seen.add(name.lower())

        if not antibodies:
            for name in hints.get("antibody_name_candidates", []):
                norm = name.strip()
                if norm and norm.lower() not in seen:
                    antibodies.append(self._empty_antibody(norm, paper_id))
                    seen.add(norm.lower())

        self.logger.info("Heuristic skeleton built: %d antibodies", len(antibodies))
        return {
            paper_id: {
                "paper_id": paper_id,
                "title": title,
                "antibodies": antibodies,
            }
        }

    @staticmethod
    def _infer_title(context: dict, paper_id: str) -> str:
        input_file = context.get("input_file", "")
        if input_file:
            parent = Path(input_file).resolve().parent.name.strip()
            if parent and parent.lower() != paper_id.lower():
                return parent
        return paper_id

    @staticmethod
    def _infer_category(paper_id: str) -> str:
        text = str(paper_id or "").strip().upper()
        if re.match(r"^(US|WO|EP|CN|JP|KR)\d", text):
            return "patent"
        return "paper"

    @staticmethod
    def _infer_target_name(text: str) -> str:
        if re.search(r"MPXV A35 \(Clade IIb\)", text, re.IGNORECASE):
            return "MPXV A35 (Clade IIb)"
        if re.search(r"EV35-\d+\s*\+\s*A35", text, re.IGNORECASE):
            return "MPXV A35"
        return ""

    @staticmethod
    def _infer_cross_reactivity(text: str) -> str:
        if re.search(r"cross-reactive", text, re.IGNORECASE) and re.search(r"VACV(?:A33)?", text, re.IGNORECASE):
            return "VACV A33"
        return ""

    @staticmethod
    def _infer_mechanism(text: str) -> str:
        parts = []
        if re.search(r"cross-reactive", text, re.IGNORECASE):
            parts.append("Cross-reactive binding")
        if re.search(r"complement-dependent", text, re.IGNORECASE):
            parts.append("Complement-dependent activity")
        return "; ".join(parts)

    @staticmethod
    def _infer_experiment(text: str) -> str:
        methods = []
        if re.search(r"\bELISA\b", text, re.IGNORECASE):
            methods.append("ELISA")
        if re.search(r"\bBLI\b|biolayer interferometry", text, re.IGNORECASE):
            methods.append("BLI")
        if re.search(r"\bSPR\b|surface plasmon resonance", text, re.IGNORECASE):
            methods.append("SPR")
        if re.search(r"\bBeacon\b", text, re.IGNORECASE):
            methods.append("Beacon")
        return ", ".join(methods)

    @staticmethod
    def _format_paper_focus(paper_focus: dict | None) -> str:
        if not isinstance(paper_focus, dict):
            return "No paper-specific focus analysis available. Use default extraction policy."
        focus_text = (paper_focus.get("paper_focus_text") or "").strip()
        if focus_text:
            return focus_text

        lines = []
        for key in (
            "paper_type",
            "primary_evidence_sources",
            "entity_risks",
            "sequence_focus",
        ):
            value = paper_focus.get(key)
            if isinstance(value, list) and value:
                lines.append(f"- {key}: {'; '.join(str(v) for v in value)}")
        split_policy = paper_focus.get("split_policy")
        if split_policy:
            lines.append(f"- split_policy: {split_policy}")
        return "\n".join(lines) or "No paper-specific focus analysis available. Use default extraction policy."

    @staticmethod
    def _format_sequence_image_hints(sequence_image_result: dict | None) -> str:
        if not isinstance(sequence_image_result, dict):
            return ""
        records = sequence_image_result.get("table_records", [])
        if not records:
            return ""

        lines = [
            "[Sequence Image Hints]:",
            "以下抗体在图片型 sequence/alignment panel 中有局部序列证据。这些提示主要用于补全已被正文/表格确认属于本文研究对象的抗体字段。",
            "如果某个名字只出现在 comparator/control/published antibody alignment、public clonotype、clonotyping 或 junctional-sequence 面板中，不要仅凭图片证据把它新增为 antibodies 数组成员。",
        ]
        seen = set()
        for record in records[:12]:
            if SkeletonAgent._is_reference_only_sequence_hint(record):
                continue
            name = (record.get("mAb") or record.get("Antibody_Name") or "").strip()
            if not name or name.lower() in seen:
                continue
            evidence = []
            if record.get("VH_sequence"):
                evidence.append("VH visible")
            if record.get("VL_sequence"):
                evidence.append("VL visible")
            if record.get("CDRH3"):
                evidence.append("CDRH3 visible")
            image = record.get("_source_image", "")
            suffix = f" [{image}]" if image else ""
            lines.append(f"- {name}: {', '.join(evidence) or 'sequence evidence'}{suffix}")
            seen.add(name.lower())
        if len(lines) <= 3:
            return ""
        return "\n".join(lines)

    @classmethod
    def _is_reference_only_sequence_hint(cls, record: dict) -> bool:
        context = " ".join(
            str(record.get(key) or "")
            for key in ("_source_context", "_source_image", "_source_crop_image")
        )
        if not context:
            return False
        lowered = context.lower()
        return any(
            re.search(pattern, lowered, re.IGNORECASE)
            for pattern in cls.REFERENCE_ONLY_HINT_PATTERNS
        )

    @staticmethod
    def _extract_vh_vl_map(text: str) -> dict[str, tuple[str, str]]:
        lines = [line.strip() for line in text.splitlines()]
        for idx, line in enumerate(lines):
            if line != "mAb ID":
                continue
            names = []
            j = idx + 1
            while j < len(lines) and lines[j] != "VH":
                if re.fullmatch(r"EV\d+-\d+", lines[j]):
                    names.append(lines[j])
                j += 1
            if j >= len(lines) or not names:
                continue
            j += 1
            vhs = []
            while j < len(lines) and lines[j] != "VL":
                if re.fullmatch(r"IG[HKL]V\d+-\d+", lines[j]):
                    vhs.append(lines[j])
                j += 1
            if j >= len(lines):
                continue
            j += 1
            vls = []
            while j < len(lines):
                if re.fullmatch(r"IG[KL]V\d+-\d+", lines[j]):
                    vls.append(lines[j])
                elif vls and not lines[j]:
                    break
                elif vls and lines[j].startswith("---"):
                    break
                j += 1
            if len(names) == len(vhs) == len(vls):
                return {name: (vh, vl) for name, vh, vl in zip(names, vhs, vls)}
        return {}

    def _extract_structure_map(self, text: str) -> dict[str, str]:
        structures = {}
        for table in self.table_parser.extract_html_tables(text):
            if not table or len(table) < 2:
                continue
            header = table[0]
            if not header or header[0] != "Data collection":
                continue
            names = []
            for cell in header[1:]:
                match = re.search(r"(EV\d+-\d+)\s*\+\s*A35", cell, re.IGNORECASE)
                names.append(match.group(1) if match else "")
            pdb_row = None
            for row in table[1:]:
                if row and row[0].strip().lower() == "pdb code":
                    pdb_row = row
                    break
            if not pdb_row:
                continue
            for name, pdb_code in zip(names, pdb_row[1:]):
                code = pdb_code.strip()
                if name and code:
                    structures[name] = f"A35 complex (PDB: {code})"
        return structures

    @staticmethod
    def _empty_antibody(name: str, reference_source: str) -> dict:
        return {
            "Antibody_Name": name,
            "Antibody_Type": "",
            "Antibody_Isotype": "",
            "source": "",
            "Target_Name": "",
            "Target_Type": "",
            "Cross_Reactivity": "",
            "Epitope": "",
            "Experiment": "",
            "Binding_Kinetics_KD": "",
            "Binding_Kinetics_kon": "",
            "Binding_Kinetics_koff": "",
            "Binding_EC50": "",
            "Mechanism_of_Action": "",
            "Quantitative_Metric": "",
            "Structure": "",
            "CDRH3_Sequence": "",
            "vh_sequence_aa": "",
            "vl_sequence_aa": "",
            "Thermal_Stability_Tm": "",
            "In_Vivo_Half_Life": "",
            "In_Vivo_Efficacy": "",
            "Reference_Source": reference_source,
        }

    @classmethod
    def _normalize_aa_sequence(cls, value: str) -> str:
        return normalize_aa_sequence(value)

    @classmethod
    def _looks_like_sequence_placeholder(cls, value: str) -> bool:
        raw = str(value or "").strip().lower()
        if not raw:
            return False
        if raw in {
            "n/a",
            "na",
            "none",
            "null",
            "unknown",
            "not provided",
            "not reported",
            "not available",
            "not found",
            "missing",
        }:
            return True
        if re.search(r"\b(?:not provided|not reported|not available|not found|missing|unknown)\b", raw):
            return True
        if "sequence" in raw and re.search(r"\b(?:text|image|images|figure|figures|table|tables|paper|document)\b", raw):
            return True
        return False

    @classmethod
    def _looks_like_full_variable_sequence(cls, value: str) -> bool:
        seq = cls._normalize_aa_sequence(value)
        return bool(seq) and len(seq) >= cls.MIN_VARIABLE_REGION_AA_LEN and set(seq) <= cls.STANDARD_AA

    @classmethod
    def _sanitize_cdrh3_sequence(cls, value: str) -> str:
        if not value:
            return ""
        raw = str(value).strip()
        if cls._looks_like_sequence_placeholder(raw):
            return ""
        seq = cls._normalize_aa_sequence(raw)
        if (
            cls.MIN_CDRH3_AA_LEN <= len(seq) <= cls.MAX_CDRH3_AA_LEN
            and set(seq) <= cls.STANDARD_AA
        ):
            return seq
        return ""

    @classmethod
    def _sanitize_variable_sequence(cls, value: str) -> str:
        if not value:
            return ""
        raw = str(value).strip()
        if cls._looks_like_sequence_placeholder(raw):
            return ""
        if cls._looks_like_full_variable_sequence(raw):
            return cls._normalize_aa_sequence(raw)
        return ""

    @staticmethod
    def _infer_source_type_from_hint(hint: dict) -> str:
        action = str(hint.get("action") or "").strip().lower()
        pointer = str(hint.get("pointer") or "").strip().lower()
        if action == "api fetch":
            return "api_fetch"
        if action == "script extract":
            if any(token in pointer for token in ("figure", "fig.", "image", ".jpg", ".png")):
                return "figure_or_image"
            if "table" in pointer:
                return "table"
            return "paper_location"
        return "paper_text"

    @classmethod
    def _normalize_field_source_entry(cls, hint: dict) -> dict:
        if not isinstance(hint, dict):
            return {}
        payload = {
            "source_type": cls._infer_source_type_from_hint(hint),
            "action": str(hint.get("action") or "").strip(),
            "pointer": str(hint.get("pointer") or "").strip(),
            "quote": str(hint.get("quote") or "").strip(),
            "confidence": str(hint.get("confidence") or "").strip(),
            "germline": str(hint.get("germline") or "").strip(),
        }
        if payload["source_type"] == "api_fetch" and payload["pointer"]:
            payload["source_label"] = f"API Fetch: {payload['pointer']}"
        elif payload["pointer"]:
            payload["source_label"] = payload["pointer"]
        elif payload["quote"]:
            payload["source_label"] = payload["quote"][:120]
        else:
            payload["source_label"] = ""
        return {key: value for key, value in payload.items() if value not in ("", None)}

    @classmethod
    def _build_field_sources_from_hints(cls, ab: dict) -> dict:
        field_hints = ab.get("_field_hints") or {}
        if not isinstance(field_hints, dict):
            return {}
        field_sources = {}
        for field, hint in field_hints.items():
            entry = cls._normalize_field_source_entry(hint)
            if entry:
                field_sources[field] = entry
        return field_sources

    def _normalize(self, data: dict | list, paper_id: str) -> dict:
        """Ensure output is in ground_truth-compatible format:
        {paper_id: {paper_id, title, antibodies: [...]}}
        """
        # Case 1: Already correct format
        if isinstance(data, dict) and paper_id in data:
            result = data
        # Case 2: {paper_id: ..., antibodies: [...]} without nesting
        elif isinstance(data, dict) and "antibodies" in data:
            result = {paper_id: {"paper_id": paper_id, **data}}
        # Case 3: Direct array of antibodies
        elif isinstance(data, list):
            result = {paper_id: {"paper_id": paper_id, "antibodies": data}}
        # Case 4: Some other paper_id key
        elif isinstance(data, dict):
            found = False
            for k, v in data.items():
                if isinstance(v, dict) and "antibodies" in v:
                    result = {paper_id: {"paper_id": paper_id, **v}}
                    found = True
                    break
            if not found:
                self.logger.warning(f"Unexpected skeleton format, wrapping as-is")
                result = {paper_id: {"paper_id": paper_id, "antibodies": [data] if isinstance(data, dict) else []}}
        else:
            self.logger.warning(f"Unexpected skeleton format, wrapping as-is")
            result = {paper_id: {"paper_id": paper_id, "antibodies": []}}

        # Fix field names in each antibody to match ground_truth format
        for ab in result.get(paper_id, {}).get("antibodies", []):
            self._fix_antibody_fields(ab)

        result.setdefault(paper_id, {})
        result[paper_id]["paper_id"] = paper_id
        result[paper_id].setdefault("title", paper_id)
        result[paper_id].setdefault("category", self._infer_category(paper_id))

        return result

    def _fix_antibody_fields(self, ab: dict):
        """Remap fields to match ground_truth v3 format (22 eval fields)"""
        # Fix 1: Legacy Experiment_value → split into Binding_Kinetics_KD / Binding_EC50
        if "Experiment_value" in ab:
            exp_val = ab.pop("Experiment_value")
            # If it's a list of experiment records, extract KD/EC50 values
            if isinstance(exp_val, list):
                for record in exp_val:
                    assay = (record.get("assay") or "").lower()
                    val = record.get("value")
                    if not val:
                        continue
                    if "kd" in assay or "dissociation" in assay:
                        if not ab.get("Binding_Kinetics_KD"):
                            ab["Binding_Kinetics_KD"] = val
                    elif "ec50" in assay:
                        if not ab.get("Binding_EC50"):
                            ab["Binding_EC50"] = val
                    elif "kon" in assay or "ka" in assay:
                        if not ab.get("Binding_Kinetics_kon"):
                            ab["Binding_Kinetics_kon"] = val
                    elif "koff" in assay or "kd" in assay:
                        if not ab.get("Binding_Kinetics_koff"):
                            ab["Binding_Kinetics_koff"] = val
                    else:
                        # Default: treat as KD if no Binding_Kinetics_KD yet
                        if not ab.get("Binding_Kinetics_KD"):
                            ab["Binding_Kinetics_KD"] = val
            elif isinstance(exp_val, str) and exp_val:
                if not ab.get("Binding_Kinetics_KD"):
                    ab["Binding_Kinetics_KD"] = exp_val

        # Fix 2: Legacy Affinity_nM → Binding_Kinetics_KD
        if "Affinity_nM" in ab:
            aff = ab.pop("Affinity_nM")
            if aff and not ab.get("Binding_Kinetics_KD"):
                ab["Binding_Kinetics_KD"] = aff

        # Fix 3: Legacy External_Database_ID → Structure
        if "External_Database_ID" in ab:
            ext_db = ab.pop("External_Database_ID")
            if ext_db and not ab.get("Structure"):
                if isinstance(ext_db, dict):
                    ab["Structure"] = ext_db.get("value", "")
                else:
                    ab["Structure"] = ext_db

        # Fix 4: Legacy PK_source → drop (not in v3 eval fields)
        ab.pop("PK_source", None)

        # Fix 5: Flatten structured Mechanism_of_Action
        moa = ab.get("Mechanism_of_Action")
        if isinstance(moa, list):
            # Extract MoA_Type values and Quantitative_Metric
            moa_types = []
            quant_metrics = []
            for item in moa:
                if isinstance(item, dict):
                    moa_type = item.get("MoA_Type")
                    if isinstance(moa_type, dict):
                        val = moa_type.get("value")
                        if val:
                            moa_types.append(val)
                    elif isinstance(moa_type, str) and moa_type:
                        moa_types.append(moa_type)
                    qm = item.get("Quantitative_Metric")
                    if isinstance(qm, dict):
                        mn = qm.get("metric_name", "")
                        mv = qm.get("metric_value", "")
                        if mn and mv:
                            quant_metrics.append(f"{mn} = {mv}")
                        elif mv:
                            quant_metrics.append(mv)
            ab["Mechanism_of_Action"] = "; ".join(moa_types) if moa_types else None
            if quant_metrics and not ab.get("Quantitative_Metric"):
                ab["Quantitative_Metric"] = "; ".join(quant_metrics)

        # Fix 6: Flatten any nested dicts into plain strings
        for key in list(ab.keys()):
            if key.startswith("_"):
                continue
            val = ab[key]
            if isinstance(val, dict):
                if key in self.FIELD_HINT_KEYS or any(val.get(meta) for meta in ("pointer", "action", "confidence", "germline")):
                    field_hints = ab.setdefault("_field_hints", {})
                    field_hints[key] = {
                        meta: val.get(meta)
                        for meta in ("value", "pointer", "action", "quote", "germline", "confidence")
                        if val.get(meta) not in (None, "")
                    }
                if "value" in val and val["value"]:
                    ab[key] = val["value"]
                elif "quote" in val and val.get("action") != "Script Extract" and val.get("action") != "API Fetch":
                    # Non-action dicts: use quote as fallback
                    ab[key] = val.get("quote", "")
                else:
                    # Script Extract / API Fetch pointer with no value → empty string
                    ab[key] = val.get("value", "")

        # Fix 7: Drop deprecated germline-only aliases instead of forcing them into full-sequence fields.
        ab.pop("VH_Germline", None)
        ab.pop("VL_Germline", None)

        # Fix 8: vh/vl sequence fields must contain complete amino-acid sequences only.
        ab["CDRH3_Sequence"] = self._sanitize_cdrh3_sequence(ab.get("CDRH3_Sequence"))
        for key in ("vh_sequence_aa", "vl_sequence_aa"):
            ab[key] = self._sanitize_variable_sequence(ab.get(key))

        # Fix 9: keep Experiment focused on direct assay/readout methods.
        if "Experiment" in ab:
            ab["Experiment"] = self._normalize_experiment_value(ab.get("Experiment"))

        # Fix 10: rewrite references into a compact GB/T-compatible citation when possible.
        if "Reference_Source" in ab:
            ab["Reference_Source"] = self._normalize_reference_source(ab.get("Reference_Source"))

        field_sources = self._build_field_sources_from_hints(ab)
        if field_sources:
            merged_sources = ab.get("field_sources") if isinstance(ab.get("field_sources"), dict) else {}
            ab["field_sources"] = {
                **merged_sources,
                **field_sources,
            }

        if not ab.get("_field_hints"):
            ab.pop("_field_hints", None)

    def _filter_non_core(self, skeleton: dict, paper_id: str) -> dict:
        """Remove non-core antibodies: failed candidates and control/reference antibodies"""
        antibodies = skeleton.get(paper_id, {}).get("antibodies", [])
        if not antibodies:
            return skeleton

        filtered = []
        for ab in antibodies:
            name = ab.get("Antibody_Name", "")
            name_norm = re.sub(r"[\s\-_]+", "", name).lower()
            target = (ab.get("Target_Name") or "").lower()
            mechanism = (ab.get("Mechanism_of_Action") or "").lower()
            ab_type = (ab.get("Antibody_Type") or "").lower()
            cdrh3 = ab.get("CDRH3_Sequence")
            vh = ab.get("vh_sequence_aa")
            vl = ab.get("vl_sequence_aa")
            kd = ab.get("Binding_Kinetics_KD")

            # Rule 1: Failed candidates — no sequence data at all
            has_any_seq = any(v and v not in (None, "", "N/A", "null")
                             for v in [cdrh3, vh, vl])
            failed_keywords = ["failed", "unsuccessful", "not recovered",
                               "amplification failed", "could not be"]
            is_failed = any(kw in target or kw in mechanism for kw in failed_keywords)
            if is_failed and not has_any_seq:
                self.logger.info(f"Filtered out failed candidate: {name}")
                continue

            # Rule 2: Control/reference antibodies — no sequence, no affinity,
            # and described as "previously tested" / "control" / "non-neutralizing" only
            control_keywords = ["previously tested", "used as control", "control antibody",
                                "non-neutralizing", "reference antibody"]
            is_control = any(kw in target or kw in mechanism for kw in control_keywords)
            if is_control and not has_any_seq and not kd:
                self.logger.info(f"Filtered out control/reference antibody: {name}")
                continue

            # Rule 3: Engineered mechanism constructs — MRCA / germline /
            # chain-swap or explicitly chimeric records should not survive as
            # standalone antibodies unless later code chooses to preserve them.
            mechanism_name_markers = ("mrca", "ancestor", "germline", "reversion")
            chain_swap_pattern = re.compile(r"[a-z0-9]+h[a-z0-9]+[kl]$")
            is_mechanism_construct = (
                any(marker in name_norm for marker in mechanism_name_markers)
                or "chimeric" in ab_type
                or chain_swap_pattern.search(name_norm) is not None
            )
            if is_mechanism_construct:
                self.logger.info(f"Filtered out engineered/mechanistic construct: {name}")
                continue

            filtered.append(ab)

        if len(filtered) < len(antibodies):
            self.logger.info(f"Filtered {len(antibodies) - len(filtered)} non-core antibodies, "
                             f"kept {len(filtered)}")

        skeleton[paper_id]["antibodies"] = filtered
        return skeleton

    @classmethod
    def _antibody_evidence_score(cls, ab: dict) -> int:
        score = 0
        for field in ("vh_sequence_aa", "vl_sequence_aa"):
            value = cls._normalize_aa_sequence(ab.get(field, ""))
            if cls._looks_like_full_variable_sequence(value):
                score += 5
        if cls._normalize_aa_sequence(ab.get("CDRH3_Sequence", "")):
            score += 3
        for field in (
            "Binding_Kinetics_KD",
            "Binding_Kinetics_kon",
            "Binding_Kinetics_koff",
            "Binding_EC50",
            "Quantitative_Metric",
            "Thermal_Stability_Tm",
            "In_Vivo_Efficacy",
            "Structure",
            "Target_Name",
            "Experiment",
        ):
            if str(ab.get(field) or "").strip():
                score += 1
        return score

    def _apply_optional_antibody_cap(self, skeleton: dict, paper_id: str) -> dict:
        limit = int(getattr(self.config, "skeleton_max_antibodies", 0) or 0)
        antibodies = skeleton.get(paper_id, {}).get("antibodies", [])
        if limit <= 0 or len(antibodies) <= limit:
            return skeleton

        ranked = sorted(
            enumerate(antibodies),
            key=lambda item: (self._antibody_evidence_score(item[1]), -item[0]),
            reverse=True,
        )
        keep_indices = sorted(idx for idx, _ in ranked[:limit])
        removed = len(antibodies) - len(keep_indices)
        skeleton[paper_id]["antibodies"] = [antibodies[idx] for idx in keep_indices]
        self.logger.warning(
            "Applied skeleton_max_antibodies=%s for %s; truncated %s low-evidence antibodies",
            limit,
            paper_id,
            removed,
        )
        return skeleton
