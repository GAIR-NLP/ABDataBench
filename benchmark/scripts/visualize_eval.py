#!/usr/bin/env python3
"""Generate a self-contained HTML dashboard for benchmark evaluation results."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


FIELD_ORDER = [
    "CDRH3_Sequence",
    "vh_sequence_aa",
    "vl_sequence_aa",
    "Binding_Kinetics_KD",
    "Target_Name",
    "Epitope",
    "Antibody_Type",
    "Mechanism_of_Action",
    "Experiment",
    "Binding_Kinetics_kon",
    "Binding_Kinetics_koff",
    "Binding_EC50",
    "Structure",
    "source",
    "Reference_Source",
    "Target_Type",
    "Antibody_Isotype",
    "Cross_Reactivity",
    "Quantitative_Metric",
    "In_Vivo_Half_Life",
    "In_Vivo_Efficacy",
    "Thermal_Stability_Tm",
]

FIELD_WEIGHTS = {
    "CDRH3_Sequence": 2.0,
    "vh_sequence_aa": 2.0,
    "vl_sequence_aa": 2.0,
    "Binding_Kinetics_KD": 2.0,
    "Target_Name": 1.0,
    "Epitope": 1.0,
    "Antibody_Type": 1.0,
    "Mechanism_of_Action": 1.0,
    "Experiment": 1.0,
    "Binding_Kinetics_kon": 1.0,
    "Binding_Kinetics_koff": 1.0,
    "Binding_EC50": 1.0,
    "Structure": 1.0,
    "source": 0.5,
    "Reference_Source": 0.5,
    "Target_Type": 0.5,
    "Antibody_Isotype": 0.5,
    "Cross_Reactivity": 0.5,
    "Quantitative_Metric": 0.5,
    "In_Vivo_Half_Life": 0.5,
    "In_Vivo_Efficacy": 0.5,
    "Thermal_Stability_Tm": 0.5,
}

FIELD_LABELS = {
    "CDRH3_Sequence": "CDRH3",
    "vh_sequence_aa": "VH",
    "vl_sequence_aa": "VL",
    "Binding_Kinetics_KD": "KD",
    "Target_Name": "Target",
    "Epitope": "Epitope",
    "Antibody_Type": "Type",
    "Mechanism_of_Action": "MoA",
    "Experiment": "Experiment",
    "Binding_Kinetics_kon": "kon",
    "Binding_Kinetics_koff": "koff",
    "Binding_EC50": "EC50",
    "Structure": "Structure",
    "source": "Source",
    "Reference_Source": "Reference",
    "Target_Type": "Target Type",
    "Antibody_Isotype": "Isotype",
    "Cross_Reactivity": "Cross React",
    "Quantitative_Metric": "Metric",
    "In_Vivo_Half_Life": "Half-life",
    "In_Vivo_Efficacy": "In Vivo",
    "Thermal_Stability_Tm": "Tm",
}


def load_result(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_html(data: dict) -> str:
    payload = json.dumps(
        {
            "result": data,
            "fieldOrder": FIELD_ORDER,
            "fieldWeights": FIELD_WEIGHTS,
            "fieldLabels": FIELD_LABELS,
        },
        ensure_ascii=False,
    )

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Benchmark Evaluation Dashboard</title>
  <style>
    :root {{
      --bg: #f5f1e7;
      --bg2: #efe6d6;
      --panel: rgba(255, 251, 244, 0.92);
      --panel-strong: rgba(255, 253, 248, 0.98);
      --ink: #18212b;
      --muted: #62707f;
      --line: rgba(24, 33, 43, 0.12);
      --accent: #b45309;
      --accent-2: #0f766e;
      --danger: #b91c1c;
      --warn: #d97706;
      --ok: #15803d;
      --chip: rgba(24, 33, 43, 0.06);
      --shadow: 0 18px 60px rgba(39, 24, 10, 0.10);
      --radius-xl: 28px;
      --radius-lg: 20px;
      --radius-md: 14px;
      --mono: "IBM Plex Mono", "SFMono-Regular", Consolas, monospace;
      --sans: "IBM Plex Sans", "Source Han Sans SC", "PingFang SC", "Noto Sans CJK SC", sans-serif;
    }}
    * {{
      box-sizing: border-box;
    }}
    html, body {{
      margin: 0;
      min-height: 100%;
      background:
        radial-gradient(circle at top left, rgba(180, 83, 9, 0.16), transparent 22%),
        radial-gradient(circle at top right, rgba(15, 118, 110, 0.12), transparent 18%),
        linear-gradient(180deg, var(--bg) 0%, var(--bg2) 100%);
      color: var(--ink);
      font-family: var(--sans);
    }}
    body::before {{
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background-image:
        linear-gradient(rgba(24, 33, 43, 0.025) 1px, transparent 1px),
        linear-gradient(90deg, rgba(24, 33, 43, 0.025) 1px, transparent 1px);
      background-size: 24px 24px;
      mask-image: radial-gradient(circle at center, black 45%, transparent 100%);
    }}
    .wrap {{
      position: relative;
      max-width: 1560px;
      margin: 0 auto;
      padding: 30px 24px 60px;
    }}
    .hero {{
      display: grid;
      grid-template-columns: minmax(0, 1.5fr) minmax(320px, 0.9fr);
      gap: 18px;
      margin-bottom: 18px;
    }}
    .panel {{
      background: var(--panel);
      backdrop-filter: blur(14px);
      border: 1px solid var(--line);
      border-radius: var(--radius-xl);
      box-shadow: var(--shadow);
    }}
    .hero-main {{
      padding: 28px 30px 24px;
      overflow: hidden;
      position: relative;
    }}
    .hero-main::after {{
      content: "";
      position: absolute;
      width: 240px;
      height: 240px;
      right: -60px;
      top: -80px;
      border-radius: 50%;
      background: radial-gradient(circle, rgba(180, 83, 9, 0.22), transparent 70%);
    }}
    .kicker {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 7px 12px;
      border-radius: 999px;
      background: rgba(180, 83, 9, 0.10);
      color: #8a3d07;
      font-size: 12px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      font-weight: 700;
    }}
    h1 {{
      margin: 18px 0 10px;
      font-size: clamp(28px, 4vw, 52px);
      line-height: 0.98;
      letter-spacing: -0.04em;
      max-width: 12ch;
    }}
    .subtitle {{
      max-width: 72ch;
      color: var(--muted);
      font-size: 15px;
      line-height: 1.6;
      margin: 0 0 24px;
    }}
    .hero-meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }}
    .pill {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 10px 12px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.58);
      color: var(--muted);
      font-size: 13px;
    }}
    .pill strong {{
      color: var(--ink);
      font-weight: 700;
    }}
    .hero-side {{
      padding: 22px;
      display: grid;
      gap: 12px;
    }}
    .score-orb {{
      background:
        radial-gradient(circle at 50% 30%, rgba(255,255,255,0.92), rgba(255,255,255,0.18) 42%, transparent 43%),
        conic-gradient(from 220deg, #0f766e, #1d4ed8, #b45309, #0f766e);
      border-radius: 24px;
      padding: 22px;
      min-height: 240px;
      display: grid;
      place-items: center;
      position: relative;
      overflow: hidden;
    }}
    .score-orb::before {{
      content: "";
      position: absolute;
      inset: 16px;
      border-radius: 20px;
      background: rgba(255, 251, 244, 0.82);
      backdrop-filter: blur(8px);
      border: 1px solid rgba(255,255,255,0.55);
    }}
    .score-orb-inner {{
      position: relative;
      text-align: center;
      z-index: 1;
    }}
    .score-value {{
      font-size: clamp(54px, 8vw, 88px);
      line-height: 0.9;
      font-weight: 800;
      letter-spacing: -0.06em;
    }}
    .score-label {{
      margin-top: 8px;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      color: var(--muted);
      font-weight: 700;
    }}
    .mini-stats {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }}
    .mini-card {{
      background: rgba(255, 255, 255, 0.7);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 16px;
    }}
    .mini-card .label {{
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 8px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-weight: 700;
    }}
    .mini-card .value {{
      font-size: 26px;
      line-height: 1;
      font-weight: 800;
      letter-spacing: -0.04em;
    }}
    .mini-card .sub {{
      color: var(--muted);
      font-size: 12px;
      margin-top: 6px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: minmax(0, 1.25fr) minmax(420px, 0.9fr);
      gap: 18px;
      align-items: start;
    }}
    .section {{
      padding: 22px;
      margin-bottom: 18px;
    }}
    .section-head {{
      display: flex;
      align-items: end;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 18px;
    }}
    .section-head h2 {{
      margin: 0;
      font-size: 20px;
      letter-spacing: -0.03em;
    }}
    .section-head p {{
      margin: 4px 0 0;
      color: var(--muted);
      font-size: 13px;
    }}
    .controls {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-bottom: 14px;
    }}
    .control {{
      min-width: 0;
      padding: 11px 12px;
      border: 1px solid var(--line);
      border-radius: 14px;
      background: rgba(255, 255, 255, 0.72);
      color: var(--ink);
      font: inherit;
    }}
    .paper-list {{
      display: grid;
      gap: 12px;
      max-height: 980px;
      overflow: auto;
      padding-right: 4px;
    }}
    .paper-card {{
      border: 1px solid var(--line);
      border-radius: 20px;
      padding: 16px;
      background: rgba(255, 255, 255, 0.72);
      cursor: pointer;
      transition: transform 120ms ease, border-color 120ms ease, box-shadow 120ms ease;
    }}
    .paper-card:hover {{
      transform: translateY(-1px);
      box-shadow: 0 10px 24px rgba(24, 33, 43, 0.08);
      border-color: rgba(15, 118, 110, 0.30);
    }}
    .paper-card.active {{
      border-color: rgba(15, 118, 110, 0.55);
      box-shadow: inset 0 0 0 1px rgba(15, 118, 110, 0.28);
      background: rgba(242, 251, 249, 0.94);
    }}
    .paper-top {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: start;
      margin-bottom: 12px;
    }}
    .paper-name {{
      font-size: 15px;
      line-height: 1.35;
      font-weight: 700;
    }}
    .grade {{
      font-family: var(--mono);
      padding: 6px 9px;
      border-radius: 999px;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: white;
      flex: none;
    }}
    .paper-score-row {{
      display: grid;
      grid-template-columns: 90px 1fr 58px;
      gap: 10px;
      align-items: center;
      margin-bottom: 12px;
    }}
    .paper-score {{
      font-size: 30px;
      line-height: 1;
      font-weight: 800;
      letter-spacing: -0.05em;
    }}
    .bar-track {{
      position: relative;
      height: 14px;
      border-radius: 999px;
      overflow: hidden;
      background: rgba(24, 33, 43, 0.10);
    }}
    .bar-raw, .bar-final {{
      position: absolute;
      inset: 0 auto 0 0;
      border-radius: inherit;
    }}
    .bar-raw {{
      background: rgba(29, 78, 216, 0.18);
    }}
    .bar-final {{
      background: linear-gradient(90deg, #0f766e, #b45309);
    }}
    .score-delta {{
      text-align: right;
      color: var(--muted);
      font-size: 12px;
      font-family: var(--mono);
    }}
    .paper-metrics {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}
    .metric-chip {{
      background: var(--chip);
      border-radius: 999px;
      padding: 7px 10px;
      color: var(--muted);
      font-size: 12px;
    }}
    .metric-chip strong {{
      color: var(--ink);
    }}
    .detail-shell {{
      position: sticky;
      top: 18px;
    }}
    .detail-empty {{
      color: var(--muted);
      min-height: 420px;
      display: grid;
      place-items: center;
      text-align: center;
      padding: 30px;
    }}
    .detail-head {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: start;
      margin-bottom: 14px;
    }}
    .detail-head h3 {{
      margin: 0;
      font-size: 28px;
      line-height: 1.02;
      letter-spacing: -0.04em;
    }}
    .detail-sub {{
      color: var(--muted);
      font-size: 13px;
      margin-top: 8px;
    }}
    .detail-stats {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      margin: 14px 0 18px;
    }}
    .detail-stat {{
      background: rgba(255,255,255,0.66);
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 14px 12px;
    }}
    .detail-stat .label {{
      font-size: 11px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-bottom: 8px;
      font-weight: 700;
    }}
    .detail-stat .value {{
      font-size: 26px;
      font-weight: 800;
      line-height: 1;
      letter-spacing: -0.05em;
    }}
    .field-leaderboard {{
      display: grid;
      gap: 10px;
      margin-top: 8px;
    }}
    .field-row {{
      display: grid;
      grid-template-columns: 120px 1fr 48px;
      gap: 10px;
      align-items: center;
    }}
    .field-label {{
      display: flex;
      justify-content: space-between;
      gap: 8px;
      font-size: 12px;
      color: var(--muted);
    }}
    .field-weight {{
      font-family: var(--mono);
    }}
    .stack {{
      display: flex;
      height: 14px;
      overflow: hidden;
      border-radius: 999px;
      background: rgba(24, 33, 43, 0.08);
    }}
    .seg {{
      height: 100%;
    }}
    .seg.exact {{ background: var(--ok); }}
    .seg.partial {{ background: var(--warn); }}
    .seg.wrong {{ background: var(--danger); }}
    .seg.miss {{ background: #7a8693; }}
    .field-rate {{
      text-align: right;
      font-size: 12px;
      font-weight: 700;
    }}
    .legend {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px 14px;
      color: var(--muted);
      font-size: 12px;
      margin-top: 14px;
    }}
    .legend span {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }}
    .legend i {{
      width: 10px;
      height: 10px;
      border-radius: 2px;
      display: inline-block;
    }}
    .antibody-list {{
      display: grid;
      gap: 10px;
      margin-top: 18px;
      max-height: 860px;
      overflow: auto;
      padding-right: 4px;
    }}
    .antibody-card {{
      border: 1px solid var(--line);
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.74);
      overflow: hidden;
    }}
    .antibody-head {{
      padding: 14px 16px;
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto auto;
      gap: 10px;
      align-items: center;
      cursor: pointer;
    }}
    .antibody-name {{
      font-weight: 700;
      font-size: 14px;
    }}
    .match-badge {{
      font-size: 11px;
      font-weight: 700;
      padding: 5px 8px;
      border-radius: 999px;
    }}
    .match-true {{
      background: rgba(21, 128, 61, 0.10);
      color: var(--ok);
    }}
    .match-false {{
      background: rgba(185, 28, 28, 0.10);
      color: var(--danger);
    }}
    .antibody-score {{
      font-family: var(--mono);
      font-weight: 700;
    }}
    .antibody-body {{
      display: none;
      padding: 0 16px 16px;
      border-top: 1px solid var(--line);
      background: rgba(255, 252, 248, 0.86);
    }}
    .antibody-card.open .antibody-body {{
      display: block;
    }}
    .field-table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 10px;
      font-size: 12px;
    }}
    .field-table th, .field-table td {{
      border-bottom: 1px solid rgba(24, 33, 43, 0.08);
      padding: 9px 8px;
      text-align: left;
      vertical-align: top;
    }}
    .field-table th {{
      color: var(--muted);
      font-weight: 700;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .field-badge {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      border-radius: 999px;
      padding: 5px 8px;
      font-size: 11px;
      font-weight: 700;
      white-space: nowrap;
    }}
    .field-badge.exact {{ background: rgba(21, 128, 61, 0.12); color: var(--ok); }}
    .field-badge.partial {{ background: rgba(217, 119, 6, 0.12); color: var(--warn); }}
    .field-badge.wrong {{ background: rgba(185, 28, 28, 0.12); color: var(--danger); }}
    .field-badge.miss {{ background: rgba(100, 116, 139, 0.12); color: #475569; }}
    .field-badge.skip {{ background: rgba(148, 163, 184, 0.12); color: #64748b; }}
    .field-value {{
      max-width: 340px;
      white-space: pre-wrap;
      word-break: break-word;
      color: var(--ink);
    }}
    .reason {{
      color: var(--muted);
      max-width: 420px;
      white-space: pre-wrap;
      word-break: break-word;
    }}
    .footer {{
      text-align: center;
      color: var(--muted);
      font-size: 12px;
      padding-top: 10px;
    }}
    @media (max-width: 1200px) {{
      .hero, .grid {{
        grid-template-columns: 1fr;
      }}
      .detail-shell {{
        position: static;
      }}
    }}
    @media (max-width: 760px) {{
      .wrap {{
        padding: 16px 14px 40px;
      }}
      .hero-main, .hero-side, .section {{
        padding: 18px;
      }}
      .mini-stats, .detail-stats {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}
      .paper-score-row {{
        grid-template-columns: 1fr;
      }}
      .field-row {{
        grid-template-columns: 96px 1fr 42px;
      }}
      .antibody-head {{
        grid-template-columns: 1fr;
      }}
      .field-table {{
        display: block;
        overflow-x: auto;
      }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="hero">
      <div class="panel hero-main">
        <div class="kicker">Benchmark Report</div>
        <h1>26-Paper Antibody Extraction Review</h1>
        <p class="subtitle">
          A static, filterable, expandable evaluation dashboard for paper-level
          scores, global field quality, and per-paper antibody details.
        </p>
        <div class="hero-meta" id="hero-meta"></div>
      </div>
      <div class="panel hero-side">
        <div class="score-orb">
          <div class="score-orb-inner">
            <div class="score-value" id="overall-score"></div>
            <div class="score-label">Overall Score</div>
          </div>
        </div>
        <div class="mini-stats" id="mini-stats"></div>
      </div>
    </section>

    <section class="grid">
      <div>
        <div class="panel section">
          <div class="section-head">
            <div>
              <h2>Paper Explorer</h2>
              <p>Filter by score, extra predictions, and missing records. Select a paper to inspect antibody details.</p>
            </div>
          </div>
          <div class="controls">
            <input id="search" class="control" type="search" placeholder="Search paper name">
            <select id="sort" class="control">
              <option value="score-desc">Final score descending</option>
              <option value="score-asc">Final score ascending</option>
              <option value="fp-desc">Extra predictions descending</option>
              <option value="fn-desc">Missing records descending</option>
              <option value="name-asc">Name ascending</option>
            </select>
            <select id="filter" class="control">
              <option value="all">All papers</option>
              <option value="high">High score 70+</option>
              <option value="mid">Mid score 40-70</option>
              <option value="low">Low score under 40</option>
              <option value="hallucination">Has extra predictions</option>
              <option value="missing">Has missing records</option>
            </select>
          </div>
          <div class="paper-list" id="paper-list"></div>
        </div>
      </div>

      <div class="detail-shell">
        <div class="panel section">
          <div class="section-head">
            <div>
              <h2>Field Quality</h2>
              <p>Global exact / partial / wrong / miss distribution by field.</p>
            </div>
          </div>
          <div class="field-leaderboard" id="field-leaderboard"></div>
          <div class="legend">
            <span><i style="background: var(--ok)"></i>Exact</span>
            <span><i style="background: var(--warn)"></i>Partial</span>
            <span><i style="background: var(--danger)"></i>Wrong</span>
            <span><i style="background: #7a8693"></i>Miss</span>
          </div>
        </div>

        <div class="panel section" id="detail-panel">
          <div class="detail-empty">Select a paper on the left to inspect matches, missing records, extra predictions, and field details.</div>
        </div>
      </div>
    </section>

    <div class="footer">
      Generated by <code>benchmark/scripts/visualize_eval.py</code>
    </div>
  </div>

  <script>
    const PAYLOAD = {payload};
    const result = PAYLOAD.result;
    const papers = result.papers.slice();
    const fieldOrder = PAYLOAD.fieldOrder;
    const fieldWeights = PAYLOAD.fieldWeights;
    const fieldLabels = PAYLOAD.fieldLabels;

    let selectedPaperId = papers.length ? papers[0].paper_id : null;

    function gradeForScore(score) {{
      if (score >= 85) return ['S', '#0f766e'];
      if (score >= 70) return ['A', '#3f7c2f'];
      if (score >= 55) return ['B', '#b45309'];
      if (score >= 40) return ['C', '#d97706'];
      if (score >= 25) return ['D', '#b45309'];
      return ['F', '#b91c1c'];
    }}

    function fmt(value, digits = 1) {{
      return Number(value || 0).toFixed(digits);
    }}

    function escapeHtml(value) {{
      return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    }}

    function truncate(value, max = 140) {{
      const text = String(value ?? '');
      return text.length > max ? text.slice(0, max) + '…' : text;
    }}

    function matchedTotals() {{
      let matched = 0;
      let gt = 0;
      let pred = 0;
      let fp = 0;
      let fn = 0;
      papers.forEach((paper) => {{
        matched += paper.matched;
        gt += paper.gt_count;
        pred += paper.pred_count;
        fp += paper.false_positive;
        fn += paper.false_negative;
      }});
      return {{ matched, gt, pred, fp, fn }};
    }}

    function renderHero() {{
      const totals = matchedTotals();
      document.getElementById('overall-score').textContent = fmt(result.accuracy, 2);

      const heroMeta = document.getElementById('hero-meta');
      heroMeta.innerHTML = [
        ['Papers', papers.length],
        ['Matched / GT', `${{totals.matched}} / ${{totals.gt}}`],
        ['Predicted Records', totals.pred],
        ['Weighted Score', `${{fmt(result.total_weighted_score, 1)}} / ${{fmt(result.total_weight, 1)}}`],
      ].map(([label, value]) => `<span class="pill"><strong>${{escapeHtml(value)}}</strong> ${{escapeHtml(label)}}</span>`).join('');

      const miniStats = document.getElementById('mini-stats');
      const rawRate = result.total_fields ? (result.total_score / result.total_fields) * 100 : 0;
      const weightedRate = result.total_weight ? (result.total_weighted_score / result.total_weight) * 100 : 0;
      const topPaper = papers.reduce((best, paper) => paper.accuracy > best.accuracy ? paper : best, papers[0]);
      const noisestPaper = papers.reduce((best, paper) => paper.false_positive > best.false_positive ? paper : best, papers[0]);
      const stats = [
        {{ label: 'Raw Avg', value: fmt(rawRate, 1), sub: `${{fmt(result.total_score, 1)}} / ${{result.total_fields}}` }},
        {{ label: 'Weighted Avg', value: fmt(weightedRate, 1), sub: `${{fmt(result.total_weighted_score, 1)}} / ${{fmt(result.total_weight, 1)}}` }},
        {{ label: 'Best Paper', value: fmt(topPaper.accuracy, 1), sub: topPaper.paper_id }},
        {{ label: 'Most Hallucinations', value: noisestPaper.false_positive, sub: noisestPaper.paper_id }},
      ];
      miniStats.innerHTML = stats.map((stat) => `
        <div class="mini-card">
          <div class="label">${{escapeHtml(stat.label)}}</div>
          <div class="value">${{escapeHtml(stat.value)}}</div>
          <div class="sub">${{escapeHtml(stat.sub)}}</div>
        </div>
      `).join('');
    }}

    function buildPaperCard(paper) {{
      const [grade, color] = gradeForScore(paper.accuracy);
      const rawWidth = Math.max(0, Math.min(100, paper.raw_accuracy));
      const finalWidth = Math.max(0, Math.min(100, paper.accuracy));
      const isActive = paper.paper_id === selectedPaperId;
      return `
        <article class="paper-card ${{isActive ? 'active' : ''}}" data-paper-id="${{escapeHtml(paper.paper_id)}}">
          <div class="paper-top">
            <div class="paper-name">${{escapeHtml(paper.paper_id)}}</div>
            <span class="grade" style="background:${{color}}">${{grade}}</span>
          </div>
          <div class="paper-score-row">
            <div class="paper-score">${{fmt(paper.accuracy, 1)}}</div>
            <div class="bar-track">
              <div class="bar-raw" style="width:${{rawWidth}}%"></div>
              <div class="bar-final" style="width:${{finalWidth}}%"></div>
            </div>
            <div class="score-delta">raw ${{fmt(paper.raw_accuracy, 1)}}</div>
          </div>
          <div class="paper-metrics">
            <span class="metric-chip"><strong>${{paper.matched}}</strong> matched / ${{paper.gt_count}} GT</span>
            <span class="metric-chip"><strong>${{paper.false_negative}}</strong> missing</span>
            <span class="metric-chip"><strong>${{paper.false_positive}}</strong> hallucinations</span>
            <span class="metric-chip">penalty <strong>${{fmt(paper.penalty_coeff, 2)}}</strong></span>
          </div>
        </article>
      `;
    }}

    function filteredPapers() {{
      const search = document.getElementById('search').value.trim().toLowerCase();
      const sort = document.getElementById('sort').value;
      const filter = document.getElementById('filter').value;

      let items = papers.filter((paper) => paper.paper_id.toLowerCase().includes(search));
      if (filter === 'high') items = items.filter((paper) => paper.accuracy >= 70);
      if (filter === 'mid') items = items.filter((paper) => paper.accuracy >= 40 && paper.accuracy < 70);
      if (filter === 'low') items = items.filter((paper) => paper.accuracy < 40);
      if (filter === 'hallucination') items = items.filter((paper) => paper.false_positive > 0);
      if (filter === 'missing') items = items.filter((paper) => paper.false_negative > 0);

      const sorters = {{
        'score-desc': (a, b) => b.accuracy - a.accuracy,
        'score-asc': (a, b) => a.accuracy - b.accuracy,
        'fp-desc': (a, b) => b.false_positive - a.false_positive || b.accuracy - a.accuracy,
        'fn-desc': (a, b) => b.false_negative - a.false_negative || a.accuracy - b.accuracy,
        'name-asc': (a, b) => a.paper_id.localeCompare(b.paper_id),
      }};
      items.sort(sorters[sort]);
      return items;
    }}

    function renderPaperList() {{
      const container = document.getElementById('paper-list');
      const items = filteredPapers();
      if (!items.some((paper) => paper.paper_id === selectedPaperId)) {{
        selectedPaperId = items.length ? items[0].paper_id : null;
      }}
      container.innerHTML = items.length
        ? items.map(buildPaperCard).join('')
        : '<div class="detail-empty">No papers match the current filters.</div>';
      container.querySelectorAll('.paper-card').forEach((card) => {{
        card.addEventListener('click', () => {{
          selectedPaperId = card.dataset.paperId;
          renderPaperList();
          renderDetail();
        }});
      }});
    }}

    function aggregateFieldStats() {{
      const stats = Object.fromEntries(fieldOrder.map((field) => [field, {{
        exact: 0, partial: 0, wrong: 0, miss: 0, total: 0,
      }}]));
      papers.forEach((paper) => {{
        paper.antibodies.forEach((ab) => {{
          ab.fields.forEach((field) => {{
            if (!stats[field.field] || field.label === 'skip') return;
            stats[field.field][field.label] += 1;
            stats[field.field].total += 1;
          }});
        }});
      }});
      return stats;
    }}

    function renderFieldLeaderboard() {{
      const stats = aggregateFieldStats();
      const container = document.getElementById('field-leaderboard');
      container.innerHTML = fieldOrder.map((field) => {{
        const item = stats[field];
        const total = item.total || 1;
        const exact = item.exact / total * 100;
        const partial = item.partial / total * 100;
        const wrong = item.wrong / total * 100;
        const miss = item.miss / total * 100;
        const quality = (item.exact + item.partial * 0.5) / total * 100;
        return `
          <div class="field-row">
            <div class="field-label">
              <span>${{escapeHtml(fieldLabels[field] || field)}}</span>
              <span class="field-weight">w=${{fieldWeights[field]}}</span>
            </div>
            <div class="stack" title="exact ${{item.exact}}, partial ${{item.partial}}, wrong ${{item.wrong}}, miss ${{item.miss}}">
              <div class="seg exact" style="width:${{exact}}%"></div>
              <div class="seg partial" style="width:${{partial}}%"></div>
              <div class="seg wrong" style="width:${{wrong}}%"></div>
              <div class="seg miss" style="width:${{miss}}%"></div>
            </div>
            <div class="field-rate">${{fmt(quality, 0)}}%</div>
          </div>
        `;
      }}).join('');
    }}

    function summarizeFieldQuality(paper) {{
      const stats = Object.fromEntries(fieldOrder.map((field) => [field, {{
        exact: 0, partial: 0, wrong: 0, miss: 0, total: 0,
      }}]));
      paper.antibodies.forEach((ab) => {{
        ab.fields.forEach((field) => {{
          if (!stats[field.field] || field.label === 'skip') return;
          stats[field.field][field.label] += 1;
          stats[field.field].total += 1;
        }});
      }});
      return fieldOrder.map((field) => {{
        const item = stats[field];
        const total = item.total || 1;
        return {{
          field,
          exact: item.exact / total * 100,
          partial: item.partial / total * 100,
          wrong: item.wrong / total * 100,
          miss: item.miss / total * 100,
          quality: (item.exact + item.partial * 0.5) / total * 100,
        }};
      }});
    }}

    function renderAntibodyCard(ab, index) {{
      const rows = fieldOrder.map((fieldName) => {{
        const field = ab.fields.find((item) => item.field === fieldName);
        if (!field) return '';
        const label = field.label;
        return `
          <tr>
            <td>${{escapeHtml(fieldLabels[field.field] || field.field)}}</td>
            <td>${{field.weight}}</td>
            <td><span class="field-badge ${{label}}">${{escapeHtml(label)}} · ${{field.score}}</span></td>
            <td><div class="field-value">${{escapeHtml(truncate(field.gt, 180) || '∅')}}</div></td>
            <td><div class="field-value">${{escapeHtml(truncate(field.pred, 180) || '∅')}}</div></td>
            <td><div class="reason">${{escapeHtml(truncate(field.reason, 220) || '—')}}</div></td>
          </tr>
        `;
      }}).join('');

      return `
        <article class="antibody-card ${{index === 0 ? 'open' : ''}}">
          <div class="antibody-head">
            <div class="antibody-name">${{escapeHtml(ab.name)}}</div>
            <span class="match-badge ${{ab.matched ? 'match-true' : 'match-false'}}">
              ${{ab.matched ? 'Matched' : 'Unmatched'}}
            </span>
            <div class="antibody-score">${{fmt(ab.accuracy, 1)}}</div>
          </div>
          <div class="antibody-body">
            <table class="field-table">
              <thead>
                <tr>
                  <th>Field</th>
                  <th>Weight</th>
                  <th>Judge</th>
                  <th>GT</th>
                  <th>Prediction</th>
                  <th>Reason</th>
                </tr>
              </thead>
              <tbody>${{rows}}</tbody>
            </table>
          </div>
        </article>
      `;
    }}

    function renderDetail() {{
      const panel = document.getElementById('detail-panel');
      const paper = papers.find((item) => item.paper_id === selectedPaperId);
      if (!paper) {{
        panel.innerHTML = '<div class="detail-empty">The selected paper was not found.</div>';
        return;
      }}

      const [grade, color] = gradeForScore(paper.accuracy);
      const fieldSummary = summarizeFieldQuality(paper)
        .sort((a, b) => b.quality - a.quality)
        .slice(0, 8);

      panel.innerHTML = `
        <div class="detail-head">
          <div>
            <h3>${{escapeHtml(paper.paper_id)}}</h3>
            <div class="detail-sub">
              raw ${{fmt(paper.raw_accuracy, 1)}} / final ${{fmt(paper.accuracy, 1)}} / penalty ${{fmt(paper.penalty_coeff, 2)}}
            </div>
          </div>
          <span class="grade" style="background:${{color}}">${{grade}}</span>
        </div>

        <div class="detail-stats">
          <div class="detail-stat">
            <div class="label">Matched</div>
            <div class="value">${{paper.matched}}</div>
          </div>
          <div class="detail-stat">
            <div class="label">Missing</div>
            <div class="value">${{paper.false_negative}}</div>
          </div>
          <div class="detail-stat">
            <div class="label">Hallucinations</div>
            <div class="value">${{paper.false_positive}}</div>
          </div>
          <div class="detail-stat">
            <div class="label">Predicted</div>
            <div class="value">${{paper.pred_count}}</div>
          </div>
        </div>

        <div class="section-head" style="margin-top:8px">
          <div>
            <h2 style="font-size:18px">Top Field Quality</h2>
            <p>Highest-quality fields in this paper, ranked by exact + 0.5 x partial.</p>
          </div>
        </div>
        <div class="field-leaderboard">
          ${{fieldSummary.map((item) => `
            <div class="field-row">
              <div class="field-label">
                <span>${{escapeHtml(fieldLabels[item.field] || item.field)}}</span>
                <span class="field-weight">w=${{fieldWeights[item.field]}}</span>
              </div>
              <div class="stack">
                <div class="seg exact" style="width:${{item.exact}}%"></div>
                <div class="seg partial" style="width:${{item.partial}}%"></div>
                <div class="seg wrong" style="width:${{item.wrong}}%"></div>
                <div class="seg miss" style="width:${{item.miss}}%"></div>
              </div>
              <div class="field-rate">${{fmt(item.quality, 0)}}%</div>
            </div>
          `).join('')}}
        </div>

        <div class="section-head" style="margin-top:22px">
          <div>
            <h2 style="font-size:18px">Antibody Details</h2>
            <p>${{paper.antibodies.length}} records. Select a card to expand field-level evaluation.</p>
          </div>
        </div>
        <div class="antibody-list">
          ${{paper.antibodies.map((ab, index) => renderAntibodyCard(ab, index)).join('')}}
        </div>
      `;

      panel.querySelectorAll('.antibody-card').forEach((card) => {{
        const head = card.querySelector('.antibody-head');
        head.addEventListener('click', () => {{
          card.classList.toggle('open');
        }});
      }});
    }}

    document.getElementById('search').addEventListener('input', renderPaperList);
    document.getElementById('sort').addEventListener('change', renderPaperList);
    document.getElementById('filter').addEventListener('change', renderPaperList);

    renderHero();
    renderFieldLeaderboard();
    renderPaperList();
    renderDetail();
  </script>
</body>
</html>"""


def generate_dashboard(data: dict, output_path: str) -> str:
    html = build_html(data)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    return output_path


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python visualize_eval.py <eval_result.json> [--output dashboard.html]")
        sys.exit(1)

    result_path = Path(sys.argv[1]).resolve()
    data = load_result(str(result_path))

    if "--output" in sys.argv:
      idx = sys.argv.index("--output")
      if idx + 1 >= len(sys.argv):
          print("Missing output path after --output")
          sys.exit(1)
      output_path = Path(sys.argv[idx + 1]).resolve()
    else:
      output_path = result_path.with_name("eval_dashboard.html")

    generate_dashboard(data, str(output_path))
    print(f"Dashboard saved: {output_path}")


if __name__ == "__main__":
    main()
