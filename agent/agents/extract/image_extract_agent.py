"""Phase 3 Track D: image-data extraction agent using a VLM."""

import asyncio
import json
import os
import re
import time
from pathlib import Path

from agents.base_agent import BaseAgent, AgentResult, AgentStatus
from tools.vlm_client import VLMClient
from tools.skill_loader import load_skill_prompt_set

_TRIAGE_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "../../prompts/vlm_triage_system.txt")
_EXTRACT_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "../../prompts/vlm_extract_system.txt")

RELEVANT_CATEGORIES = {"SEQUENCE_DATA", "KINETICS_DATA", "QUANTITATIVE_TABLE", "EFFICACY_DATA"}
SEQUENCE_FIELDS = {"CDRH3_Sequence", "vh_sequence_aa", "vl_sequence_aa"}
KINETIC_FIELDS = {
    "Binding_Kinetics_KD",
    "Binding_Kinetics_kon",
    "Binding_Kinetics_koff",
    "Binding_EC50",
    "Quantitative_Metric",
    "Thermal_Stability_Tm",
}
EFFICACY_FIELDS = {"In_Vivo_Efficacy"}
SEQUENCE_FIELD_NAMES = {"CDRH3_Sequence", "vh_sequence_aa", "vl_sequence_aa"}
SEQUENCE_IMAGE_KEYWORDS = ("sequence", "alignment", "cdr", "heavy chain", "light chain", "vh", "vl")
ANTIBODY_TOKEN_RE = re.compile(r"\b[A-Za-z0-9]+(?:[._-][A-Za-z0-9]+)*\b")
LONG_SEQUENCE_RE = re.compile(r"[A-Z-]{40,}")
ALIGNMENT_DIFF_RE = re.compile(r"[A-Z.\-]{40,}")
OCR_BLOCK_RE = re.compile(r"<!-- OCR extracted from .*?-->\s*(.*?)\s*<!-- end OCR -->", flags=re.DOTALL)
ANTIBODY_CLUSTER_MIN_NAMES = 4
NEIGHBOR_SEQUENCE_WINDOW = 2
MAX_ADJACENT_GROUP_SIZE = 3


