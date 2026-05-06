#!/usr/bin/env python3
"""Trace visualization: terminal summary + HTML timeline from trace_events.json"""

import json
import sys
import os
from collections import defaultdict
from datetime import datetime

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box


def load_trace(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_spans(events: list) -> dict:
    """Match span_start/span_end events into completed spans."""
    open_spans = {}
    closed = []
    for ev in events:
        if ev["event"] == "span_start":
            open_spans[ev["span_id"]] = ev
        elif ev["event"] == "span_end":
            sid = ev["span_id"]
            if sid in open_spans:
                start_ev = open_spans.pop(sid)
                closed.append({
                    "span_id": sid,
                    "span_type": start_ev.get("span_type", ""),
                    "name": start_ev.get("name", ""),
                    "start_ms": start_ev["offset_ms"],
                    "end_ms": ev["offset_ms"],
                    "duration_ms": round(ev["offset_ms"] - start_ev["offset_ms"], 1),
                    "status": ev.get("status", "unknown"),
                    "start_fields": {k: v for k, v in start_ev.items()
                                     if k not in ("event", "span_id", "span_type", "name",
                                                   "timestamp", "offset_ms")},
                    "end_fields": {k: v for k, v in ev.items()
                                   if k not in ("event", "span_id", "status",
                                                 "timestamp", "offset_ms")},
                })
    return closed


def print_terminal_summary(trace: dict, console: Console):
    events = trace["events"]
    spans = build_spans(events)
    standalone = [e for e in events if e["event"] not in ("span_start", "span_end")]

    # ── Batch overview ──
    batch_spans = [s for s in spans if s["span_type"] == "batch"]
    if batch_spans:
        bs = batch_spans[0]
        total = bs["end_fields"].get("total_papers", "?")
        completed = bs["end_fields"].get("completed_papers", "?")
        console.print(Panel(
            f"[bold]Batch Run[/bold]  |  Papers: {completed}/{total}  |  "
            f"Duration: {bs['duration_ms']/1000:.1f}s  |  Status: {bs['status']}",
            title="Batch Summary", border_style="cyan",
        ))

    # ── Per-paper table ──
    paper_spans = [s for s in spans if s["span_type"] == "paper"]
    if paper_spans:
        table = Table(title="Per-Paper Results", box=box.ROUNDED, show_lines=True)
        table.add_column("Paper ID", style="bold")
        table.add_column("Status", justify="center")
        table.add_column("Duration", justify="right")
        table.add_column("Antibodies", justify="center")
        table.add_column("LLM Calls", justify="center")

        for ps in sorted(paper_spans, key=lambda x: x["start_ms"]):
            pid = ps["end_fields"].get("paper_id", ps["name"])
            status = ps["status"]
            style = "green" if status == "success" else "red" if status == "error" else "yellow"
            dur = f"{ps['duration_ms']/1000:.1f}s"
            ab = str(ps["end_fields"].get("antibody_count", "?"))
            # Count LLM tool spans for this paper
            llm_calls = sum(1 for s in spans
                            if s["span_type"] == "tool"
                            and s["start_fields"].get("paper_id") == pid)
            table.add_row(pid, Text(status, style=style), dur, ab, str(llm_calls))

        console.print(table)

    # ── Phase timeline per paper ──
    phase_spans = [s for s in spans if s["span_type"] == "phase"]
    papers = defaultdict(list)
    for ps in phase_spans:
        pid = ps["start_fields"].get("paper_id", "?")
        papers[pid].append(ps)

    if papers:
        table = Table(title="Phase Timeline", box=box.SIMPLE_HEAVY)
        table.add_column("Paper", style="bold", width=25)
        table.add_column("Phase", width=18)
        table.add_column("Duration", justify="right", width=10)
        table.add_column("Status", justify="center", width=10)
        table.add_column("Details", width=40)

        for pid in sorted(papers):
            phases = sorted(papers[pid], key=lambda x: x["start_ms"])
            for i, ph in enumerate(phases):
                details = []
                for k, v in ph["end_fields"].items():
                    if k not in ("status",):
                        details.append(f"{k}={v}")
                detail_str = ", ".join(details) if details else ""
                status_style = ("green" if ph["status"] == "success"
                                else "red" if ph["status"] == "error"
                                else "yellow")
                table.add_row(
                    pid if i == 0 else "",
                    ph["name"],
                    f"{ph['duration_ms']/1000:.1f}s",
                    Text(ph["status"], style=status_style),
                    detail_str[:60],
                )

        console.print(table)

    # ── Agent spans ──
    agent_spans = [s for s in spans if s["span_type"] == "agent"]
    if agent_spans:
        table = Table(title="Agent Invocations", box=box.SIMPLE)
        table.add_column("Paper", style="bold", width=25)
        table.add_column("Agent", width=15)
        table.add_column("Duration", justify="right", width=10)
        table.add_column("Status", justify="center", width=10)
        table.add_column("Details", width=50)

        for ag in sorted(agent_spans, key=lambda x: x["start_ms"]):
            pid = ag["start_fields"].get("paper_id", "?")
            details = []
            for k, v in ag["end_fields"].items():
                if k not in ("status",):
                    details.append(f"{k}={v}")
            status_style = ("green" if ag["status"] == "success"
                            else "red" if ag["status"] == "error"
                            else "yellow")
            table.add_row(
                pid, ag["name"],
                f"{ag['duration_ms']/1000:.1f}s",
                Text(ag["status"], style=status_style),
                ", ".join(details)[:70],
            )
        console.print(table)

    # ── Tool spans (LLM calls) ──
    tool_spans = [s for s in spans if s["span_type"] == "tool"]
    if tool_spans:
        table = Table(title="Tool Calls (LLM)", box=box.SIMPLE)
        table.add_column("Paper", style="bold", width=25)
        table.add_column("Tool", width=12)
        table.add_column("Model", width=30)
        table.add_column("Duration", justify="right", width=10)
        table.add_column("Tokens", justify="right", width=10)
        table.add_column("Status", justify="center", width=8)

        for ts in sorted(tool_spans, key=lambda x: x["start_ms"]):
            pid = ts["start_fields"].get("paper_id", "?")
            model = ts["start_fields"].get("model", "?")
            tokens = str(ts["end_fields"].get("total_tokens", "?"))
            status_style = "green" if ts["status"] == "success" else "red"
            table.add_row(
                pid, ts["name"],
                model[:30],
                f"{ts['duration_ms']/1000:.1f}s",
                tokens,
                Text(ts["status"], style=status_style),
            )
        console.print(table)

    # ── Standalone events ──
    if standalone:
        table = Table(title="Events", box=box.SIMPLE)
        table.add_column("Time (ms)", justify="right", width=12)
        table.add_column("Event", width=20)
        table.add_column("Name", width=20)
        table.add_column("Paper", width=25)
        table.add_column("Details", width=40)

        for ev in standalone[:50]:  # Cap at 50
            details = {k: v for k, v in ev.items()
                       if k not in ("event", "name", "timestamp", "offset_ms",
                                    "paper_id", "phase")}
            table.add_row(
                f"{ev['offset_ms']:.0f}",
                ev["event"],
                ev.get("name", ""),
                ev.get("paper_id", ""),
                str(details)[:60] if details else "",
            )
        console.print(table)


def generate_html_timeline(trace: dict, output_path: str):
    """Generate a self-contained HTML file with a Gantt-style timeline."""
    events = trace["events"]
    spans = build_spans(events)
    standalone = [e for e in events if e["event"] not in ("span_start", "span_end")]

    # Group by paper_id
    paper_data = defaultdict(list)
    for s in spans:
        pid = s.get("start_fields", {}).get("paper_id") or s.get("end_fields", {}).get("paper_id") or "batch"
        paper_data[pid].append(s)

    max_ms = max((s["end_ms"] for s in spans), default=1)

    # Color map
    colors = {
        "batch": "#607D8B",
        "paper": "#2196F3",
        "phase": "#4CAF50",
        "agent": "#FF9800",
        "tool": "#9C27B0",
    }
    status_colors = {
        "success": "#4CAF50",
        "error": "#F44336",
        "retry": "#FF9800",
        "unknown": "#9E9E9E",
    }

    rows_html = []
    row_idx = 0
    for pid in sorted(paper_data):
        group_spans = sorted(paper_data[pid], key=lambda x: x["start_ms"])
        for s in group_spans:
            left_pct = (s["start_ms"] / max_ms) * 100
            width_pct = max((s["duration_ms"] / max_ms) * 100, 0.3)
            bg = colors.get(s["span_type"], "#666")
            border_color = status_colors.get(s["status"], "#9E9E9E")
            label = f'{s["span_type"]}: {s["name"]}'
            tooltip = (f'{label}\\n'
                       f'Duration: {s["duration_ms"]/1000:.2f}s\\n'
                       f'Status: {s["status"]}\\n'
                       f'Paper: {pid}')
            rows_html.append(
                f'<div class="row" style="top:{row_idx * 28}px">'
                f'  <div class="label">{pid[:20]} / {s["name"]}</div>'
                f'  <div class="bar-area">'
                f'    <div class="bar" style="left:{left_pct}%;width:{width_pct}%;'
                f'background:{bg};border:2px solid {border_color}" '
                f'title="{tooltip}">'
                f'      <span class="bar-text">{s["duration_ms"]/1000:.1f}s</span>'
                f'    </div>'
                f'  </div>'
                f'</div>'
            )
            row_idx += 1

    # Event markers
    event_markers = []
    for ev in standalone:
        left_pct = (ev["offset_ms"] / max_ms) * 100
        event_markers.append(
            f'<div class="event-marker" style="left:calc(220px + {left_pct}% * 0.82)" '
            f'title="{ev["event"]}: {ev.get("name", "")} [{ev.get("paper_id", "")}]"></div>'
        )

    total_height = max(row_idx * 28 + 60, 200)

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>Pipeline Trace Timeline</title>
<style>
body {{ font-family: 'SF Mono', 'Fira Code', monospace; background: #1a1a2e; color: #eee; margin: 20px; }}
h1 {{ color: #00d2ff; font-size: 18px; }}
.info {{ color: #aaa; font-size: 13px; margin-bottom: 20px; }}
.legend {{ display: flex; gap: 16px; margin-bottom: 16px; font-size: 12px; }}
.legend-item {{ display: flex; align-items: center; gap: 4px; }}
.legend-dot {{ width: 12px; height: 12px; border-radius: 3px; }}
.timeline {{ position: relative; height: {total_height}px; overflow-x: auto; }}
.row {{ position: absolute; left: 0; right: 0; height: 24px; display: flex; }}
.label {{ width: 220px; min-width: 220px; font-size: 11px; color: #aaa; line-height: 24px;
           overflow: hidden; text-overflow: ellipsis; white-space: nowrap; padding-right: 8px; }}
.bar-area {{ flex: 1; position: relative; }}
.bar {{ position: absolute; height: 20px; top: 2px; border-radius: 4px; cursor: pointer;
         display: flex; align-items: center; justify-content: center; min-width: 2px;
         transition: opacity 0.2s; opacity: 0.85; }}
.bar:hover {{ opacity: 1; z-index: 10; }}
.bar-text {{ font-size: 10px; color: #fff; text-shadow: 0 1px 2px rgba(0,0,0,0.5); white-space: nowrap; }}
.event-marker {{ position: absolute; top: 0; width: 2px; height: 100%; background: rgba(255,255,0,0.3);
                  pointer-events: none; }}
.time-axis {{ display: flex; justify-content: space-between; padding-left: 220px; font-size: 11px;
              color: #666; margin-top: 8px; }}
</style></head><body>
<h1>Pipeline Trace Timeline</h1>
<div class="info">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Total duration: {max_ms/1000:.1f}s | Spans: {len(spans)} | Events: {len(standalone)}</div>
<div class="legend">
  <div class="legend-item"><div class="legend-dot" style="background:#2196F3"></div>Paper</div>
  <div class="legend-item"><div class="legend-dot" style="background:#4CAF50"></div>Phase</div>
  <div class="legend-item"><div class="legend-dot" style="background:#FF9800"></div>Agent</div>
  <div class="legend-item"><div class="legend-dot" style="background:#9C27B0"></div>Tool (LLM)</div>
  <div class="legend-item"><div class="legend-dot" style="background:#607D8B"></div>Batch</div>
</div>
<div class="timeline">
  {''.join(event_markers)}
  {''.join(rows_html)}
</div>
<div class="time-axis">
  <span>0s</span>
  <span>{max_ms/4000:.0f}s</span>
  <span>{max_ms/2000:.0f}s</span>
  <span>{max_ms*3/4000:.0f}s</span>
  <span>{max_ms/1000:.0f}s</span>
</div>
</body></html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    return output_path


def main():
    if len(sys.argv) < 2:
        print("Usage: python visualize_trace.py <trace_events.json> [--html output.html]")
        sys.exit(1)

    trace_path = sys.argv[1]
    trace = load_trace(trace_path)
    console = Console()

    # Terminal summary
    print_terminal_summary(trace, console)

    # HTML timeline
    html_path = None
    if "--html" in sys.argv:
        idx = sys.argv.index("--html")
        html_path = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else "trace_timeline.html"
    else:
        html_path = os.path.join(os.path.dirname(trace_path), "trace_timeline.html")

    generate_html_timeline(trace, html_path)
    console.print(f"\n[bold green]HTML timeline saved:[/bold green] {html_path}")


if __name__ == "__main__":
    main()
