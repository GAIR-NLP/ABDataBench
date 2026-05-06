"""Optional conservative OCR markdown repair stage."""

import asyncio
import json
import os
import re
import time
from collections import Counter
from html import unescape
from html.parser import HTMLParser

from .base_agent import BaseAgent, AgentResult, AgentStatus
from tools.llm_client import LLMClient
from tools.paper_text_reducer import PaperTextReducer
from tools.skill_loader import load_skill_prompt_set


class _HTMLTableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables = []
        self._current_table = None
        self._current_row = None
        self._current_cell = None
        self._cell_depth = 0

    def handle_starttag(self, tag, attrs):
        lowered = tag.lower()
        if lowered == "table":
            self._current_table = []
        elif lowered == "tr" and self._current_table is not None:
            self._current_row = []
        elif lowered in {"td", "th"} and self._current_row is not None:
            self._current_cell = []
            self._cell_depth += 1

    def handle_endtag(self, tag):
        lowered = tag.lower()
        if lowered in {"td", "th"} and self._current_row is not None and self._current_cell is not None:
            text = "".join(self._current_cell)
            self._current_row.append(text)
            self._current_cell = None
            self._cell_depth = max(0, self._cell_depth - 1)
        elif lowered == "tr" and self._current_table is not None and self._current_row is not None:
            self._current_table.append(self._current_row)
            self._current_row = None
        elif lowered == "table" and self._current_table is not None:
            self.tables.append(self._current_table)
            self._current_table = None

    def handle_data(self, data):
        if self._current_cell is not None:
            self._current_cell.append(data)