class ImageExtractAgent(BaseAgent):
    """Extract antibody sequences and quantitative data from Markdown-referenced images."""

    def __init__(self, config, vlm: VLMClient | None = None):
        super().__init__("image_extract", config)
        self.vlm = vlm or VLMClient(config)
        prompts = load_skill_prompt_set(
            "figure-vlm-extraction",
            {
                "triage_prompt": _TRIAGE_PROMPT_PATH,
                "extract_prompt": _EXTRACT_PROMPT_PATH,
            },
        )
        self._triage_prompt = prompts["triage_prompt"]
        self._extract_prompt = prompts["extract_prompt"]
        self.top_k_images = getattr(config, "vlm_top_k_images", 5)
        self.parallel_limit = max(1, int(getattr(config, "vlm_concurrency", 10)))

    async def execute(self, context: dict) -> AgentResult:
        start = time.time()
        agent_span = self._start_span(context, "agent", self.name)

        md_text = context["markdown_text"]
        input_file = context["input_file"]
        base_dir = os.path.dirname(os.path.abspath(input_file))
        targets = self._normalize_targets(context.get("vlm_targets", []))
        force_sequence_images = bool(context.get("force_sequence_vlm"))
        allowed_categories = self._allowed_categories(targets, force_sequence_images=force_sequence_images)

        try:
            if not targets:
                elapsed = round(time.time() - start, 2)
                self._end_span(context, agent_span, status="success", target_antibodies=0)
                return AgentResult(
                    status=AgentStatus.SUCCESS,
                    data={"table_records": [], "note": "No targeted VLM gaps"},
                    metrics={"elapsed_seconds": elapsed, "images_found": 0},
                )

            # 1. Scan image references
            image_refs = self._scan_images(md_text, base_dir)
            self.logger.info(f"Image Extract: found {len(image_refs)} image references")

            if not image_refs:
                elapsed = round(time.time() - start, 2)
                self._end_span(context, agent_span, status="success", image_count=0)
                return AgentResult(
                    status=AgentStatus.SUCCESS,
                    data={"table_records": [], "note": "No images found"},
                    metrics={"elapsed_seconds": elapsed, "images_found": 0},
                )

            # 2. Filter by size
            image_refs = self._filter_by_size(image_refs)
            self.logger.info(f"Image Extract: {len(image_refs)} images after size filter")
            known_sequence_images = set(context.get("sequence_image_known_images", set()))
            if known_sequence_images:
                for ref in image_refs:
                    group_paths = ref.get("group_rel_paths") or []
                    if ref.get("rel_path") in known_sequence_images or any(path in known_sequence_images for path in group_paths):
                        ref["category"] = "SEQUENCE_DATA"

            # Cap at max
            if len(image_refs) > self.config.vlm_max_images_per_paper:
                image_refs = image_refs[: self.config.vlm_max_images_per_paper]

            image_refs = self._select_top_relevant_images(
                image_refs,
                targets,
                allowed_categories,
                known_sequence_images,
            )
            self.logger.info(
                "Image Extract: selected %d most relevant images (top_k=%d, parallel_limit=%d)",
                len(image_refs),
                self.top_k_images,
                self.parallel_limit,
            )
            self.vlm.set_parallel_limit(self.parallel_limit)

            # 3. Triage
            image_refs = await self._triage_images(image_refs, allowed_categories)
            self.logger.info(f"Image Extract: {len(image_refs)} relevant images after triage")

            if not image_refs:
                elapsed = round(time.time() - start, 2)
                self._end_span(context, agent_span, status="success", relevant_images=0)
                return AgentResult(
                    status=AgentStatus.SUCCESS,
                    data={"table_records": [], "note": "No relevant images after targeted triage"},
                    metrics={"elapsed_seconds": elapsed, "relevant_images": 0},
                )

            # 4. Extract data from relevant images
            self.vlm.set_parallel_limit(self.parallel_limit)
            all_records = await self._extract_from_images(image_refs, targets)
            elapsed = round(time.time() - start, 2)
            self.logger.info(f"Image Extract: {len(all_records)} records from {len(image_refs)} images in {elapsed}s")

            self._end_span(
                context, agent_span, status="success",
                relevant_images=len(image_refs),
                record_count=len(all_records),
                elapsed_seconds=elapsed,
            )
            return AgentResult(
                status=AgentStatus.SUCCESS,
                data={
                    "table_records": all_records,
                    "source": "vlm_image_extract",
                    "target_antibodies": [t["antibody_name"] for t in targets],
                },
                metrics={
                    "elapsed_seconds": elapsed,
                    "images_scanned": len(image_refs),
                    "records_extracted": len(all_records),
                    "target_antibodies": len(targets),
                    "vlm_stats": self.vlm.stats,
                },
            )
        except Exception as exc:
            self.logger.error(f"Image Extract failed: {exc}", exc_info=True)
            self._end_span(context, agent_span, status="error", error=str(exc))
            # Non-blocking: return empty result instead of raising
            elapsed = round(time.time() - start, 2)
            return AgentResult(
                status=AgentStatus.SUCCESS,
                data={"table_records": [], "error": str(exc)},
                metrics={"elapsed_seconds": elapsed},
            )

    @staticmethod
    def _normalize_targets(targets: list[dict]) -> list[dict]:
        normalized = []
        for target in targets:
            name = (target.get("antibody_name") or target.get("Antibody_Name") or "").strip()
            missing_fields = [f for f in target.get("missing_fields", []) if f]
            if name and missing_fields:
                normalized.append({"antibody_name": name, "missing_fields": sorted(set(missing_fields))})
        return normalized

    @classmethod
    def _allowed_categories(cls, targets: list[dict], force_sequence_images: bool = False) -> set[str]:
        missing_fields = {field for target in targets for field in target["missing_fields"]}
        wants_sequences = force_sequence_images or bool(missing_fields & SEQUENCE_FIELDS)
        wants_kinetics = bool(missing_fields & KINETIC_FIELDS)
        wants_efficacy = bool(missing_fields & EFFICACY_FIELDS)
        if wants_sequences and wants_kinetics and wants_efficacy:
            return set(RELEVANT_CATEGORIES)
        if wants_sequences and wants_kinetics:
            return {"SEQUENCE_DATA", "KINETICS_DATA", "QUANTITATIVE_TABLE"}
        if wants_sequences and wants_efficacy:
            return {"SEQUENCE_DATA", "EFFICACY_DATA"}
        if wants_kinetics and wants_efficacy:
            return {"KINETICS_DATA", "QUANTITATIVE_TABLE", "EFFICACY_DATA"}
        if wants_sequences:
            return {"SEQUENCE_DATA"}
        if wants_kinetics:
            return {"KINETICS_DATA", "QUANTITATIVE_TABLE"}
        if wants_efficacy:
            return {"EFFICACY_DATA", "QUANTITATIVE_TABLE"}
        return set(RELEVANT_CATEGORIES)

    def _scan_images(self, md_text: str, base_dir: str) -> list[dict]:
        """Extract ![...](images/xxx.jpg) references and local context from Markdown."""
        pattern = re.compile(r"!\[([^\]]*)\]\(([^)]*images/[^)]+)\)")
        results = []
        for m in pattern.finditer(md_text):
            alt_text = m.group(1)
            rel_path = m.group(2)
            abs_path = self._resolve_image_path(base_dir, rel_path, md_text, m.start())

            if not abs_path or not os.path.isfile(abs_path):
                continue

            # Keep a wider local window so adjacent sequence panels and OCR blocks stay visible.
            start = max(0, m.start() - 450)
            end = min(len(md_text), m.end() + 450)
            surrounding = md_text[start:end]

            results.append({
                "alt_text": alt_text,
                "rel_path": rel_path,
                "abs_path": abs_path,
                "context": surrounding,
                "_match_start": m.start(),
                "_match_end": m.end(),
            })
        return self._augment_with_adjacent_image_groups(results, md_text)

    @classmethod
    def _augment_with_adjacent_image_groups(cls, refs: list[dict], md_text: str) -> list[dict]:
        if len(refs) < 2:
            return refs
        grouped = list(refs)
        seen_keys = {tuple([ref.get("rel_path", "")]) for ref in refs}
        for start_idx in range(len(refs)):
            group = [refs[start_idx]]
            for next_idx in range(start_idx + 1, len(refs)):
                gap = md_text[group[-1]["_match_end"] : refs[next_idx]["_match_start"]]
                if not cls._is_lightweight_image_gap(gap):
                    break
                group.append(refs[next_idx])
                if len(group) > MAX_ADJACENT_GROUP_SIZE:
                    group.pop(0)
                if len(group) < 2:
                    continue
                key = tuple(ref["rel_path"] for ref in group)
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                grouped.append(cls._build_image_group_ref(group, md_text))
        return grouped

    @staticmethod
    def _build_image_group_ref(group: list[dict], md_text: str) -> dict:
        first = group[0]
        last = group[-1]
        start = max(0, first["_match_start"] - 450)
        end = min(len(md_text), last["_match_end"] + 450)
        group_rel_paths = [ref["rel_path"] for ref in group]
        group_abs_paths = [ref["abs_path"] for ref in group]
        return {
            "alt_text": first.get("alt_text", ""),
            "rel_path": " + ".join(group_rel_paths),
            "abs_path": group_abs_paths[0],
            "group_rel_paths": group_rel_paths,
            "group_abs_paths": group_abs_paths,
            "source_rel_path": group_rel_paths[0],
            "context": md_text[start:end],
            "is_image_group": True,
            "_match_start": first["_match_start"],
            "_match_end": last["_match_end"],
        }

    @staticmethod
    def _is_lightweight_image_gap(text: str) -> bool:
        cleaned = re.sub(r"<!--.*?-->", " ", text or "", flags=re.DOTALL)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if not cleaned:
            return True
        if re.fullmatch(r"[A-Za-z0-9](?:\s*[A-Za-z0-9]){0,2}", cleaned):
            return True
        if re.fullmatch(r"[\W_]+", cleaned):
            return True
        return False

    def _resolve_image_path(self, base_dir: str, rel_path: str, md_text: str, match_start: int) -> str | None:
        direct = os.path.normpath(os.path.join(base_dir, rel_path))
        if os.path.isfile(direct):
            return direct

        images_dir = os.path.join(base_dir, "images")
        basename = os.path.basename(rel_path)
        if os.path.isdir(images_dir):
            candidate = os.path.join(images_dir, basename)
            if os.path.isfile(candidate):
                return candidate

        # Some merged markdown files rewrite image refs but retain a section heading whose
        # hash still matches the real extracted image filename on disk.
        section_hash = self._nearest_section_hash(md_text, match_start)
        if section_hash and os.path.isdir(images_dir):
            for ext in (".jpg", ".jpeg", ".png", ".webp"):
                candidate = os.path.join(images_dir, f"{section_hash}{ext}")
                if os.path.isfile(candidate):
                    return candidate

        return None

    def _select_top_relevant_images(
        self,
        image_refs: list[dict],
        targets: list[dict],
        allowed_categories: set[str],
        known_sequence_images: set[str],
    ) -> list[dict]:
        sequence_evidence_indices = self._sequence_evidence_indices(
            image_refs,
            targets,
            allowed_categories,
            known_sequence_images,
        )
        scored = []
        for idx, ref in enumerate(image_refs):
            score = self._image_relevance_score(ref, targets, allowed_categories, known_sequence_images)
            score += self._neighbor_sequence_bonus(idx, sequence_evidence_indices)
            scored.append((score, idx, ref))
        scored.sort(key=lambda item: (-item[0], item[1], item[2]["rel_path"]))
        top_k = max(1, min(self.top_k_images, len(scored)))
        return [ref for _, _, ref in scored[:top_k]]

    @classmethod
    def _image_relevance_score(
        cls,
        ref: dict,
        targets: list[dict],
        allowed_categories: set[str],
        known_sequence_images: set[str],
    ) -> int:
        text = " ".join(
            [
                ref.get("alt_text", ""),
                ref.get("rel_path", ""),
                ref.get("context", ""),
                ref.get("category", ""),
            ]
        ).lower()
        score = 0

        if ref.get("rel_path") in known_sequence_images:
            score += 100

        preset_category = cls._normalize_category(ref.get("category", ""))
        if preset_category in allowed_categories:
            score += 40

        target_name_hits = 0
        for target in targets:
            name = (target.get("antibody_name") or "").strip().lower()
            if name and name in text:
                target_name_hits += 1
        score += min(target_name_hits, 3) * 25

        sequence_need = any(
            field in SEQUENCE_FIELDS for target in targets for field in target.get("missing_fields", [])
        )
        kinetics_need = any(
            field in KINETIC_FIELDS for target in targets for field in target.get("missing_fields", [])
        )
        efficacy_need = any(
            field in EFFICACY_FIELDS for target in targets for field in target.get("missing_fields", [])
        )

        if sequence_need:
            score += cls._keyword_score(
                text,
                SEQUENCE_IMAGE_KEYWORDS,
                weight=8,
            )
            antibody_cluster_count = cls._antibody_cluster_count(text)
            if antibody_cluster_count >= ANTIBODY_CLUSTER_MIN_NAMES:
                score += min(antibody_cluster_count, 6) * 5
            if cls._looks_like_alignment_ocr_block(text):
                score += 30
            elif antibody_cluster_count >= ANTIBODY_CLUSTER_MIN_NAMES and cls._contains_long_sequence(text):
                score += 18
        if kinetics_need:
            score += cls._keyword_score(
                text,
                ("kd", "kon", "koff", "ec50", "ic50", "bli", "spr", "kinetic", "affinity"),
                weight=7,
            )
        if efficacy_need:
            score += cls._keyword_score(
                text,
                ("survival", "challenge", "protection", "in vivo", "mouse", "mice"),
                weight=7,
            )

        if "fig" in text or "figure" in text:
            score += 2
        if "table" in text:
            score += 2
        return score

    @staticmethod
    def _keyword_score(text: str, keywords: tuple[str, ...], weight: int) -> int:
        return sum(weight for keyword in keywords if keyword in text)

    @classmethod
    def _sequence_evidence_indices(
        cls,
        image_refs: list[dict],
        targets: list[dict],
        allowed_categories: set[str],
        known_sequence_images: set[str],
    ) -> set[int]:
        indices = set()
        for idx, ref in enumerate(image_refs):
            if cls._has_sequence_evidence(ref, targets, allowed_categories, known_sequence_images):
                indices.add(idx)
        return indices

    @classmethod
    def _has_sequence_evidence(
        cls,
        ref: dict,
        targets: list[dict],
        allowed_categories: set[str],
        known_sequence_images: set[str],
    ) -> bool:
        text = " ".join(
            [
                ref.get("alt_text", ""),
                ref.get("rel_path", ""),
                ref.get("context", ""),
                ref.get("category", ""),
            ]
        ).lower()
        if ref.get("rel_path") in known_sequence_images:
            return True
        if cls._normalize_category(ref.get("category", "")) == "SEQUENCE_DATA" and "SEQUENCE_DATA" in allowed_categories:
            return True
        if any(keyword in text for keyword in SEQUENCE_IMAGE_KEYWORDS):
            return True
        if cls._looks_like_alignment_ocr_block(ref.get("context", "")):
            return True
        if cls._antibody_cluster_count(text) >= ANTIBODY_CLUSTER_MIN_NAMES and cls._contains_long_sequence(text):
            return True
        return cls._target_name_hits(text, targets) >= 2 and cls._contains_long_sequence(text)

    @classmethod
    def _neighbor_sequence_bonus(cls, idx: int, sequence_evidence_indices: set[int]) -> int:
        if not sequence_evidence_indices:
            return 0
        if idx in sequence_evidence_indices:
            return 12
        distance = min(abs(idx - candidate_idx) for candidate_idx in sequence_evidence_indices)
        if distance == 1:
            return 22
        if distance == 2:
            return 10
        return 0

    @classmethod
    def _target_name_hits(cls, text: str, targets: list[dict]) -> int:
        hits = 0
        for target in targets:
            name = (target.get("antibody_name") or "").strip().lower()
            if name and name in text:
                hits += 1
        return hits

    @classmethod
    def _antibody_cluster_count(cls, text: str) -> int:
        candidates = set()
        for match in ANTIBODY_TOKEN_RE.finditer(text or ""):
            token = match.group(0)
            if len(token) < 3:
                continue
            if not re.search(r"[A-Za-z]", token) or not re.search(r"\d", token):
                continue
            candidates.add(token.lower())
        return len(candidates)

    @staticmethod
    def _contains_long_sequence(text: str) -> bool:
        return bool(LONG_SEQUENCE_RE.search((text or "").upper()))

    @classmethod
    def _looks_like_alignment_ocr_block(cls, text: str) -> bool:
        for block in OCR_BLOCK_RE.findall(text or ""):
            lines = [line.strip() for line in block.splitlines() if line.strip()]
            if not lines:
                continue
            long_ref_seen = any(len(re.sub(r"[^A-Z-]", "", line.upper())) >= 60 and "." not in line for line in lines)
            diff_line_count = sum(1 for line in lines if cls._looks_like_alignment_diff_line(line))
            if long_ref_seen and diff_line_count >= ANTIBODY_CLUSTER_MIN_NAMES:
                return True
        return False

    @staticmethod
    def _looks_like_alignment_diff_line(line: str) -> bool:
        normalized = re.sub(r"[^A-Z.\-]", "", (line or "").upper())
        if len(normalized) < 40:
            return False
        if "." not in normalized:
            return False
        return bool(ALIGNMENT_DIFF_RE.fullmatch(normalized))

    @staticmethod
    def _nearest_section_hash(md_text: str, position: int) -> str | None:
        prefix = md_text[:position]
        matches = re.findall(r"(?m)^#\s+([0-9a-f]{32,64})\s*$", prefix)
        return matches[-1] if matches else None

    def _filter_by_size(self, image_refs: list[dict]) -> list[dict]:
        """Filter out small icons below the configured pixel threshold."""
        min_pixels = self.config.vlm_min_image_pixels
        filtered = []
        for ref in image_refs:
            try:
                from PIL import Image
                image_paths = ref.get("group_abs_paths") or [ref["abs_path"]]
                total_pixels = 0
                for image_path in image_paths:
                    with Image.open(image_path) as img:
                        w, h = img.size
                    total_pixels += w * h
                if total_pixels >= min_pixels:
                    filtered.append(ref)
                else:
                    self.logger.debug(f"Skipping small image {ref['rel_path']}: total_pixels={total_pixels}")
            except Exception:
                # If we can't read image dimensions, include it
                filtered.append(ref)
        return filtered

    async def _triage_images(self, image_refs: list[dict], allowed_categories: set[str]) -> list[dict]:
        """Classify images with concurrent VLM calls and keep only relevant categories."""
        async def _classify(ref: dict) -> dict | None:
            preset = self._normalize_category(ref.get("category", ""))
            if preset in allowed_categories:
                ref["category"] = preset
                return ref
            try:
                image_paths = ref.get("group_abs_paths") or [ref["abs_path"]]
                resp = await self.vlm.chat_with_images(
                    system=self._triage_prompt,
                    user_text=f"请分类这组图片。图片上下文：{ref['context'][:200]}",
                    image_paths=image_paths,
                    max_tokens=64,
                    temperature=0.0,
                )
                category = self._normalize_category(resp.content)
                ref["category"] = category
                if category in allowed_categories:
                    return ref
                self.logger.debug(f"Triage: {ref['rel_path']} -> {category} (skipped)")
                return None
            except Exception as e:
                self.logger.warning(f"Triage failed for {ref['rel_path']}: {e}")
                return None

        results = await asyncio.gather(*(_classify(ref) for ref in image_refs))
        return [r for r in results if r is not None]

    async def _extract_from_images(self, image_refs: list[dict], targets: list[dict]) -> list[dict]:
        """Extract data from relevant images with concurrent VLM calls."""
        valid_names = {target["antibody_name"].lower() for target in targets}

        async def _extract(ref: dict) -> list[dict]:
            try:
                category = ref.get("category", "UNKNOWN")
                user_text = self._build_extract_user_text(ref, category, targets)
                image_paths = ref.get("group_abs_paths") or [ref["abs_path"]]
                resp = await self.vlm.chat_with_images(
                    system=self._extract_prompt,
                    user_text=user_text,
                    image_paths=image_paths,
                    max_tokens=4096,
                    temperature=0.1,
                )
                records = self._parse_vlm_json(resp.content)
                # Tag source image
                for rec in records:
                    rec["_source_image"] = ref.get("source_rel_path", ref["rel_path"])
                    if ref.get("group_rel_paths"):
                        rec["_source_image_group"] = list(ref["group_rel_paths"])
                        rec["_source_multi_image"] = True
                    rec["_source_context"] = ref.get("context", "")[:600]
                    rec["_source_category"] = category
                return self._filter_records(records, ref, valid_names)
            except Exception as e:
                self.logger.warning(f"Extract failed for {ref['rel_path']}: {e}")
                return []

        all_records = []
        batches = await asyncio.gather(*(_extract(ref) for ref in image_refs))
        for batch in batches:
            all_records.extend(batch)
        return all_records

    @staticmethod
    def _normalize_category(raw: str) -> str:
        token = (raw or "").strip().split()[0] if (raw or "").strip() else "NOT_RELEVANT"
        canon = token.upper().replace('-', '_').strip('_')
        if canon.startswith("SEQUENCE"):
            return "SEQUENCE_DATA"
        if canon.startswith("KINETICS"):
            return "KINETICS_DATA"
        if canon.startswith("QUANTITATIVE"):
            return "QUANTITATIVE_TABLE"
        if canon.startswith("EFFICACY"):
            return "EFFICACY_DATA"
        if canon.startswith("NOT"):
            return "NOT_RELEVANT"
        return canon or "NOT_RELEVANT"

    @staticmethod
    def _filter_records(records: list[dict], ref: dict, valid_names: set[str]) -> list[dict]:
        context = (ref.get("context") or "").lower()
        filtered = []
        for rec in records:
            name = (rec.get("mAb") or rec.get("Antibody_Name") or "").strip()
            if name and valid_names and name.lower() not in valid_names:
                continue
            if rec.get("In_Vivo_Efficacy") and name and name.lower() not in context:
                continue
            filtered.append(rec)
        return filtered

    @staticmethod
    def _build_extract_user_text(ref: dict, category: str, targets: list[dict]) -> str:
        target_lines = []
        for target in targets[:20]:
            missing = ", ".join(target["missing_fields"])
            target_lines.append(f"- {target['antibody_name']}: missing [{missing}]")
        target_block = "\n".join(target_lines) if target_lines else "- none"
        return (
            f"这张图片被分类为 {category}。\n"
            "任务目标：只为当前 JSON 骨架中已有抗体补充缺失字段，不要输出无关抗体。\n"
            "如果图片里无法明确对应到下列抗体名称，则不要猜测。\n"
            f"已知抗体及缺失字段:\n{target_block}\n"
            f"图片上下文：{ref['context'][:300]}\n"
            "只输出图中清晰可见且能和已知抗体名称对应的数据。输出 JSON 数组。"
        )

    @staticmethod
    def _parse_vlm_json(text: str) -> list[dict]:
        """Parse a VLM-returned JSON array with defensive fallback handling."""
        cleaned = text.strip()
        # Remove markdown fences
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines)

        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict):
                return [parsed]
            return []
        except json.JSONDecodeError:
            pass

        # Try to find JSON array
        start = cleaned.find("[")
        end = cleaned.rfind("]")
        if start != -1 and end > start:
            try:
                parsed = json.loads(cleaned[start : end + 1])
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass

        # Try to find JSON object
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end > start:
            try:
                parsed = json.loads(cleaned[start : end + 1])
                if isinstance(parsed, dict):
                    return [parsed]
            except json.JSONDecodeError:
                pass

        return []
