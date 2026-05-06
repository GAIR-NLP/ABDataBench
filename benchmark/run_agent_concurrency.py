#!/usr/bin/env python3
"""Run a concurrency benchmark over the 9 OCR markdown papers."""

from __future__ import annotations

import argparse
import asyncio
import glob
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENT_DIR = os.path.join(REPO_ROOT, "agent")
if AGENT_DIR not in sys.path:
    sys.path.insert(0, AGENT_DIR)

from config import Config
from main import run_batch
from tools.trace_recorder import TraceRecorder


PHASE_COLORS = {
    "scan": "#2563eb",
    "skeleton": "#dc2626",
    "extract": "#7c3aed",
    "validate": "#0f766e",
    "review": "#ea580c",
    "skeleton_retry": "#9333ea",
    "validate_retry": "#0d9488",
    "finalize": "#475569",
}


def parse_args():
    parser = argparse.ArgumentParser(description="Concurrency benchmark for the agent pipeline")
    parser.add_argument(
        "--ocr-dir",
        default=os.environ.get(
            "BENCHMARK_OCR_DIR",
            os.path.join(REPO_ROOT, "dataset"),
        ),
        help="Directory containing OCR paper folders; can also be set with BENCHMARK_OCR_DIR",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Output directory for benchmark artifacts; defaults to benchmark/concurrency_results/<timestamp>",
    )
    parser.add_argument("--papers-per-worker", type=int, default=4, help="Concurrent papers")
    parser.add_argument("--llm-concurrency", type=int, default=8, help="Shared LLM concurrency")
    parser.add_argument("--timeout", type=int, default=900, help="Per-paper timeout in seconds")
    parser.add_argument("--live", action="store_true", help="Use the configured live LLM instead of mock mode")
    parser.add_argument("--api-base", help="Override LLM API base URL")
    parser.add_argument("--api-key", help="Override LLM API key")
    parser.add_argument("--model", help="Override LLM model")
    parser.add_argument("--max-retries", type=int, default=1, help="Pipeline retry count")
    parser.add_argument("--keep-intermediate", action="store_true", help="Preserve per-paper intermediate outputs")
    return parser.parse_args()


def default_output_dir() -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(REPO_ROOT, "benchmark", "concurrency_results", stamp)


def discover_papers(ocr_dir: str) -> list[str]:
    files = sorted(glob.glob(os.path.join(ocr_dir, "*/vlm/*.md")))
    return [f for f in files if os.path.basename(f).endswith(".md")]


def merge_span(start: dict, end: dict) -> dict:
    span = dict(start)
    span["end_offset_ms"] = end["offset_ms"]
    span["duration_ms"] = round(end["offset_ms"] - start["offset_ms"], 3)
    span["status"] = end.get("status", "success")
    for key, value in end.items():
        if key not in {"event", "timestamp", "offset_ms", "span_id"}:
            span[key] = value
    return span


def build_spans(events: list[dict]) -> list[dict]:
    starts = {}
    spans = []
    for event in events:
        if event["event"] == "span_start":
            starts[event["span_id"]] = event
        elif event["event"] == "span_end":
            start = starts.get(event["span_id"])
            if start:
                spans.append(merge_span(start, event))
    return spans


def calc_max_concurrency(spans: list[dict], span_type: str) -> int:
    points = []
    for span in spans:
        if span.get("span_type") != span_type:
            continue
        points.append((span["offset_ms"], 1))
        points.append((span["end_offset_ms"], -1))
    current = 0
    peak = 0
    for _, delta in sorted(points, key=lambda item: (item[0], -item[1])):
        current += delta
        peak = max(peak, current)
    return peak