class OCRRepairAgent(BaseAgent):
    SEQUENCE_TOKEN_RE = re.compile(r"\b[ACDEFGHIKLMNPQRSTVWY]{8,}\b|\b[ACGTU]{8,}\b")
    PROTECTED_ID_RE = re.compile(
        r"\bSEQ\s*ID\s*(?:NO\.?|NUMBER)?\s*[:#]?\s*\d+\b"
        r"|\b[0-9][A-Za-z0-9]{3}\b"
        r"|\b[A-Z]{1,4}[_ -]?\d{3,9}(?:\.\d+)?\b"
        r"|\b(?:PDB|GenBank|NCBI)\b",
        re.IGNORECASE,
    )
    DIGIT_TOKEN_RE = re.compile(r"\b\S*\d\S*\b")
    HTML_TABLE_RE = re.compile(r"<table\b.*?</table>", re.IGNORECASE | re.DOTALL)
    WHITESPACE_RE = re.compile(r"\s+")
    TABLE_HEADER_WHITELIST = {
        "",
        "variant",
        "variants",
        "mutant",
        "mutants",
        "fab",
        "species",
        "molecule",
        "kd",
        "kdnm",
        "ka1",
        "ka11ms",
        "kd1",
        "kd11s",
        "kd1nm",
        "ka2",
        "ka21ms",
        "kd2",
        "kd21s",
        "kd2nm",
        "lowaffinityka1",
        "lowaffinitykd1",
        "lowaffinitykd1nm",
        "highaffinityka2",
        "highaffinitykd2",
        "highaffinitykd2nm",
        "ic50pm",
        "ic90pm",
        "t12days",
        "t12betahours",
    }

    def __init__(self, config, llm: LLMClient = None):
        super().__init__("ocr_repair", config)
        chunk_chars = int(getattr(config, "ocr_repair_chunk_chars", 12_000))
        self.chunker = PaperTextReducer(chunk_chars=chunk_chars)
        self.llm = llm or LLMClient(config)
        self.repair_model = getattr(config, "ocr_repair_model", "") or config.llm_model
        self.repair_max_tokens = int(getattr(config, "ocr_repair_max_tokens", 6_000))
        self.repair_temperature = float(getattr(config, "ocr_repair_temperature", 0.0))
        self.repair_concurrency = max(1, int(getattr(config, "ocr_repair_concurrency", 6)))
        prompts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts")
        prompts = load_skill_prompt_set(
            "ocr-format-repair",
            {
                "system_prompt": os.path.join(prompts_dir, "ocr_repair_system.txt"),
                "user_template": os.path.join(prompts_dir, "ocr_repair_user.txt"),
            },
        )
        self.system_prompt = prompts["system_prompt"]
        self.user_template = prompts["user_template"]

    async def execute(self, context: dict) -> AgentResult:
        text = context["markdown_text"]
        start = time.time()
        agent_span = self._start_span(context, "agent", self.name)
        enabled = bool(getattr(self.config, "enable_ocr_repair", False))
        min_chars = int(getattr(self.config, "ocr_repair_min_chars", 2_000))

        if not enabled or len(text) < min_chars:
            elapsed = round(time.time() - start, 2)
            meta = {
                "enabled": enabled,
                "used_repaired_text": False,
                "original_chars": len(text),
                "repaired_chars": len(text),
                "reason": "below_threshold" if enabled else "disabled",
                "total_chunks": 0,
                "changed_chunks": 0,
                "protected_change_rejections": 0,
                "failed_chunks": 0,
                "chunk_summaries": [],
            }
            self._end_span(context, agent_span, status="success", elapsed_seconds=elapsed, used_repaired_text=False)
            return AgentResult(
                status=AgentStatus.SUCCESS,
                data={"repaired_text": text, "meta": meta},
                metrics={"elapsed_seconds": elapsed, "used_repaired_text": False, "llm_calls": 0},
            )

        chunks = self.chunker.chunk_text(text)
        total_chunks = len(chunks)
        semaphore = asyncio.Semaphore(self.repair_concurrency)

        async def process_chunk(chunk: dict) -> dict:
            user_msg = self.user_template.format(
                PAPER_ID=context.get("paper_id", "unknown"),
                CHUNK_INDEX=chunk["chunk_index"],
                TOTAL_CHUNKS=total_chunks,
                CHUNK_TEXT=chunk["text"],
            )
            async with semaphore:
                try:
                    resp = await self.llm.chat(
                        system=self.system_prompt,
                        user=user_msg,
                        model=self.repair_model,
                        temperature=self.repair_temperature,
                        max_tokens=self.repair_max_tokens,
                        response_format="json",
                        trace_fields={
                            "paper_id": context.get("paper_id"),
                            "phase": context.get("current_phase"),
                            "agent": self.name,
                            "chunk_index": chunk["chunk_index"],
                            "chunk_count": total_chunks,
                        },
                    )
                    payload = self.llm.parse_json_response(resp.content)
                    repaired_text, changed, notes, summary, rejected = self._normalize_chunk_payload(
                        payload, chunk["text"]
                    )
                    return {
                        "chunk_index": chunk["chunk_index"],
                        "repaired_text": repaired_text,
                        "original_chars": chunk["char_count"],
                        "repaired_chars": len(repaired_text),
                        "changed": changed,
                        "edit_summary": summary,
                        "notes": notes,
                        "llm_tokens": resp.total_tokens,
                        "protected_change_rejected": rejected,
                        "error": None,
                    }
                except Exception as exc:
                    self.logger.warning(
                        "OCR repair chunk %s failed; keeping original chunk. Error: %s",
                        chunk["chunk_index"],
                        exc,
                    )
                    return {
                        "chunk_index": chunk["chunk_index"],
                        "repaired_text": chunk["text"],
                        "original_chars": chunk["char_count"],
                        "repaired_chars": chunk["char_count"],
                        "changed": False,
                        "edit_summary": [],
                        "notes": "llm_repair_failed_keep_original",
                        "llm_tokens": 0,
                        "protected_change_rejected": False,
                        "error": str(exc),
                    }

        chunk_results = await asyncio.gather(*(process_chunk(chunk) for chunk in chunks))
        chunk_results.sort(key=lambda item: item["chunk_index"])
        repaired_text = "\n\n".join((item.get("repaired_text") or "").strip() for item in chunk_results).strip()
        if not repaired_text:
            repaired_text = text

        total_tokens = sum(item.get("llm_tokens", 0) for item in chunk_results)
        changed_chunks = sum(1 for item in chunk_results if item.get("changed"))
        failed_chunks = sum(1 for item in chunk_results if item.get("error"))
        protected_rejections = sum(1 for item in chunk_results if item.get("protected_change_rejected"))
        elapsed = round(time.time() - start, 2)
        meta = {
            "enabled": True,
            "model": self.repair_model,
            "used_repaired_text": repaired_text != text,
            "original_chars": len(text),
            "repaired_chars": len(repaired_text),
            "total_chunks": total_chunks,
            "changed_chunks": changed_chunks,
            "protected_change_rejections": protected_rejections,
            "failed_chunks": failed_chunks,
            "llm_calls": total_chunks,
            "llm_tokens": total_tokens,
            "concurrency": self.repair_concurrency,
            "chunk_summaries": [
                {
                    "chunk_index": item["chunk_index"],
                    "original_chars": item["original_chars"],
                    "repaired_chars": item["repaired_chars"],
                    "changed": item["changed"],
                    "edit_summary": item.get("edit_summary", []),
                    "notes": item.get("notes", ""),
                    "protected_change_rejected": item.get("protected_change_rejected", False),
                    "error": item.get("error"),
                }
                for item in chunk_results
            ],
        }
        self._end_span(
            context,
            agent_span,
            status="success",
            elapsed_seconds=elapsed,
            used_repaired_text=meta["used_repaired_text"],
            changed_chunks=changed_chunks,
            llm_calls=total_chunks,
            llm_tokens=total_tokens,
        )
        return AgentResult(
            status=AgentStatus.SUCCESS,
            data={"repaired_text": repaired_text, "meta": meta},
            metrics={
                "elapsed_seconds": elapsed,
                "used_repaired_text": meta["used_repaired_text"],
                "changed_chunks": changed_chunks,
                "llm_calls": total_chunks,
                "llm_tokens": total_tokens,
            },
        )

    @classmethod
    def _normalize_chunk_payload(cls, payload: dict, original_chunk: str) -> tuple[str, bool, str, list[str], bool]:
        if not isinstance(payload, dict):
            return original_chunk, False, "payload_not_dict_keep_original", [], False

        repaired_text = payload.get("repaired_text")
        changed = bool(payload.get("changed"))
        notes = str(payload.get("notes") or "")
        edit_summary = payload.get("edit_summary") or []
        if not isinstance(edit_summary, list):
            edit_summary = [str(edit_summary)] if edit_summary else []
        edit_summary = [str(item).strip() for item in edit_summary if str(item).strip()]

        if not isinstance(repaired_text, str):
            return original_chunk, False, "missing_repaired_text_keep_original", edit_summary, False

        candidate = repaired_text.strip()
        if not candidate:
            return original_chunk, False, "empty_repaired_text_keep_original", edit_summary, False
        if candidate == original_chunk.strip():
            return original_chunk, False, notes or "no_change", edit_summary, False
        if len(candidate) > max(len(original_chunk) * 1.5, len(original_chunk) + 2_000):
            return original_chunk, False, notes or "expanded_too_much_keep_original", edit_summary, False
        if len(original_chunk) >= 500 and len(candidate) < int(len(original_chunk) * 0.5):
            return original_chunk, False, notes or "shrunk_too_much_keep_original", edit_summary, False
        if cls._protected_tokens(candidate) != cls._protected_tokens(original_chunk):
            if cls._is_allowed_table_header_repair(original_chunk, candidate):
                return candidate, True, notes or "table_header_whitelist_repair", edit_summary, False
            return original_chunk, False, "protected_tokens_changed_keep_original", edit_summary, True

        return candidate, changed or candidate != original_chunk.strip(), notes or "chunk_repaired", edit_summary, False

    @classmethod
    def _protected_tokens(cls, text: str) -> Counter:
        tokens: list[str] = []
        for match in cls.PROTECTED_ID_RE.finditer(text):
            tokens.append(re.sub(r"\s+", "", match.group(0).upper()))
        for match in cls.DIGIT_TOKEN_RE.finditer(text):
            tokens.append(match.group(0))
        for match in cls.SEQUENCE_TOKEN_RE.finditer(text):
            tokens.append(match.group(0))
        return Counter(tokens)

    @classmethod
    def _is_allowed_table_header_repair(cls, original_text: str, candidate_text: str) -> bool:
        original_tables = cls._extract_tables(original_text)
        candidate_tables = cls._extract_tables(candidate_text)
        if not original_tables or not candidate_tables:
            return False
        if len(original_tables) != len(candidate_tables):
            return False
        if cls._normalize_non_table_text(original_text) != cls._normalize_non_table_text(candidate_text):
            return False

        for original_table, candidate_table in zip(original_tables, candidate_tables):
            if len(original_table) != len(candidate_table):
                return False
            if not original_table or not candidate_table:
                return False
            original_widths = [len(row) for row in original_table]
            candidate_widths = [len(row) for row in candidate_table]
            if original_widths != candidate_widths:
                return False

            for row_index in range(1, len(original_table)):
                if cls._normalize_row(original_table[row_index]) != cls._normalize_row(candidate_table[row_index]):
                    return False

            header_changed = cls._normalize_row(original_table[0]) != cls._normalize_row(candidate_table[0])
            if not header_changed:
                continue
            if not all(cls._is_whitelisted_header_cell(cell) for cell in candidate_table[0]):
                return False

        return True

    @classmethod
    def _extract_tables(cls, text: str) -> list[list[list[str]]]:
        tables: list[list[list[str]]] = []
        for match in cls.HTML_TABLE_RE.finditer(text):
            parser = _HTMLTableParser()
            parser.feed(match.group(0))
            for table in parser.tables:
                if table:
                    tables.append(table)
        return tables

    @classmethod
    def _normalize_non_table_text(cls, text: str) -> str:
        stripped = cls.HTML_TABLE_RE.sub(" ", text)
        return cls._normalize_text(stripped)

    @classmethod
    def _normalize_row(cls, row: list[str]) -> list[str]:
        return [cls._normalize_text(cell) for cell in row]

    @classmethod
    def _normalize_text(cls, text: str) -> str:
        return cls.WHITESPACE_RE.sub(" ", unescape(text or "")).strip()

    @classmethod
    def _is_whitelisted_header_cell(cls, cell_text: str) -> bool:
        normalized = cls._normalize_header_label(cell_text)
        return normalized in cls.TABLE_HEADER_WHITELIST

    @classmethod
    def _normalize_header_label(cls, text: str) -> str:
        value = unescape(text or "").strip().lower()
        value = value.replace("β", "beta")
        value = value.replace("μ", "u")
        value = value.replace("µ", "u")
        value = value.replace("κ", "kappa")
        value = value.replace("α", "alpha")
        value = value.replace("γ", "gamma")
        value = value.replace("½", "1/2")
        value = re.sub(r"\blow\b", "low", value)
        value = re.sub(r"\bhigh\b", "high", value)
        value = re.sub(r"[^a-z0-9]+", "", value)
        return value
