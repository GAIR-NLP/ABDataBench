"""Phase 1.x: heuristic + optional LLM paper-focus analysis agent."""

import json
import os
import time

from .base_agent import BaseAgent, AgentResult, AgentStatus
from tools.llm_client import LLMClient
from tools.paper_focus import PaperFocusBuilder
from tools.skill_loader import load_skill_prompt


class PaperFocusAgent(BaseAgent):
    def __init__(self, config, llm: LLMClient = None):
        super().__init__("paper_focus", config)
        self.builder = PaperFocusBuilder()
        self.llm = llm or LLMClient(config)
        prompts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts")
        self.system_prompt = load_skill_prompt(
            "paper-focus-analysis",
            "system_prompt",
            os.path.join(prompts_dir, "paper_focus_system.txt"),
        )

    async def execute(self, context: dict) -> AgentResult:
        start = time.time()
        agent_span = self._start_span(context, "agent", self.name)
        try:
            focus = self.builder.analyze(
                context["markdown_text"],
                context.get("regex_hints"),
            )
            llm_focus_used = False
            llm_tokens = 0
            if (
                focus.get("hard_paper")
                and getattr(self.config, "enable_hard_paper_focus_analyzer", True)
            ):
                llm_payload, llm_tokens = await self._run_hard_paper_focus_llm(context, focus)
                focus = self._merge_llm_focus(focus, llm_payload)
                llm_focus_used = bool(llm_payload)
            elapsed = round(time.time() - start, 2)
            self._end_span(
                context,
                agent_span,
                status="success",
                elapsed_seconds=elapsed,
                hard_paper=focus.get("hard_paper", False),
                difficulty_count=len(focus.get("difficulty_flags") or []),
                llm_focus_used=llm_focus_used,
                llm_tokens=llm_tokens,
            )
            return AgentResult(
                status=AgentStatus.SUCCESS,
                data=focus,
                metrics={
                    "elapsed_seconds": elapsed,
                    "hard_paper": focus.get("hard_paper", False),
                    "difficulty_flags": len(focus.get("difficulty_flags") or []),
                    "llm_focus_used": llm_focus_used,
                    "llm_tokens": llm_tokens,
                },
            )
        except Exception as exc:
            self._end_span(context, agent_span, status="error", error=str(exc))
            raise

    async def _run_hard_paper_focus_llm(self, context: dict, focus: dict) -> tuple[dict, int]:
        md_text = context.get("markdown_text_reduced") or context["markdown_text"]
        max_chars = getattr(self.config, "hard_paper_focus_max_input_chars", 60_000)
        if len(md_text) > max_chars:
            md_text = md_text[:max_chars] + "\n\n[... truncated for hard-paper focus analyzer ...]"

        regex_hints = json.dumps(context.get("regex_hints", {}), ensure_ascii=False, indent=2)
        heuristic_focus = json.dumps(
            {
                "paper_type": focus.get("paper_type"),
                "evidence_carriers": focus.get("evidence_carriers"),
                "activated_modules": focus.get("activated_modules"),
                "difficulty_flags": focus.get("difficulty_flags"),
                "priority_antibody_names": focus.get("priority_antibody_names"),
                "deprioritized_antibody_names": focus.get("deprioritized_antibody_names"),
                "split_policy": focus.get("split_policy"),
                "value_binding_policy": focus.get("value_binding_policy"),
            },
            ensure_ascii=False,
            indent=2,
        )
        user_msg = (
            "[Paper Focus Analysis Task]\n"
            "Refine the extraction strategy for this hard paper. Output JSON only.\n\n"
            f"[Paper ID]: {context.get('paper_id', 'unknown')}\n\n"
            f"[Heuristic Focus]:\n{heuristic_focus}\n\n"
            f"[Regex Hints]:\n{regex_hints}\n\n"
            f"[Document Text]:\n{md_text}"
        )
        resp = await self.llm.chat(
            system=self.system_prompt,
            user=user_msg,
            model=getattr(self.config, "hard_paper_focus_model", "") or self.config.llm_model,
            temperature=getattr(self.config, "hard_paper_focus_temperature", 0.0),
            max_tokens=getattr(self.config, "hard_paper_focus_max_tokens", 3000),
            response_format="json",
            trace_fields={
                "paper_id": context.get("paper_id"),
                "phase": context.get("current_phase"),
                "agent": self.name,
                "hard_paper_focus": True,
            },
        )
        payload = self.llm.parse_json_response(resp.content)
        return (payload if isinstance(payload, dict) else {}), resp.total_tokens

    def _merge_llm_focus(self, focus: dict, llm_payload: dict) -> dict:
        if not llm_payload:
            focus["llm_focus_used"] = False
            return focus

        focus["llm_focus_used"] = True
        focus["llm_focus_analysis"] = llm_payload
        focus["priority_antibody_names"] = self.builder._unique_names(
            (focus.get("priority_antibody_names") or [])
            + (llm_payload.get("likely_core_antibodies") or [])
        )[:8]
        focus["deprioritized_antibody_names"] = self.builder._unique_names(
            (focus.get("deprioritized_antibody_names") or [])
            + (llm_payload.get("likely_reference_only_antibodies") or [])
        )[:8]
        focus["entity_risks"] = self._merge_lines(
            focus.get("entity_risks"),
            llm_payload.get("local_binding_warnings"),
        )
        focus["extraction_priority"] = self._merge_lines(
            focus.get("extraction_priority"),
            llm_payload.get("recommended_order"),
        )
        focus["sequence_focus"] = self._merge_lines(
            focus.get("sequence_focus"),
            llm_payload.get("sequence_source_priority"),
        )
        split_alerts = llm_payload.get("record_split_alerts") or []
        if split_alerts:
            focus["split_policy"] = (
                (focus.get("split_policy") or "")
                + " LLM hard-paper alerts: "
                + "; ".join(str(item) for item in split_alerts[:3])
            ).strip()
        summary = (llm_payload.get("llm_focus_summary") or "").strip()
        if summary:
            focus["paper_focus_text"] = (
                (focus.get("paper_focus_text") or "").rstrip()
                + "\n- Hard-paper LLM refinement: "
                + summary
            ).strip()
        return focus

    @staticmethod
    def _merge_lines(existing: list | None, additions: list | None) -> list:
        merged = []
        seen = set()
        for item in (existing or []) + (additions or []):
            text = str(item or "").strip()
            key = text.lower()
            if not text or key in seen:
                continue
            seen.add(key)
            merged.append(text)
        return merged[:6]