def summarise(trace_payload: dict, batch_summary: dict, config: Config, paper_files: list[str]) -> dict:
    events = trace_payload["events"]
    spans = build_spans(events)
    spans_by_type = defaultdict(list)
    for span in spans:
        spans_by_type[span.get("span_type", "unknown")].append(span)

    wall_time_ms = max((span.get("end_offset_ms", 0) for span in spans), default=0)
    paper_spans = sorted(spans_by_type["paper"], key=lambda item: item["offset_ms"])
    phase_spans = spans_by_type["phase"]
    agent_spans = spans_by_type["agent"]
    tool_spans = spans_by_type["tool"]

    paper_phase_map = defaultdict(list)
    paper_agent_map = defaultdict(list)
    for span in phase_spans:
        paper_phase_map[span.get("paper_id", "unknown")].append(span)
    for span in agent_spans:
        paper_agent_map[span.get("paper_id", "unknown")].append(span)

    phase_groups = defaultdict(list)
    for span in phase_spans:
        phase_groups[span["name"]].append(span)
    phase_summary = []
    for phase, phase_items in sorted(phase_groups.items()):
        durations = [item["duration_ms"] for item in phase_items]
        phase_summary.append(
            {
                "phase": phase,
                "count": len(phase_items),
                "avg_ms": round(sum(durations) / len(durations), 2),
                "max_ms": round(max(durations), 2),
                "color": PHASE_COLORS.get(phase, "#64748b"),
            }
        )

    tool_groups = defaultdict(list)
    for span in tool_spans:
        tool_groups[span.get("tool", span["name"])].append(span)
    tool_summary = []
    for tool_name, items in sorted(tool_groups.items()):
        durations = [item["duration_ms"] for item in items]
        tool_summary.append(
            {
                "tool": tool_name,
                "count": len(items),
                "errors": len([item for item in items if item.get("status") == "error"]),
                "avg_ms": round(sum(durations) / len(durations), 2),
                "max_ms": round(max(durations), 2),
            }
        )

    agent_groups = defaultdict(list)
    for span in agent_spans:
        agent_groups[span.get("agent", span["name"])].append(span)
    agent_summary = []
    for agent_name, items in sorted(agent_groups.items()):
        durations = [item["duration_ms"] for item in items]
        agent_summary.append(
            {
                "agent": agent_name,
                "count": len(items),
                "avg_ms": round(sum(durations) / len(durations), 2),
                "max_ms": round(max(durations), 2),
            }
        )

    paper_results_index = {item["paper_id"]: item for item in batch_summary["results"]}
    paper_timelines = []
    for paper_span in paper_spans:
        paper_id = paper_span.get("paper_id")
        paper_timelines.append(
            {
                "paper_id": paper_id,
                "status": paper_span.get("status", "success"),
                "start_ms": paper_span["offset_ms"],
                "end_ms": paper_span["end_offset_ms"],
                "duration_ms": paper_span["duration_ms"],
                "result": paper_results_index.get(paper_id, {}),
                "phases": sorted(paper_phase_map.get(paper_id, []), key=lambda item: item["offset_ms"]),
                "agents": sorted(paper_agent_map.get(paper_id, []), key=lambda item: item["offset_ms"]),
            }
        )

    recent_events = [event for event in events if event["event"] not in {"span_start", "span_end"}][-50:]

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "config": {
            "mock_llm": config.mock_llm,
            "papers_per_worker": config.papers_per_worker,
            "llm_concurrency": config.llm_concurrency,
            "timeout_per_paper": config.timeout_per_paper,
            "max_retries": config.max_retries,
            "paper_count": len(paper_files),
        },
        "batch_summary": batch_summary,
        "wall_time_ms": round(wall_time_ms, 2),
        "peak_paper_concurrency": calc_max_concurrency(spans, "paper"),
        "peak_agent_concurrency": calc_max_concurrency(spans, "agent"),
        "peak_tool_concurrency": calc_max_concurrency(spans, "tool"),
        "phase_summary": phase_summary,
        "agent_summary": agent_summary,
        "tool_summary": tool_summary,
        "paper_timelines": paper_timelines,
        "recent_events": recent_events,
    }


