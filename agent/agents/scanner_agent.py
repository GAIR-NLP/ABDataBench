"""Phase 1: regex pre-scan agent."""

import time
from .base_agent import BaseAgent, AgentResult, AgentStatus
from tools.regex_scanner import RegexScanner


class ScannerAgent(BaseAgent):
    def __init__(self, config):
        super().__init__("scanner", config)
        self.scanner = RegexScanner()

    async def execute(self, context: dict) -> AgentResult:
        text = context["markdown_text"]
        start = time.time()
        agent_span = self._start_span(context, "agent", self.name)
        tool_span = self._start_span(context, "tool", "regex_scanner.scan_all", tool="regex_scanner.scan_all")

        try:
            results = self.scanner.scan_all(text)
            results["regex_hints_text"] = self.scanner.format_hints(results)
            results["routing_suggestions"] = self.scanner.suggest_routing(results)
            self._end_span(
                context,
                tool_span,
                table_count=results["tables"]["total_table_count"],
                pdb_count=len(results["pdb_ids"]),
            )

            self.logger.info(f"Scan done: PDB={len(results['pdb_ids'])}, "
                             f"GenBank={len(results['genbank']['likely_genbank'])}, "
                             f"Tables={results['tables']['total_table_count']}, "
                             f"CDR3_H={len(results['cdr3_sequences']['CDRH3_candidates'])}")
            elapsed = round(time.time() - start, 2)
            self._end_span(context, agent_span, elapsed_seconds=elapsed, status="success")
            return AgentResult(
                status=AgentStatus.SUCCESS,
                data=results,
                metrics={"elapsed_seconds": elapsed},
            )
        except Exception as exc:
            self._end_span(context, tool_span, status="error", error=str(exc))
            self._end_span(context, agent_span, status="error", error=str(exc))
            raise
