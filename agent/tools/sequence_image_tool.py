"""Image-only sequence extraction tool backed by a Responses-compatible vision API."""

import asyncio
import base64
import json
import logging
import mimetypes
import os
import re
from pathlib import Path

import httpx

from tools.skill_loader import load_skill_prompt

logger = logging.getLogger(__name__)


class SequenceImageTool:
    """Use a multimodal model to extract antibody sequences from sequence-alignment images."""

    ALIGNMENT_REF_MIN_LEN = 60
    ALIGNMENT_DIFF_MIN_RATIO = 0.7
    ANTIBODY_CLUSTER_MIN_NAMES = 4
    MAX_ADJACENT_GROUP_SIZE = 3
    LOW_RECALL_RECORD_THRESHOLD = 1
    OCR_NORMALIZATION_MAP = str.maketrans({
        "0": "Q",
        "1": "I",
        "O": "Q",
    })
    SEQUENCE_CONTEXT_KEYWORDS = (
        "sequence alignment",
        "sequence",
        "alignment",
        "h chain",
        "l chain",
        "heavy chain",
        "light chain",
        "cdr",
    )
    OCR_SEQUENCE_KEYWORDS = (
        "heavy chain",
        "light chain",
        "h chain",
        "l chain",
        "cdr",
        "germline",
        "imgt",
        "shm",
        "fr1",
        "fr2",
        "fr3",
        "fr4",
    )
    OCR_NON_SEQUENCE_KEYWORDS = (
        "anti-strep",
        "mw (kda)",
        "pngase",
        "od450",
        "western blot",
        "fluorescence",
        "microscopy",
        "overlay",
        "dapi",
    )
    NAME_LINE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{1,31}$")
    SEQUENCE_RE = re.compile(r"[A-Z-]{20,}")
    ANTIBODY_TOKEN_RE = re.compile(r"\b[A-Za-z0-9]+(?:[._-][A-Za-z0-9]+)*\b")
    VARIANT_NAME_RE = re.compile(r"\b[A-Za-z0-9]+-[HL]\d+\b")
    COMBO_NAME_RE = re.compile(r"\bH\d+L\d+\b")

    def __init__(self, config):
        self.config = config
        self.api_base = (config.sequence_vlm_api_base or config.llm_api_base).rstrip("/")
        self.api_key = config.sequence_vlm_api_key or config.llm_api_key
        self.model = config.sequence_vlm_model
        self.timeout = config.sequence_vlm_timeout
        self.retry_count = getattr(config, "sequence_vlm_retry_count", 5)
        self.max_images = config.sequence_vlm_max_images
        self.top_k_images = getattr(config, "sequence_vlm_top_k_images", 5)
        self.max_output_tokens = config.sequence_vlm_max_output_tokens
        self.parallel_limit = max(1, int(getattr(config, "sequence_vlm_concurrency", 1)))
        self._semaphore = asyncio.Semaphore(self.parallel_limit)
        prompt_path = Path(__file__).resolve().parent.parent / "prompts" / "sequence_image_extract_system.txt"
        self.system_prompt = load_skill_prompt(
            "sequence-image-extraction",
            "system_prompt",
            prompt_path,
        )
        self._total_calls = 0
        self._total_tokens = 0

    async def extract_from_markdown(
        self,
        markdown_text: str,
        input_file: str,
        seed_names: list[str] | None = None,
    ) -> dict:
        base_dir = os.path.dirname(os.path.abspath(input_file))
        image_refs = self._scan_images(markdown_text, base_dir)
        candidates = [
            ref
            for ref in image_refs
            if self._looks_like_sequence_image(ref["context"], ref.get("ocr_text", ""))
        ]
        if len(candidates) > self.max_images:
            candidates = candidates[: self.max_images]
        candidates = self._select_top_relevant_candidates(candidates, seed_names or [])
        candidates = self._expand_candidate_crop_variants(candidates)

        if not candidates:
            return {
                "table_records": [],
                "images_considered": 0,
                "images_used": 0,
                "note": "No sequence-image candidates found",
                "source": "sequence_image_tool",
            }

        self._semaphore = asyncio.Semaphore(self.parallel_limit)
        logger.info(
            "Sequence image tool: selected %d candidate images (top_k=%d, parallel_limit=%d, retries=%d)",
            len(candidates),
            self.top_k_images,
            self.parallel_limit,
            self.retry_count,
        )
        results = await asyncio.gather(
            *(self._extract_one_image(ref, seed_names or []) for ref in candidates)
        )
        retry_updates = await self._run_targeted_retries(candidates, results, seed_names or [])
        for idx, extra_records in retry_updates.items():
            if idx < 0 or idx >= len(results) or not extra_records:
                continue
            results[idx].extend(extra_records)

        merged = {}
        used = 0
        for ref, records in zip(candidates, results):
            if records:
                used += 1
            for record in records:
                name = (record.get("mAb") or "").strip()
                if not name:
                    continue
                existing = merged.setdefault(name, {"mAb": name})
                for field in ("VH_sequence", "VL_sequence", "CDRH3"):
                    value = self._clean_sequence(record.get(field, ""))
                    if value and len(value) > len(existing.get(field, "")):
                        existing[field] = value
                existing["_source_image"] = ref.get("source_rel_path", ref["rel_path"])
                if ref.get("group_rel_paths"):
                    existing["_source_image_group"] = list(ref["group_rel_paths"])
                    existing["_source_multi_image"] = True
                if ref.get("crop_image_name"):
                    existing["_source_crop_image"] = ref["crop_image_name"]
                existing["_source_context"] = ref["context"][:600]
                existing["_source_category"] = "SEQUENCE_DATA"
                existing["_discovered_from_sequence_image"] = True

        return {
            "table_records": list(merged.values()),
            "images_considered": len(candidates),
            "images_used": used,
            "note": "Sequence-image extraction completed",
            "source": "sequence_image_tool",
            "seed_names": sorted(set(seed_names or [])),
        }

    def _select_top_relevant_candidates(self, candidates: list[dict], seed_names: list[str]) -> list[dict]:
        scored = []
        for idx, ref in enumerate(candidates):
            scored.append((self._candidate_relevance_score(ref, seed_names), idx, ref))
        scored.sort(key=lambda item: (-item[0], item[1], item[2]["rel_path"]))
        top_k = max(1, min(self.top_k_images, len(scored)))
        return [ref for _, _, ref in scored[:top_k]]

    def _candidate_relevance_score(self, ref: dict, seed_names: list[str]) -> int:
        text = " ".join(
            [
                ref.get("rel_path", ""),
                ref.get("context", ""),
            ]
        ).lower()
        score = 0

        for keyword in self.SEQUENCE_CONTEXT_KEYWORDS:
            if keyword in text:
                score += 8
        if "fig" in text or "figure" in text:
            score += 2
        if "supp" in text or "supplement" in text:
            score += 2

        seed_hits = 0
        for name in seed_names:
            normalized = (name or "").strip().lower()
            if normalized and normalized in text:
                seed_hits += 1
        score += min(seed_hits, 3) * 20
        score += max(0, len(ref.get("group_rel_paths", [])) - 1) * 10

        score += min(len(self.SEQUENCE_RE.findall(text)), 3) * 6
        return score

    def _expand_candidate_crop_variants(self, candidates: list[dict]) -> list[dict]:
        expanded = []
        seen_keys = set()
        for ref in candidates:
            for variant in self._candidate_crop_variants(ref):
                path = variant.get("abs_path")
                unique_key = tuple(variant.get("group_rel_paths") or [variant.get("rel_path", path)])
                if not path or unique_key in seen_keys:
                    continue
                seen_keys.add(unique_key)
                expanded.append(variant)
        return expanded

    def _candidate_crop_variants(self, ref: dict) -> list[dict]:
        variants = [ref]
        if ref.get("group_abs_paths"):
            return variants
        crop_dir = self._ocr_crop_dir(ref.get("abs_path", ""))
        if not crop_dir:
            return variants

        crop_paths = sorted(
            path for path in crop_dir.iterdir()
            if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
        )
        for crop_path in crop_paths:
            variant = dict(ref)
            variant["abs_path"] = str(crop_path)
            variant["source_rel_path"] = ref["rel_path"]
            variant["crop_image_name"] = crop_path.name
            variant["rel_path"] = f"{ref['rel_path']}#crop:{crop_path.name}"
            variants.append(variant)
        return variants

    @staticmethod
    def _ocr_crop_dir(image_path: str) -> Path | None:
        if not image_path:
            return None
        image_file = Path(image_path)
        image_hash = image_file.stem
        paper_dir = image_file.parent.parent
        crop_dir = paper_dir / "images_ocr" / image_hash / "vlm" / "images"
        if crop_dir.is_dir():
            return crop_dir
        return None

    async def _extract_one_image(self, ref: dict, seed_names: list[str]) -> list[dict]:
        if self._ocr_strongly_rejects_sequence(ref.get("ocr_text", "")) and not self._ocr_supports_sequence(ref.get("ocr_text", "")):
            return []
        local_records = self._extract_alignment_ocr_records(ref["context"])
        if local_records:
            return local_records

        user_text = self._build_user_text(ref["context"], seed_names)
        return await self._extract_records_with_user_text(ref, user_text)

    async def _extract_records_with_user_text(self, ref: dict, user_text: str) -> list[dict]:
        image_paths = list(ref.get("group_abs_paths") or [ref["abs_path"]])
        text = await self._call_responses_api(image_paths, user_text)
        records = self._parse_records(text)
        return self._normalize_records(records)

    def _normalize_records(self, records: list[dict]) -> list[dict]:
        cleaned = []
        for record in records:
            name = (record.get("mAb") or "").strip()
            vh = self._clean_sequence(record.get("VH_sequence", ""))
            vl = self._clean_sequence(record.get("VL_sequence", ""))
            cdrh3 = self._clean_sequence(record.get("CDRH3", ""))
            if not name or not (vh or vl or cdrh3):
                continue
            cleaned.append(
                {
                    "mAb": name,
                    "VH_sequence": vh,
                    "VL_sequence": vl,
                    "CDRH3": cdrh3,
                }
            )
        return cleaned

    @staticmethod
    def _source_group_key(ref: dict) -> str:
        return str(ref.get("source_rel_path") or ref.get("rel_path") or ref.get("abs_path") or "")

    @classmethod
    def _unique_record_names(cls, records: list[dict]) -> list[str]:
        names = []
        seen = set()
        for record in records:
            name = str(record.get("mAb") or "").strip()
            if not name:
                continue
            norm = name.lower()
            if norm in seen:
                continue
            seen.add(norm)
            names.append(name)
        return names

    @classmethod
    def _extract_expected_antibody_names(cls, context: str, seed_names: list[str]) -> list[str]:
        text = str(context or "")
        expected = []
        seen = set()

        for match in cls.VARIANT_NAME_RE.finditer(text):
            token = match.group(0).strip()
            lower = token.lower()
            if lower not in seen:
                seen.add(lower)
                expected.append(token)

        for match in cls.COMBO_NAME_RE.finditer(text):
            token = match.group(0).strip()
            lower = token.lower()
            if lower not in seen:
                seen.add(lower)
                expected.append(token)

        lower_text = text.lower()
        for seed in seed_names:
            token = str(seed or "").strip()
            if not token:
                continue
            if token.lower() not in lower_text:
                continue
            lower = token.lower()
            if lower not in seen:
                seen.add(lower)
                expected.append(token)

        return expected

    @classmethod
    def _has_alignment_retry_signal(cls, refs: list[dict], expected_names: list[str], observed_names: list[str]) -> bool:
        if not refs:
            return False
        context = " ".join(str(ref.get("context") or "") for ref in refs).lower()
        has_alignment_signal = (
            "alignment" in context
            or "variant sequence" in context
            or "variant sequences" in context
            or "humanized variant" in context
            or "humanized variants" in context
            or cls._looks_like_alignment_ocr_block(" ".join(str(ref.get("context") or "") for ref in refs))
        )
        has_multiple_crops = sum(1 for ref in refs if ref.get("crop_image_name")) >= 2
        missing_expected = [
            name for name in expected_names
            if name.lower() not in {observed.lower() for observed in observed_names}
        ]
        sparse_output = len(observed_names) <= cls.LOW_RECALL_RECORD_THRESHOLD
        return has_alignment_signal and (
            sparse_output and has_multiple_crops
            or len(missing_expected) >= 2
        )

    @staticmethod
    def _prioritize_retry_indices(refs: list[dict], indices: list[int]) -> list[int]:
        keyed = sorted(
            zip(indices, refs),
            key=lambda item: (
                0 if item[1].get("crop_image_name") else 1,
                len(item[1].get("group_rel_paths") or []),
                item[1].get("rel_path", ""),
            ),
        )
        return [idx for idx, _ in keyed]

    @staticmethod
    def _build_targeted_user_text(context: str, seed_names: list[str], focus_names: list[str]) -> str:
        seed_block = ", ".join(seed_names[:20]) if seed_names else "none"
        focus_block = ", ".join(focus_names[:20]) if focus_names else "none"
        return (
            "上一次抽取结果明显不完整。请重新读取这张图，并穷举所有真正可见的抗体/variant 行。\n"
            "如果这是一张被裁剪出的 heavy-chain 或 light-chain alignment panel，请逐行输出每个 donor/variant 名称，不要只输出 parent 抗体。\n"
            "如果图中能看到 1C8-H0/H1/H2/H3/H4、1C8-L0/L1/L2/L3、H3L1/H4L2 这类名字，请分别作为独立对象输出。\n"
            "不要把多行 donor 合并成一个结果，也不要因为序列不完整就省略可见名字；能可靠转写多少就转写多少。\n"
            "若只看到 heavy-chain panel，就只填 VH_sequence/CDRH3；若只看到 light-chain panel，就只填 VL_sequence。\n"
            "如果图中使用参考行 + 差异位点 + '.'，请尽量按可见参考关系还原完整 variable-region 序列；若仍无法可靠还原，就保留可见部分，不要猜测。\n"
            f"优先检查这些可能缺失的名称：{focus_block}\n"
            f"已知可能相关的抗体名：{seed_block}\n"
            f"上下文：{context[:900]}\n"
            "只输出 JSON 数组。"
        )

    async def _run_targeted_retries(
        self,
        candidates: list[dict],
        results: list[list[dict]],
        seed_names: list[str],
    ) -> dict[int, list[dict]]:
        updates: dict[int, list[dict]] = {}
        grouped_indices: dict[str, list[int]] = {}
        for idx, ref in enumerate(candidates):
            grouped_indices.setdefault(self._source_group_key(ref), []).append(idx)

        for indices in grouped_indices.values():
            refs = [candidates[idx] for idx in indices]
            observed_records = []
            for idx in indices:
                observed_records.extend(results[idx])
            observed_names = self._unique_record_names(observed_records)
            expected_names = self._extract_expected_antibody_names(
                " ".join(str(ref.get("context") or "") for ref in refs),
                seed_names,
            )
            if not self._has_alignment_retry_signal(refs, expected_names, observed_names):
                continue

            focus_names = [
                name for name in expected_names
                if name.lower() not in {observed.lower() for observed in observed_names}
            ]
            prioritized = self._prioritize_retry_indices(refs, indices)
            for idx in prioritized:
                ref = candidates[idx]
                user_text = self._build_targeted_user_text(ref.get("context", ""), seed_names, focus_names)
                extra_records = await self._extract_records_with_user_text(ref, user_text)
                if not extra_records:
                    continue
                updates.setdefault(idx, []).extend(extra_records)
                observed_names = self._unique_record_names(observed_records + extra_records)
                if focus_names and all(
                    name.lower() in {observed.lower() for observed in observed_names}
                    for name in focus_names
                ):
                    break

        return updates

    async def _call_responses_api(self, image_paths: list[str], user_text: str) -> str:
        image_paths = [path for path in image_paths if path]
        if not image_paths:
            return ""
        content = [{"type": "input_text", "text": user_text}]
        for image_path in image_paths:
            content.append({"type": "input_image", "image_url": self._image_to_data_uri(image_path)})
        payload = {
            "model": self.model,
            "input": [
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": self.system_prompt}],
                },
                {
                    "role": "user",
                    "content": content,
                },
            ],
            "max_output_tokens": self.max_output_tokens,
            "temperature": 0.0,
            "text": {"format": {"type": "text"}},
        }
        headers = {
            "Authorization": self._auth_header_value(self.api_key),
            "Content-Type": "application/json",
        }

        async with self._semaphore:
            for attempt in range(self.retry_count):
                try:
                    async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
                        response = await client.post(
                            f"{self.api_base}/v1/responses",
                            headers=headers,
                            json=payload,
                        )
                        if response.status_code == 429:
                            wait = 2 ** (attempt + 1)
                            logger.warning(
                                "Sequence image rate limited for %s, retrying in %ss (%s/%s)",
                                self._image_batch_label(image_paths),
                                wait,
                                attempt + 1,
                                self.retry_count,
                            )
                            await asyncio.sleep(wait)
                            continue
                        response.raise_for_status()
                        body = response.json()
                    break
                except httpx.HTTPStatusError as e:
                    if attempt < self.retry_count - 1:
                        wait = 2 ** (attempt + 1)
                        logger.warning(
                            "Sequence image HTTP %s for %s, retry in %ss (%s/%s)",
                            e.response.status_code,
                            self._image_batch_label(image_paths),
                            wait,
                            attempt + 1,
                            self.retry_count,
                        )
                        await asyncio.sleep(wait)
                        continue
                    raise
                except (httpx.ConnectError, httpx.ReadTimeout) as e:
                    if attempt < self.retry_count - 1:
                        wait = 2 ** (attempt + 1)
                        logger.warning(
                            "Sequence image %s for %s: %r, retry in %ss (%s/%s)",
                            type(e).__name__,
                            self._image_batch_label(image_paths),
                            e,
                            wait,
                            attempt + 1,
                            self.retry_count,
                        )
                        await asyncio.sleep(wait)
                        continue
                    raise
            else:
                raise RuntimeError(
                    f"Sequence image call failed after {self.retry_count} retries for {self._image_batch_label(image_paths)}"
                )

        usage = body.get("usage", {})
        self._total_calls += 1
        self._total_tokens += usage.get("total_tokens", 0)
        return self._extract_output_text(body)

    @staticmethod
    def _auth_header_value(api_key: str) -> str:
        if api_key.startswith("Bearer "):
            return api_key
        return f"Bearer {api_key}"

    @staticmethod
    def _image_to_data_uri(path: str) -> str:
        data = Path(path).read_bytes()
        mime, _ = mimetypes.guess_type(path)
        if not mime:
            mime = "image/jpeg"
        b64 = base64.b64encode(data).decode("utf-8")
        return f"data:{mime};base64,{b64}"

    @staticmethod
    def _extract_output_text(body: dict) -> str:
        parts = []
        for item in body.get("output", []):
            if item.get("type") != "message":
                continue
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    parts.append(content.get("text", ""))
        return "\n".join(part for part in parts if part).strip()

    @staticmethod
    def _image_batch_label(image_paths: list[str]) -> str:
        if not image_paths:
            return "no-image"
        if len(image_paths) == 1:
            return Path(image_paths[0]).name
        names = [Path(path).name for path in image_paths[:3]]
        suffix = "..." if len(image_paths) > 3 else ""
        return ", ".join(names) + suffix

    def _scan_images(self, md_text: str, base_dir: str) -> list[dict]:
        pattern = re.compile(r"!\[([^\]]*)\]\(([^)]*images/[^)]+)\)")
        refs = []
        for match in pattern.finditer(md_text):
            rel_path = match.group(2)
            abs_path = self._resolve_image_path(base_dir, rel_path, md_text, match.start())
            if not abs_path or not os.path.isfile(abs_path):
                continue
            start = max(0, match.start() - 400)
            end = min(len(md_text), match.end() + 800)
            ocr_text = self._extract_image_ocr_text(md_text, os.path.basename(rel_path), match.end())
            refs.append(
                {
                    "rel_path": rel_path,
                    "abs_path": abs_path,
                    "context": md_text[start:end],
                    "ocr_text": ocr_text,
                    "_match_start": match.start(),
                    "_match_end": match.end(),
                }
            )
        return self._augment_with_adjacent_image_groups(refs, md_text)

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
                if len(group) > cls.MAX_ADJACENT_GROUP_SIZE:
                    group.pop(0)
                if len(group) < 2:
                    continue
                key = tuple(ref["rel_path"] for ref in group)
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                grouped.append(cls._build_image_group_ref(group, md_text))
        return grouped

    @classmethod
    def _build_image_group_ref(cls, group: list[dict], md_text: str) -> dict:
        first = group[0]
        last = group[-1]
        start = max(0, first["_match_start"] - 400)
        end = min(len(md_text), last["_match_end"] + 800)
        ocr_parts = [str(ref.get("ocr_text") or "").strip() for ref in group]
        group_rel_paths = [ref["rel_path"] for ref in group]
        group_abs_paths = [ref["abs_path"] for ref in group]
        return {
            "rel_path": " + ".join(group_rel_paths),
            "abs_path": group_abs_paths[0],
            "source_rel_path": group_rel_paths[0],
            "context": md_text[start:end],
            "ocr_text": "\n\n".join(part for part in ocr_parts if part),
            "group_rel_paths": group_rel_paths,
            "group_abs_paths": group_abs_paths,
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

    @staticmethod
    def _extract_image_ocr_text(md_text: str, image_name: str, search_start: int) -> str:
        if not image_name:
            return ""
        pattern = re.compile(
            rf"<!-- OCR extracted from {re.escape(image_name)} -->\s*(.*?)\s*<!-- end OCR -->",
            flags=re.DOTALL,
        )
        local_window = md_text[search_start : min(len(md_text), search_start + 5000)]
        match = pattern.search(local_window)
        if match:
            return match.group(1).strip()
        match = pattern.search(md_text)
        return match.group(1).strip() if match else ""

    def _resolve_image_path(self, base_dir: str, rel_path: str, md_text: str, match_start: int) -> str | None:
        direct = os.path.normpath(os.path.join(base_dir, rel_path))
        if os.path.isfile(direct):
            return direct

        images_dir = os.path.join(base_dir, "images")
        basename = os.path.basename(rel_path)
        fallback = os.path.join(images_dir, basename)
        if os.path.isfile(fallback):
            return fallback

        section_hash = self._nearest_section_hash(md_text, match_start)
        if section_hash and os.path.isdir(images_dir):
            for ext in (".jpg", ".jpeg", ".png", ".webp"):
                candidate = os.path.join(images_dir, f"{section_hash}{ext}")
                if os.path.isfile(candidate):
                    return candidate
        return None

    @staticmethod
    def _nearest_section_hash(md_text: str, position: int) -> str | None:
        prefix = md_text[:position]
        matches = re.findall(r"(?m)^#\s+([0-9a-f]{32,64})\s*$", prefix)
        return matches[-1] if matches else None

    def _looks_like_sequence_image(self, context: str, ocr_text: str = "") -> bool:
        context_l = (context or "").lower()
        ocr_l = (ocr_text or "").lower()
        if ocr_l:
            if self._ocr_strongly_rejects_sequence(ocr_l) and not self._ocr_supports_sequence(ocr_text):
                return False
            if self._ocr_supports_sequence(ocr_text):
                return True
        if any(keyword in context_l for keyword in self.SEQUENCE_CONTEXT_KEYWORDS):
            return True
        if self._looks_like_alignment_ocr_block(context):
            return True
        if self._has_antibody_name_cluster(context) and self.SEQUENCE_RE.findall(context.upper()):
            return True
        return False

    def _ocr_supports_sequence(self, ocr_text: str) -> bool:
        ocr_l = (ocr_text or "").lower()
        if not ocr_l:
            return False
        if any(keyword in ocr_l for keyword in self.OCR_SEQUENCE_KEYWORDS):
            return True
        if self._looks_like_alignment_ocr_block(ocr_text):
            return True
        if self._has_antibody_name_cluster(ocr_text) and self.SEQUENCE_RE.findall(ocr_text.upper()):
            return True
        return False

    def _ocr_strongly_rejects_sequence(self, ocr_text: str) -> bool:
        ocr_l = (ocr_text or "").lower()
        return any(keyword in ocr_l for keyword in self.OCR_NON_SEQUENCE_KEYWORDS)

    @classmethod
    def _extract_ocr_blocks(cls, context: str) -> list[str]:
        return re.findall(
            r"<!-- OCR extracted from .*?-->\s*(.*?)\s*<!-- end OCR -->",
            context or "",
            flags=re.DOTALL,
        )

    @classmethod
    def _normalize_alignment_text(cls, value: str) -> str:
        text = re.sub(r"\s+", "", str(value or "")).upper()
        return text.translate(cls.OCR_NORMALIZATION_MAP)

    @classmethod
    def _normalize_reference_sequence(cls, value: str) -> str:
        text = cls._normalize_alignment_text(value)
        return re.sub(r"[^A-Z-]", "", text)

    @classmethod
    def _normalize_diff_line(cls, value: str) -> str:
        text = cls._normalize_alignment_text(value)
        return re.sub(r"[^A-Z.\-]", "", text)

    @classmethod
    def _looks_like_antibody_label(cls, line: str) -> bool:
        line = (line or "").strip()
        if not line or len(line) < 2:
            return False
        if len(line) == 1 and line.isalpha():
            return False
        if not cls.NAME_LINE_RE.match(line):
            return False
        if cls.SEQUENCE_RE.fullmatch(line.upper()):
            return False
        normalized = line.lower()
        stopwords = {
            "figure",
            "related",
            "binding",
            "heavy",
            "light",
            "chain",
            "hcdr1",
            "hcdr2",
            "hcdr3",
            "lcdr1",
            "lcdr2",
            "lcdr3",
        }
        return normalized not in stopwords

    @classmethod
    def _find_reference_line_index(cls, lines: list[str]) -> int:
        for idx, line in enumerate(lines):
            reference = cls._normalize_reference_sequence(line)
            if len(reference) < cls.ALIGNMENT_REF_MIN_LEN:
                continue
            if "." in line:
                continue
            if set(reference) <= set("ABCDEFGHIJKLMNOPQRSTUVWXYZ-"):
                return idx
        return -1

    @classmethod
    def _looks_like_alignment_diff_line(cls, line: str, reference_len: int) -> bool:
        diff = cls._normalize_diff_line(line)
        if len(diff) < max(20, int(reference_len * cls.ALIGNMENT_DIFF_MIN_RATIO)):
            return False
        if not any(ch == "." for ch in diff):
            return False
        return True

    @classmethod
    def _reconstruct_alignment_sequence(cls, reference: str, diff_line: str) -> str:
        reference = cls._normalize_reference_sequence(reference)
        diff = cls._normalize_diff_line(diff_line)
        if not reference or not cls._looks_like_alignment_diff_line(diff_line, len(reference)):
            return ""

        rebuilt = []
        usable = min(len(reference), len(diff))
        for idx in range(usable):
            ch = diff[idx]
            if ch == ".":
                rebuilt.append(reference[idx])
            elif ch == "-":
                rebuilt.append("-")
            elif ch.isalpha():
                rebuilt.append(ch)
            else:
                return ""

        if usable < len(reference):
            rebuilt.extend(reference[usable:])

        result = "".join(rebuilt)
        if len(result) != len(reference):
            return ""
        return result

    @classmethod
    def _infer_alignment_field(cls, reference: str, context: str) -> str:
        seq = cls._normalize_reference_sequence(reference)
        context_l = (context or "").lower()
        if (
            seq.startswith(("QVQ", "EVQ", "QMQ", "VQL"))
            or "hcdr" in context_l
            or "heavy chain" in context_l
        ):
            return "VH_sequence"
        if (
            seq.startswith(("DIV", "EIV", "DIQ", "IVL"))
            or "lcdr" in context_l
            or "light chain" in context_l
        ):
            return "VL_sequence"
        if "WGQGT" in seq:
            return "VH_sequence"
        if "FGQGTK" in seq or "FGGGTK" in seq:
            return "VL_sequence"
        return ""

    @classmethod
    def _parse_alignment_ocr_block(cls, block: str, context: str) -> list[dict]:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        ref_idx = cls._find_reference_line_index(lines)
        direct_records = cls._parse_name_sequence_lines(lines, context)
        if ref_idx <= 0:
            return direct_records

        reference = cls._normalize_reference_sequence(lines[ref_idx])
        field = cls._infer_alignment_field(reference, context)
        if field not in {"VH_sequence", "VL_sequence"}:
            return direct_records

        names = [line for line in lines[:ref_idx] if cls._looks_like_antibody_label(line)]
        diff_lines = [line for line in lines[ref_idx + 1 :] if cls._looks_like_alignment_diff_line(line, len(reference))]
        min_cluster_size = cls.ANTIBODY_CLUSTER_MIN_NAMES
        context_l = (context or "").lower()
        if "variant sequence" in context_l or "variant sequences" in context_l or "humanized" in context_l:
            min_cluster_size = 2
        if len(names) < min_cluster_size or len(diff_lines) < min_cluster_size:
            return direct_records if len(direct_records) >= 2 else []

        records = []
        for name, diff_line in zip(names, diff_lines):
            rebuilt = cls._reconstruct_alignment_sequence(reference, diff_line)
            cleaned = cls._clean_sequence(rebuilt)
            if not cleaned or len(cleaned) < cls.ALIGNMENT_REF_MIN_LEN:
                continue
            records.append({"mAb": name, field: cleaned})
        return records

    @classmethod
    def _parse_name_sequence_lines(cls, lines: list[str], context: str) -> list[dict]:
        records = []
        idx = 0
        while idx < len(lines) - 1:
            name = lines[idx].strip()
            candidate = cls._normalize_reference_sequence(lines[idx + 1])
            if not cls._looks_like_antibody_label(name):
                idx += 1
                continue
            if len(candidate) < cls.ALIGNMENT_REF_MIN_LEN:
                idx += 1
                continue
            field = cls._infer_alignment_field(candidate, context)
            if field not in {"VH_sequence", "VL_sequence"}:
                idx += 1
                continue
            records.append({"mAb": name, field: cls._clean_sequence(candidate)})
            idx += 2
        return records

    @classmethod
    def _extract_alignment_ocr_records(cls, context: str) -> list[dict]:
        merged: dict[str, dict] = {}
        for block in cls._extract_ocr_blocks(context):
            for record in cls._parse_alignment_ocr_block(block, context):
                name = (record.get("mAb") or "").strip()
                if not name:
                    continue
                existing = merged.setdefault(name, {"mAb": name})
                for field in ("VH_sequence", "VL_sequence"):
                    value = cls._clean_sequence(record.get(field, ""))
                    if value and len(value) > len(existing.get(field, "")):
                        existing[field] = value
        return list(merged.values())

    @classmethod
    def _looks_like_alignment_ocr_block(cls, context: str) -> bool:
        for block in cls._extract_ocr_blocks(context):
            lines = [line.strip() for line in block.splitlines() if line.strip()]
            ref_idx = cls._find_reference_line_index(lines)
            if ref_idx <= 0:
                continue
            reference = cls._normalize_reference_sequence(lines[ref_idx])
            if len(reference) < cls.ALIGNMENT_REF_MIN_LEN:
                continue
            names = [line for line in lines[:ref_idx] if cls._looks_like_antibody_label(line)]
            diff_lines = [
                line for line in lines[ref_idx + 1 :] if cls._looks_like_alignment_diff_line(line, len(reference))
            ]
            if len(names) >= cls.ANTIBODY_CLUSTER_MIN_NAMES and len(diff_lines) >= cls.ANTIBODY_CLUSTER_MIN_NAMES:
                return True
        return False

    @classmethod
    def _antibody_cluster_count(cls, text: str) -> int:
        candidates = set()
        for match in cls.ANTIBODY_TOKEN_RE.finditer(text or ""):
            token = match.group(0)
            if len(token) < 3:
                continue
            if not re.search(r"[A-Za-z]", token) or not re.search(r"\d", token):
                continue
            candidates.add(token.lower())
        return len(candidates)

    @classmethod
    def _has_antibody_name_cluster(cls, context: str) -> bool:
        return cls._antibody_cluster_count(context) >= cls.ANTIBODY_CLUSTER_MIN_NAMES

    @staticmethod
    def _build_user_text(context: str, seed_names: list[str]) -> str:
        seed_block = ", ".join(seed_names[:20]) if seed_names else "none"
        return (
            "请优先读取这张图中真实可见的氨基酸序列内容，并逐字符转写。\n"
            "如果当前输入包含多张相邻图片，请把它们视作同一个被拆开的 sequence/alignment panel，联合读取，不要只看第一张。\n"
            "请识别抗体名称，并提取其 H/VH、L/VL 氨基酸序列；如果图中单独标出 CDRH3，也请提取。\n"
            "如果图里有参考序列行，而其他行用 . 表示与参考序列相同，请把这些 . 按参考行对应位置还原成完整序列；- 仍保留为 gap。\n"
            "如果图里是 H3/H4/L1/L2/L3 这类链级 alignment，请直接输出图片里显示的原始行名，不要自行合成为 H3L1 之类的新名字。\n"
            "如果是 sequence alignment，可以保留 - 作为 gap；不要补全缺失字符，不要根据常识猜测。\n"
            "不要把图注、panel 标签、核苷酸序列或编号混入氨基酸序列字段。\n"
            "如果图片里只有名字没有对应氨基酸序列，则不要输出该抗体。\n"
            f"上下文：{context[:900]}\n"
            f"已知可能相关的抗体名：{seed_block}\n"
            "输出 JSON 数组。"
        )

    def _parse_records(self, text: str) -> list[dict]:
        parsed = self._parse_json(text)
        if parsed:
            return parsed
        return self._parse_plaintext_blocks(text)

    @staticmethod
    def _parse_json(text: str) -> list[dict]:
        cleaned = text.strip()
        if not cleaned:
            return []
        try:
            payload = json.loads(cleaned)
            if isinstance(payload, list):
                return payload
            if isinstance(payload, dict):
                return [payload]
        except json.JSONDecodeError:
            pass
        start = cleaned.find("[")
        end = cleaned.rfind("]")
        if start != -1 and end > start:
            try:
                payload = json.loads(cleaned[start : end + 1])
                if isinstance(payload, list):
                    return payload
            except json.JSONDecodeError:
                return []
        return []

    def _parse_plaintext_blocks(self, text: str) -> list[dict]:
        records = []
        current = None
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if ":" not in line and self.NAME_LINE_RE.match(line):
                if current and any(current.get(field) for field in ("VH_sequence", "VL_sequence", "CDRH3")):
                    records.append(current)
                current = {"mAb": line, "VH_sequence": "", "VL_sequence": "", "CDRH3": ""}
                continue
            if current is None or ":" not in line:
                continue
            key, value = [part.strip() for part in line.split(":", 1)]
            key_l = key.lower()
            if key_l in {"h chain", "heavy chain", "vh", "重链", "h链"}:
                current["VH_sequence"] = value
            elif key_l in {"l chain", "light chain", "vl", "轻链", "l链"}:
                current["VL_sequence"] = value
            elif key_l in {"cdrh3", "cdr-h3"}:
                current["CDRH3"] = value
        if current and any(current.get(field) for field in ("VH_sequence", "VL_sequence", "CDRH3")):
            records.append(current)
        return records

    @staticmethod
    def _clean_sequence(value: str) -> str:
        text = re.sub(r"\s+", "", str(value or "")).upper()
        cleaned = re.sub(r"[^A-Z-]", "", text)
        return cleaned

    @property
    def stats(self) -> dict:
        return {"total_calls": self._total_calls, "total_tokens": self._total_tokens}
