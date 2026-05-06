"""Phase 5: LLM review and correction suggestion agent."""

import os
import json
import time
from .base_agent import BaseAgent, AgentResult, AgentStatus
from tools.llm_client import LLMClient
from tools.skill_loader import load_skill_prompt


class ReviewerAgent(BaseAgent):
    def __init__(self, config, llm: LLMClient = None):
        super().__init__("reviewer", config)
        self.llm = llm or LLMClient(config)
        prompts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts")
        self.system_prompt = load_skill_prompt(
            "reviewer-qa",
            "system_prompt",
            os.path.join(prompts_dir, "reviewer_system.txt"),
        )

    async def execute(self, context: dict) -> AgentResult:
        start = time.time()
        agent_span = self._start_span(context, "agent", self.name)
        validation = context["validation"]

        fails = [c for ab in validation["antibodies"]
                 for c in ab["checks"] if c["status"] == "fail"]
        warns = [c for ab in validation["antibodies"]
                 for c in ab["checks"] if c["status"] == "warn"]

        if not fails:
            self.logger.info(f"Review PASSED (0 fails, {len(warns)} warns)")
            elapsed = round(time.time() - start, 2)
            self._end_span(
                context,
                agent_span,
                status="success",
                elapsed_seconds=elapsed,
                fail_count=0,
                warn_count=len(warns),
                review_decision="approved",
            )
            return AgentResult(
                status=AgentStatus.SUCCESS,
                data={"approved": True, "fail_count": 0, "warn_count": len(warns)},
                metrics={"elapsed_seconds": elapsed},
            )

        # Build correction prompt
        user_msg = self._build_correction_prompt(context, fails, warns)
        try:
            resp = await self.llm.chat(
                system=self.system_prompt,
                user=user_msg,
                model=self.config.llm_review_model,
                temperature=0.1,
                max_tokens=4096,
                trace_fields={"paper_id": context.get("paper_id"), "phase": context.get("current_phase"), "agent": self.name},
            )

            self.logger.info(f"Review: {len(fails)} fails → correction generated")
            elapsed = round(time.time() - start, 2)
            self._end_span(
                context,
                agent_span,
                status="retry",
                elapsed_seconds=elapsed,
                fail_count=len(fails),
                warn_count=len(warns),
                llm_tokens=resp.total_tokens,
                review_decision="retry",
            )
            return AgentResult(
                status=AgentStatus.RETRY,
                data={
                    "approved": False,
                    "corrections": resp.content,
                    "fail_count": len(fails),
                    "warn_count": len(warns),
                },
                retry_suggestion="Re-build skeleton with corrections",
                metrics={"elapsed_seconds": elapsed,
                         "llm_tokens": resp.total_tokens},
            )
        except Exception as exc:
            self._end_span(context, agent_span, status="error", error=str(exc))
            raise

    def _build_correction_prompt(self, context, fails, warns) -> str:
        skeleton = context["skeleton"]
        paper_id = context.get("paper_id", "unknown")
        skeleton_str = json.dumps(skeleton.get(paper_id, skeleton), indent=2, ensure_ascii=False)

        lines = ["## Current Skeleton (excerpt):", skeleton_str[:3000], "",
                 f"## Validation Failures ({len(fails)}):", ""]
        for f in fails:
            lines.append(f"- FAIL: {f['message']}")
        lines.append("")
        lines.append(f"## High-priority Warnings ({min(len(warns), 10)}):")
        for w in warns[:10]:
            lines.append(f"- WARN: {w['message']}")
        lines.append("")
        lines.append("Please generate specific field-level corrections.")
        return "\n".join(lines)
