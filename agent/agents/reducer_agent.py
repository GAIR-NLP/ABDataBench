"""Phase 1.2: chunked LLM reducer for long-context papers."""

import asyncio
import os
import time

from .base_agent import BaseAgent, AgentResult, AgentStatus
from tools.llm_client import LLMClient
from tools.paper_text_reducer import PaperTextReducer
from tools.skill_loader import load_skill_prompt_set


class ReducerAgent(BaseAgent):
    def __init__(self, config, llm: LLMClient = None):
        super().__init__("reducer", config)
        chunk_chars = getattr(config, "text_reduce_chunk_chars", 4_000)
        self.reducer = PaperTextReducer(chunk_chars=chunk_chars)
        self.llm = llm or LLMClient(config)
        self.reduce_model = getattr(config, "text_reduce_model", "") or config.llm_model
        self.reduce_max_tokens = getattr(config, "text_reduce_max_tokens", 4_000)
        self.reduce_temperature = getattr(config, "text_reduce_temperature", 0.0)
        self.reduce_concurrency = max(1, int(getattr(config, "text_reduce_concurrency", 10)))
        prompts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts")
        prompts = load_skill_prompt_set(
            "evidence-reduction",
            {
                "system_prompt": os.path.join(prompts_dir, "reducer_system.txt"),
                "user_template": os.path.join(prompts_dir, "reducer_user.txt"),
            },
        )
        self.system_prompt = prompts["system_prompt"]
        self.user_template = prompts["user_template"]

    async def execute(self, context: dict) -> AgentResult:
        text = context["markdown_text"]
        start = time.time()
        agent_span = self._start_span(context, "agent", self.name)
        min_chars = getattr(self.config, "text_reduce_min_chars", 120_000)
        enabled = getattr(self.config, "enable_text_reduce", True)

        if not enabled or len(text) < min_chars:
            elapsed = round(time.time() - start, 2)
            data = {
                "reduced_text": text,
                "meta": {
                    "enabled": enabled,
                    "used_reduced_text": False,
                    "original_chars": len(text),
                    "reduced_chars": len(text),
                    "reduction_ratio": 1.0,
                    "reason": "below_threshold" if enabled else "disabled",
                    "image_manifest": [],
                    "total_chunks": 0,
                    "kept_chunks": 0,
                    "dropped_chunks": 0,
                    "failed_chunks": 0,
                    "chunk_summaries": [],
                },
            }
            self._end_span(context, agent_span, status="success", elapsed_seconds=elapsed, used_reduced_text=False)
            return AgentResult(
                status=AgentStatus.SUCCESS,
                data=data,
                metrics={"elapsed_seconds": elapsed, "used_reduced_text": False, "llm_calls": 0},
            )

        chunks = self.reducer.chunk_text(text)
        total_chunks = len(chunks)
        semaphore = asyncio.Semaphore(self.reduce_concurrency)

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
                        model=self.reduce_model,
                        temperature=self.reduce_temperature,
                        max_tokens=self.reduce_max_tokens,
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
                    filtered_text, evidence_types, notes = self._normalize_chunk_payload(payload, chunk["text"])
                    return {
                        "chunk_index": chunk["chunk_index"],
                        "filtered_text": filtered_text,
                        "original_chars": chunk["char_count"],
                        "evidence_types": evidence_types,
                        "notes": notes,
                        "llm_tokens": resp.total_tokens,
                        "error": None,
                    }
                except Exception as exc:
                    self.logger.warning(
                        "Reducer chunk %s failed; keeping original chunk. Error: %s",
                        chunk["chunk_index"],
                        exc,
                    )
                    return {
                        "chunk_index": chunk["chunk_index"],
                        "filtered_text": chunk["text"],
                        "original_chars": chunk["char_count"],
                        "evidence_types": ["fallback_original_chunk"],
                        "notes": "llm_filter_failed_keep_original",
                        "llm_tokens": 0,
                        "error": str(exc),
                    }

        chunk_results = await asyncio.gather(*(process_chunk(chunk) for chunk in chunks))
        chunk_results.sort(key=lambda item: item["chunk_index"])
        total_tokens = sum(item.get("llm_tokens", 0) for item in chunk_results)
        successful_chunks = sum(1 for item in chunk_results if not item.get("error"))

        result = self.reducer.merge_filtered_chunks(text, chunk_results, paper_id=context.get("paper_id", ""))
        result["meta"].update(
            {
                "enabled": True,
                "model": self.reduce_model,
                "requested_chunk_chars": self.reducer.chunk_chars,
                "successful_chunks": successful_chunks,
                "llm_calls": total_chunks,
                "total_llm_tokens": total_tokens,
                "concurrency": self.reduce_concurrency,
            }
        )

        elapsed = round(time.time() - start, 2)
        self.logger.info(
            "LLM reduction complete: %s -> %s chars across %s chunk(s) with concurrency=%s",
            result["meta"]["original_chars"],
            result["meta"]["reduced_chars"],
            total_chunks,
            self.reduce_concurrency,
        )
        self._end_span(
            context,
            agent_span,
            status="success",
            elapsed_seconds=elapsed,
            used_reduced_text=result["meta"]["used_reduced_text"],
            reduced_chars=result["meta"]["reduced_chars"],
            llm_calls=total_chunks,
            llm_tokens=total_tokens,
        )
        return AgentResult(
            status=AgentStatus.SUCCESS,
            data=result,
            metrics={
                "elapsed_seconds": elapsed,
                "used_reduced_text": result["meta"]["used_reduced_text"],
                "reduced_chars": result["meta"]["reduced_chars"],
                "llm_calls": total_chunks,
                "llm_tokens": total_tokens,
            },
        )

    @staticmethod
    def _normalize_chunk_payload(payload: dict, original_chunk: str) -> tuple[str, list[str], str]:
        if not isinstance(payload, dict):
            return original_chunk, ["fallback_original_chunk"], "payload_not_dict_keep_original"

        keep = payload.get("keep")
        filtered_text = payload.get("filtered_text")
        evidence_types = payload.get("evidence_types") or []
        notes = str(payload.get("notes") or "")

        if not isinstance(evidence_types, list):
            evidence_types = [str(evidence_types)] if evidence_types else []
        evidence_types = [str(item) for item in evidence_types if str(item).strip()]

        if isinstance(filtered_text, str):
            filtered_text = filtered_text.strip()
        else:
            filtered_text = ""

        if keep is False:
            return "", evidence_types, notes or "chunk_dropped"

        if not filtered_text:
            return original_chunk, evidence_types or ["fallback_original_chunk"], notes or "empty_filtered_text_keep_original"

        if len(filtered_text) > len(original_chunk) + 2_000:
            return original_chunk, evidence_types or ["fallback_original_chunk"], notes or "expanded_too_much_keep_original"

        return filtered_text, evidence_types, notes
