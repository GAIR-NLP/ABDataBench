"""Phase 4: biological validation agent."""

import time
from .base_agent import BaseAgent, AgentResult, AgentStatus
from tools.bio_validator import BioValidator


class ValidatorAgent(BaseAgent):
    def __init__(self, config):
        super().__init__("validator", config)
        self.validator = BioValidator()

    async def execute(self, context: dict) -> AgentResult:
        start = time.time()
        agent_span = self._start_span(context, "agent", self.name)
        tool_span = self._start_span(context, "tool", "bio_validator.validate", tool="bio_validator.validate")
        skeleton = context["skeleton"]
        paper_id = context.get("paper_id", "unknown")

        # Extract antibodies list from the nested structure
        antibodies = skeleton.get(paper_id, {}).get("antibodies", [])
        if not antibodies:
            # Try flat list
            if isinstance(skeleton, list):
                antibodies = skeleton

        try:
            all_results = []
            total = {"pass": 0, "warn": 0, "fail": 0, "skip": 0, "info": 0}
            for ab in antibodies:
                result = self.validator.validate_antibody(ab)
                all_results.append(result)
                for k in total:
                    total[k] += result["summary"].get(k, 0)

            duplicates = self.validator.detect_duplicates(antibodies)

            overall = "PASS"
            if total["fail"] > 0:
                overall = "FAIL"
            elif total["warn"] > 0:
                overall = "WARN" if not self.config.strict_validation else "FAIL"

            report = {
                "summary": {**total, "overall": overall, "duplicates": len(duplicates),
                            "total_antibodies": len(antibodies)},
                "antibodies": all_results,
                "duplicates": duplicates,
            }

            self.logger.info(f"Validation: {len(antibodies)} antibodies, "
                             f"pass={total['pass']} warn={total['warn']} fail={total['fail']}, "
                             f"overall={overall}")
            elapsed = round(time.time() - start, 2)
            self._end_span(
                context,
                tool_span,
                status="success",
                antibody_count=len(antibodies),
                fail_count=total["fail"],
                warn_count=total["warn"],
            )
            self._end_span(context, agent_span, status="success", elapsed_seconds=elapsed, overall=overall)
            return AgentResult(
                status=AgentStatus.SUCCESS,
                data=report,
                metrics={"elapsed_seconds": elapsed},
            )
        except Exception as exc:
            self._end_span(context, tool_span, status="error", error=str(exc))
            self._end_span(context, agent_span, status="error", error=str(exc))
            raise
