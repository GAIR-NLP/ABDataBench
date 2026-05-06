"""Phase 3 Track C: in-text table extraction agent."""

import time
from agents.base_agent import BaseAgent, AgentResult, AgentStatus
from tools.table_parser import TableParser


class TableExtractAgent(BaseAgent):
    def __init__(self, config):
        super().__init__("table_extract", config)
        self.parser = TableParser()

    async def execute(self, context: dict) -> AgentResult:
        start = time.time()
        agent_span = self._start_span(context, "agent", self.name)
        tool_span = self._start_span(context, "tool", "table_parser.extract", tool="table_parser.extract")
        text = context["markdown_text"]

        try:
            html_tables = self.parser.extract_html_tables(text)
            md_tables = self.parser.extract_markdown_tables(text)

            all_records = []
            ab_table_count = 0
            all_tables_data = []
            reconstructed_seq_records = []
            seen_reconstructed = set()

            for table in html_tables + md_tables:
                result = self.parser.table_to_records(table)
                all_tables_data.append(result)
                if result["is_antibody_table"]:
                    ab_table_count += 1
                    all_records.extend(result["rows"])
                if self.parser._detect_sequence_fragment_table(table):
                    for record in self.parser._assemble_sequence_fragment_records(table):
                        key = (
                            record.get("mAb", ""),
                            record.get("VH_sequence", ""),
                            record.get("VL_sequence", ""),
                        )
                        if key in seen_reconstructed:
                            continue
                        seen_reconstructed.add(key)
                        reconstructed_seq_records.append(record)

            all_records.extend(reconstructed_seq_records)

            self.logger.info(f"Table Extract: {len(html_tables)} HTML + {len(md_tables)} MD tables, "
                             f"{ab_table_count} antibody tables, {len(all_records)} records "
                             f"({len(reconstructed_seq_records)} reconstructed sequences)")
            elapsed = round(time.time() - start, 2)
            self._end_span(
                context,
                tool_span,
                status="success",
                html_table_count=len(html_tables),
                markdown_table_count=len(md_tables),
                antibody_table_count=ab_table_count,
                record_count=len(all_records),
                reconstructed_sequence_records=len(reconstructed_seq_records),
            )
            self._end_span(context, agent_span, status="success", elapsed_seconds=elapsed)
            return AgentResult(
                status=AgentStatus.SUCCESS,
                data={
                    "table_records": all_records,
                    "all_tables": all_tables_data,
                    "confidence": "Level 2",
                },
                metrics={"elapsed_seconds": elapsed},
            )
        except Exception as exc:
            self._end_span(context, tool_span, status="error", error=str(exc))
            self._end_span(context, agent_span, status="error", error=str(exc))
            raise
