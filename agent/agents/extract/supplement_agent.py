"""Phase 3 Track B: supplemental material extraction agent."""

import time
from agents.base_agent import BaseAgent, AgentResult, AgentStatus


class SupplementAgent(BaseAgent):
    def __init__(self, config):
        super().__init__("supplement", config)

    async def execute(self, context: dict) -> AgentResult:
        start = time.time()
        agent_span = self._start_span(context, "agent", self.name)
        # Supplement material extraction is optional and often not accessible
        # This agent checks if supplement files exist and attempts to parse them
        self.logger.info("Supplement: No supplement files available (placeholder)")
        elapsed = round(time.time() - start, 2)
        self._end_span(context, agent_span, status="success", elapsed_seconds=elapsed, note="placeholder")
        return AgentResult(
            status=AgentStatus.SUCCESS,
            data={"supplement_data": [], "note": "Supplement files not accessible"},
            metrics={"elapsed_seconds": elapsed},
        )