def render_dashboard(summary: dict) -> str:
    data = json.dumps(summary, ensure_ascii=False)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>Agent Concurrency Dashboard</title>
  <style>
    :root {{
      --bg: #f5f1e8;
      --panel: #fffdf8;
      --ink: #172033;
      --muted: #5b6474;
      --accent: #b45309;
      --grid: #ddd2bf;
      --ok: #0f766e;
      --warn: #ea580c;
      --err: #b91c1c;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "IBM Plex Sans", "Source Han Sans SC", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(234, 88, 12, 0.08), transparent 28%),
        linear-gradient(180deg, #f7f1e6 0%, #efe7d8 100%);
    }}
    .wrap {{ max-width: 1480px; margin: 0 auto; padding: 28px; }}
    .hero {{
      display: grid;
      grid-template-columns: 2fr 1fr;
      gap: 18px;
      margin-bottom: 20px;
    }}
    .panel {{
      background: rgba(255, 253, 248, 0.94);
      border: 1px solid rgba(91, 100, 116, 0.16);
      border-radius: 18px;
      padding: 18px 20px;
      box-shadow: 0 10px 30px rgba(23, 32, 51, 0.06);
    }}
    h1, h2 {{ margin: 0 0 10px; font-family: "IBM Plex Serif", "Source Han Serif SC", serif; }}
    h1 {{ font-size: 32px; }}
    h2 {{ font-size: 20px; margin-top: 18px; }}
    .muted {{ color: var(--muted); }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      margin-top: 16px;
    }}
    .card {{
      background: #fff;
      border-radius: 14px;
      padding: 12px 14px;
      border: 1px solid rgba(91, 100, 116, 0.12);
    }}
    .card .value {{ font-size: 28px; font-weight: 700; }}
    .grid {{
      display: grid;
      grid-template-columns: 1.4fr 1fr;
      gap: 18px;
      margin-bottom: 18px;
    }}
    .bars {{ display: grid; gap: 10px; }}
    .bar-row {{
      display: grid;
      grid-template-columns: 190px 1fr 86px;
      align-items: center;
      gap: 10px;
      font-size: 13px;
    }}
    .track {{
      position: relative;
      min-height: 22px;
      background: repeating-linear-gradient(
        90deg,
        rgba(221, 210, 191, 0.55),
        rgba(221, 210, 191, 0.55) 1px,
        transparent 1px,
        transparent 8%
      );
      border-radius: 999px;
      overflow: hidden;
    }}
    .segment {{
      position: absolute;
      top: 0;
      bottom: 0;
      border-radius: 999px;
      opacity: 0.92;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    th, td {{
      padding: 8px 10px;
      text-align: left;
      border-bottom: 1px solid rgba(91, 100, 116, 0.12);
    }}
    .pill {{
      display: inline-block;
      padding: 2px 8px;
      border-radius: 999px;
      font-size: 12px;
      background: rgba(15, 118, 110, 0.12);
      color: var(--ok);
    }}
    .pill.warn {{ background: rgba(234, 88, 12, 0.12); color: var(--warn); }}
    .pill.err {{ background: rgba(185, 28, 28, 0.12); color: var(--err); }}
    .legend {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px 14px;
      margin-top: 8px;
      font-size: 12px;
      color: var(--muted);
    }}
    .legend span::before {{
      content: "";
      display: inline-block;
      width: 10px;
      height: 10px;
      border-radius: 999px;
      background: var(--c);
      margin-right: 6px;
    }}
    .events {{
      max-height: 320px;
      overflow: auto;
      display: grid;
      gap: 8px;
      font-size: 12px;
    }}
    .event {{
      padding: 8px 10px;
      border-radius: 12px;
      background: #fff;
      border: 1px solid rgba(91, 100, 116, 0.12);
    }}
    @media (max-width: 1100px) {{
      .hero, .grid {{ grid-template-columns: 1fr; }}
      .stats {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .bar-row {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="hero">
      <section class="panel">
        <h1>Reviewer-Aware Concurrency Benchmark</h1>
        <div class="muted">Batch concurrency benchmark and sub-agent scheduling visualization for OCR Markdown inputs.</div>
        <div class="stats" id="stats"></div>
      </section>
      <section class="panel">
        <h2>Configuration</h2>
        <table id="configTable"></table>
      </section>
    </div>

    <div class="grid">
      <section class="panel">
        <h2>Paper-Level Timeline</h2>
        <div class="muted">Each row is one paper; colored segments show phase execution intervals.</div>
        <div class="legend" id="legend"></div>
        <div class="bars" id="paperBars"></div>
      </section>
      <section class="panel">
        <h2>Phase Statistics</h2>
        <table id="phaseTable"></table>
      </section>
    </div>

    <div class="grid">
      <section class="panel">
        <h2>Sub-Agent Scheduling</h2>
        <div class="muted">Agent spans are grouped by paper to show concurrency overlap.</div>
        <div class="bars" id="agentBars"></div>
      </section>
      <section class="panel">
        <h2>Tool Calls</h2>
        <table id="toolTable"></table>
      </section>
    </div>

    <div class="grid">
      <section class="panel">
        <h2>Paper Results</h2>
        <table id="paperTable"></table>
      </section>
      <section class="panel">
        <h2>Recent Events</h2>
        <div class="events" id="eventList"></div>
      </section>
    </div>
  </div>

  <script>
    const data = {data};
    const phaseColors = {json.dumps(PHASE_COLORS, ensure_ascii=False)};
    const totalMs = Math.max(data.wall_time_ms, 1);

    function fmtMs(ms) {{
      if (ms >= 1000) return `${{(ms / 1000).toFixed(2)}}s`;
      return `${{ms.toFixed(0)}}ms`;
    }}

    function statusPill(status) {{
      const cls = status === "success" ? "" : status === "retry" ? "warn" : "err";
      return `<span class="pill ${{cls}}">${{status}}</span>`;
    }}

    function renderStats() {{
      const stats = [
        ["Total elapsed", fmtMs(data.wall_time_ms)],
        ["Peak paper concurrency", data.peak_paper_concurrency],
        ["Peak agent concurrency", data.peak_agent_concurrency],
        ["Peak tool concurrency", data.peak_tool_concurrency],
      ];
      document.getElementById("stats").innerHTML = stats.map(([label, value]) =>
        `<div class="card"><div class="muted">${{label}}</div><div class="value">${{value}}</div></div>`
      ).join("");
    }}

    function renderConfig() {{
      const rows = Object.entries(data.config).map(([k, v]) =>
        `<tr><th>${{k}}</th><td>${{v}}</td></tr>`
      );
      document.getElementById("configTable").innerHTML = rows.join("");
    }}

    function renderLegend() {{
      const items = Object.entries(phaseColors).map(([name, color]) =>
        `<span style="--c:${{color}}">${{name}}</span>`
      );
      document.getElementById("legend").innerHTML = items.join("");
    }}

    function phaseSegments(phases) {{
      return phases.map(phase => {{
        const left = (phase.offset_ms / totalMs) * 100;
        const width = (phase.duration_ms / totalMs) * 100;
        const color = phaseColors[phase.name] || "#64748b";
        return `<div class="segment" title="${{phase.name}} · ${{fmtMs(phase.duration_ms)}}" style="left:${{left}}%;width:${{Math.max(width, 0.8)}}%;background:${{color}}"></div>`;
      }}).join("");
    }}

    function agentSegments(agents) {{
      return agents.map(agent => {{
        const left = (agent.offset_ms / totalMs) * 100;
        const width = (agent.duration_ms / totalMs) * 100;
        const color = phaseColors[agent.phase] || "#64748b";
        return `<div class="segment" title="${{agent.agent}} · ${{fmtMs(agent.duration_ms)}}" style="left:${{left}}%;width:${{Math.max(width, 0.8)}}%;background:${{color}}"></div>`;
      }}).join("");
    }}

    function renderPaperBars() {{
      const rows = data.paper_timelines.map(item => `
        <div class="bar-row">
          <div><strong>${{item.paper_id}}</strong><div class="muted">${{item.result.status || item.status}}</div></div>
          <div class="track">${{phaseSegments(item.phases)}}</div>
          <div>${{fmtMs(item.duration_ms)}}</div>
        </div>
      `);
      document.getElementById("paperBars").innerHTML = rows.join("");
    }}

    function renderAgentBars() {{
      const rows = data.paper_timelines.map(item => `
        <div class="bar-row">
          <div><strong>${{item.paper_id}}</strong><div class="muted">${{item.agents.length}} agent spans</div></div>
          <div class="track">${{agentSegments(item.agents)}}</div>
          <div>${{item.agents.length}}</div>
        </div>
      `);
      document.getElementById("agentBars").innerHTML = rows.join("");
    }}

    function renderPhaseTable() {{
      const rows = data.phase_summary.map(item => `
        <tr>
          <th><span class="pill" style="background:${{item.color}}22;color:${{item.color}}">${{item.phase}}</span></th>
          <td>${{item.count}}</td>
          <td>${{fmtMs(item.avg_ms)}}</td>
          <td>${{fmtMs(item.max_ms)}}</td>
        </tr>
      `);
      document.getElementById("phaseTable").innerHTML = `
        <tr><th>phase</th><th>count</th><th>avg</th><th>max</th></tr>${{rows.join("")}}
      `;
    }}

    function renderToolTable() {{
      const rows = data.tool_summary.map(item => `
        <tr>
          <th>${{item.tool}}</th>
          <td>${{item.count}}</td>
          <td>${{item.errors}}</td>
          <td>${{fmtMs(item.avg_ms)}}</td>
          <td>${{fmtMs(item.max_ms)}}</td>
        </tr>
      `);
      document.getElementById("toolTable").innerHTML = `
        <tr><th>tool</th><th>count</th><th>errors</th><th>avg</th><th>max</th></tr>${{rows.join("")}}
      `;
    }}

    function renderPaperTable() {{
      const rows = data.paper_timelines.map(item => `
        <tr>
          <th>${{item.paper_id}}</th>
          <td>${{statusPill(item.result.status || item.status)}}</td>
          <td>${{item.result.antibodies ?? "-"}}</td>
          <td>${{fmtMs(item.duration_ms)}}</td>
        </tr>
      `);
      document.getElementById("paperTable").innerHTML = `
        <tr><th>paper</th><th>status</th><th>antibodies</th><th>duration</th></tr>${{rows.join("")}}
      `;
    }}

    function renderEvents() {{
      const rows = data.recent_events.slice().reverse().map(item => `
        <div class="event">
          <strong>${{item.event}}</strong> · ${{item.name}}
          <div class="muted">${{item.paper_id || "batch"}} · ${{fmtMs(item.offset_ms)}}</div>
        </div>
      `);
      document.getElementById("eventList").innerHTML = rows.join("");
    }}

    renderStats();
    renderConfig();
    renderLegend();
    renderPaperBars();
    renderAgentBars();
    renderPhaseTable();
    renderToolTable();
    renderPaperTable();
    renderEvents();
  </script>
</body>
</html>"""


async def main():
    args = parse_args()
    output_dir = args.output or default_output_dir()
    os.makedirs(output_dir, exist_ok=True)

    paper_files = discover_papers(args.ocr_dir)
    if not paper_files:
        raise RuntimeError(f"No OCR markdown files found under {args.ocr_dir}")

    tracer = TraceRecorder()
    config = Config(
        max_retries=args.max_retries,
        papers_per_worker=args.papers_per_worker,
        llm_concurrency=args.llm_concurrency,
        timeout_per_paper=args.timeout,
        enable_supplement=True,
        save_intermediate=args.keep_intermediate,
        trace_enabled=True,
        trace_recorder=tracer,
        mock_llm=not args.live,
    )
    if args.api_base:
        config.llm_api_base = args.api_base
    if args.api_key:
        config.llm_api_key = args.api_key
    if args.model:
        config.llm_model = args.model
        config.llm_review_model = args.model

    started = time.time()
    batch_summary = await run_batch(config, args.ocr_dir, output_dir)
    elapsed = round(time.time() - started, 2)

    trace_payload = tracer.snapshot()
    summary = summarise(trace_payload, batch_summary, config, paper_files)
    summary["driver_elapsed_seconds"] = elapsed

    summary_path = os.path.join(output_dir, "concurrency_report.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    dashboard_path = os.path.join(output_dir, "concurrency_dashboard.html")
    with open(dashboard_path, "w", encoding="utf-8") as f:
        f.write(render_dashboard(summary))

    print("\n" + "=" * 60)
    print(f"Concurrency benchmark complete in {elapsed}s")
    print(f"Output dir: {output_dir}")
    print(f"Report: {summary_path}")
    print(f"Dashboard: {dashboard_path}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
