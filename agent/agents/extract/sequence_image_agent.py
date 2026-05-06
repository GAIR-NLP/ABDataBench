"""Sequence image extraction agent for image-only sequence alignment figures."""

import time

from agents.base_agent import BaseAgent, AgentResult, AgentStatus
from tools.sequence_image_tool import SequenceImageTool


class SequenceImageExtractAgent(BaseAgent):
    def __init__(self, config, tool: SequenceImageTool | None = None):
        super().__init__("sequence_image_extract", config)
        self.tool = tool or SequenceImageTool(config)

    async def execute(self, context: dict) -> AgentResult:
        start = time.time()
        agent_span = self._start_span(context, "agent", self.name)
        try:
            seed_names = list(context.get("regex_hints", {}).get("antibody_name_candidates", []))
            for ab in context.get("skeleton", {}).get(context.get("paper_id", ""), {}).get("antibodies", []):
                name = (ab.get("Antibody_Name") or "").strip()
                if name and name not in seed_names:
                    seed_names.append(name)

            data = await self.tool.extract_from_markdown(
                context["markdown_text"],
                context["input_file"],
                seed_names=seed_names,
            )
            elapsed = round(time.time() - start, 2)
            self._end_span(
                context,
                agent_span,
                status="success",
                elapsed_seconds=elapsed,
                records=len(data.get("table_records", [])),
                images_considered=data.get("images_considered", 0),
            )
            return AgentResult(
                status=AgentStatus.SUCCESS,
                data=data,
                metrics={
                    "elapsed_seconds": elapsed,
                    "images_considered": data.get("images_considered", 0),
                    "images_used": data.get("images_used", 0),
                    "records": len(data.get("table_records", [])),
                    "vlm_stats": self.tool.stats,
                },
            )
        except Exception as exc:
            elapsed = round(time.time() - start, 2)
            self.logger.warning("Sequence image extraction failed: %s", exc)
            self._end_span(context, agent_span, status="error", error=str(exc))
            return AgentResult(
                status=AgentStatus.SUCCESS,
                data={
                    "table_records": [],
                    "images_considered": 0,
                    "images_used": 0,
                    "note": f"Sequence-image extraction failed: {exc}",
                    "source": "sequence_image_tool",
                },
                metrics={"elapsed_seconds": elapsed, "records": 0},
            )
