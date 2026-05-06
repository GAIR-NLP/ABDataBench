#!/usr/bin/env python3
"""Run extraction, benchmark evaluation, and static dashboard serving."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run document sequence extraction, benchmark evaluation, and dashboard generation."
    )
    parser.add_argument(
        "--ocr-dir",
        default="dataset",
        help="Directory containing OCR markdown paper folders",
    )
    parser.add_argument("--output-root", default="runs", help="Root directory for run artifacts")
    parser.add_argument("--run-name", default="", help="Run name; defaults to timestamp")
    parser.add_argument(
        "--gt",
        default="benchmark/ground_truth/ground_truth.json",
        help="Ground-truth JSON path",
    )
    parser.add_argument("--subset", default="all", choices=["all", "paper", "patent"], help="Benchmark subset")
    parser.add_argument("--papers", nargs="*", help="Optional paper IDs to evaluate")
    parser.add_argument("--papers-per-worker", type=int, default=4, help="Agent paper concurrency")
    parser.add_argument("--llm-concurrency", type=int, default=8, help="Shared LLM concurrency")
    parser.add_argument("--paper-concurrency", type=int, default=5, help="Benchmark paper concurrency")
    parser.add_argument("--model", default="", help="Extraction LLM model; defaults to LLM_MODEL")
    parser.add_argument("--api-base", default="", help="Extraction LLM API base; defaults to LLM_API_BASE")
    parser.add_argument("--api-key", default="", help="Extraction LLM API key; defaults to LLM_API_KEY")
    parser.add_argument("--judge-model", default="", help="Benchmark judge model; defaults to BENCHMARK_MODEL")
    parser.add_argument("--judge-base-url", default="", help="Benchmark judge API base")
    parser.add_argument("--judge-api-key", default="", help="Benchmark judge API key")
    parser.add_argument("--mock-llm", action="store_true", help="Use mock LLM for extraction smoke tests")
    parser.add_argument("--trace", action="store_true", help="Record agent trace_events.json")
    parser.add_argument("--skip-eval", action="store_true", help="Only run extraction")
    parser.add_argument("--serve", action="store_true", help="Serve the generated dashboard over HTTP")
    parser.add_argument("--host", default="127.0.0.1", help="HTTP host for --serve")
    parser.add_argument("--port", type=int, default=8000, help="HTTP port for --serve")
    return parser.parse_args()


def run_command(cmd: list[str], *, cwd: Path, env: dict[str, str]) -> None:
    display = " ".join(str(part) for part in cmd)
    print(f"\n$ {display}", flush=True)
    subprocess.run(cmd, cwd=str(cwd), env=env, check=True)


def first_env(*names: str) -> str:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def main() -> int:
    args = parse_args()
    env = os.environ.copy()

    if args.api_key:
        env["LLM_API_KEY"] = args.api_key
    if args.api_base:
        env["LLM_API_BASE"] = args.api_base
    if args.model:
        env["LLM_MODEL"] = args.model

    llm_api_key = env.get("LLM_API_KEY", "").strip()
    if not args.mock_llm and not llm_api_key:
        print("LLM_API_KEY is required for live extraction. Pass --api-key or set LLM_API_KEY.", file=sys.stderr)
        return 2

    run_name = args.run_name or datetime.now().strftime("%Y%m%d_%H%M%S")
    run_root = (REPO_ROOT / args.output_root / run_name).resolve()
    agent_output = run_root / "agent"
    eval_output = run_root / "benchmark"
    agent_output.mkdir(parents=True, exist_ok=True)

    ocr_dir = Path(args.ocr_dir).expanduser()
    if not ocr_dir.is_absolute():
        ocr_dir = REPO_ROOT / ocr_dir

    agent_cmd = [
        sys.executable,
        str(REPO_ROOT / "agent" / "main.py"),
        "--batch",
        str(ocr_dir.resolve()),
        "-o",
        str(agent_output),
        "--papers-per-worker",
        str(args.papers_per_worker),
        "--llm-concurrency",
        str(args.llm_concurrency),
    ]
    if args.mock_llm:
        agent_cmd.append("--mock-llm")
    if args.trace:
        agent_cmd.append("--trace")
    if args.model:
        agent_cmd.extend(["--model", args.model])
    if args.api_base:
        agent_cmd.extend(["--api-base", args.api_base])
    if args.api_key:
        agent_cmd.extend(["--api-key", args.api_key])

    run_command(agent_cmd, cwd=REPO_ROOT, env=env)

    prediction_path = agent_output / "benchmark_predictions.json"
    if args.skip_eval:
        print(f"\nExtraction complete: {prediction_path}")
        return 0
    if not prediction_path.exists():
        print(f"Prediction file not found: {prediction_path}", file=sys.stderr)
        return 1

    judge_key = (
        args.judge_api_key
        or first_env("BENCHMARK_API_KEY", "JUDGE_API_KEY", "ANTHROPIC_AUTH_TOKEN", "LLM_API_KEY")
    )
    if not judge_key:
        print(
            "Benchmark judge API key is required. Pass --judge-api-key or set BENCHMARK_API_KEY/JUDGE_API_KEY/LLM_API_KEY.",
            file=sys.stderr,
        )
        return 2

    env["BENCHMARK_API_KEY"] = judge_key
    if args.judge_base_url:
        env["BENCHMARK_BASE_URL"] = args.judge_base_url
    if args.judge_model:
        env["BENCHMARK_MODEL"] = args.judge_model

    eval_output.mkdir(parents=True, exist_ok=True)
    eval_cmd = [
        sys.executable,
        str(REPO_ROOT / "benchmark" / "run_eval.py"),
        "--gt",
        str((REPO_ROOT / args.gt).resolve() if not Path(args.gt).is_absolute() else Path(args.gt)),
        "--pred",
        str(prediction_path),
        "--output",
        str(eval_output),
        "--subset",
        args.subset,
        "--paper-concurrency",
        str(args.paper_concurrency),
    ]
    if args.judge_model:
        eval_cmd.extend(["--model", args.judge_model])
    if args.judge_base_url:
        eval_cmd.extend(["--base-url", args.judge_base_url])
    if args.papers:
        eval_cmd.append("--papers")
        eval_cmd.extend(args.papers)

    run_command(eval_cmd, cwd=REPO_ROOT / "benchmark", env=env)

    result_path = eval_output / "eval_result_latest.json"
    dashboard_path = eval_output / "eval_dashboard.html"
    run_command(
        [
            sys.executable,
            str(REPO_ROOT / "benchmark" / "scripts" / "visualize_eval.py"),
            str(result_path),
            "--output",
            str(dashboard_path),
        ],
        cwd=REPO_ROOT,
        env=env,
    )

    print(f"\nRun artifacts: {run_root}")
    print(f"Predictions: {prediction_path}")
    print(f"Benchmark result: {result_path}")
    print(f"Dashboard: {dashboard_path}")

    if args.serve:
        url = f"http://{args.host}:{args.port}/eval_dashboard.html"
        print(f"\nServing dashboard: {url}")
        subprocess.run(
            [
                sys.executable,
                "-m",
                "http.server",
                str(args.port),
                "--bind",
                args.host,
                "--directory",
                str(eval_output),
            ],
            check=False,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
