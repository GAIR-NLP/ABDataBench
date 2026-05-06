#!/usr/bin/env python3
"""
Benchmark evaluation entry point for antibody literature extraction v3.

Features:
  - 22 scoring fields aligned with the benchmark JSON schema
  - weighted field scoring: core 2.0, standard 1.0, auxiliary 0.5
  - order-independent antibody matching
  - penalty formula: max(0, 1.0 - 0.01*floor(NFP/5) - 0.05*NFN)
  - numeric pre-checks for KD, kon, koff, EC50, and Tm

Examples:
    python run_eval.py --gt ground_truth/ground_truth.json --pred ../runs/dev/agent/benchmark_predictions.json
    python run_eval.py --gt ground_truth/ground_truth.json --pred ../runs/dev/agent/benchmark_predictions.json --papers "Fantin et al. Cell 2025"
    python run_eval.py --gt ground_truth/ground_truth.json --pred ../runs/dev/agent/benchmark_predictions.json --model gzy/claude-4.6-sonnet

An API key is required through --api-key or BENCHMARK_API_KEY/JUDGE_API_KEY/LLM_API_KEY.
"""

import json
import os
import sys
import argparse
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "scripts"))
from dataset_partition import annotate_categories, filter_ground_truth, normalize_subset
from evaluator import evaluate_benchmark, generate_markdown_report, result_to_dict
from llm_judge import LLMJudge


BENCHMARK_ROOT = Path(__file__).resolve().parent


def resolve_input_path(path_value: str) -> Path:
    path = Path(path_value).expanduser()
    if path.is_absolute() or path.exists():
        return path
    return BENCHMARK_ROOT / path


def main():
    parser = argparse.ArgumentParser(
        description="Antibody literature extraction benchmark v3"
    )
    parser.add_argument(
        "--gt",
        default="ground_truth/ground_truth.json",
        help="Ground-truth JSON path",
    )
    parser.add_argument("--pred", required=True, help="Prediction JSON path")
    parser.add_argument("--output", default="results", help="Output directory")
    parser.add_argument("--papers", nargs="*", help="Only evaluate the specified paper IDs")
    parser.add_argument(
        "--subset",
        "--category",
        dest="subset",
        default="all",
        choices=["all", "paper", "patent"],
        help="Filter the benchmark subset: all | paper | patent",
    )
    parser.add_argument("--api-key", default=None, help="API Key")
    parser.add_argument("--base-url", default=None, help="API Base URL")
    parser.add_argument(
        "--model",
        default=os.environ.get("BENCHMARK_MODEL") or os.environ.get("JUDGE_MODEL") or "gzy/claude-4.6-sonnet",
        help="Judge model",
    )
    parser.add_argument("--paper-concurrency", type=int, default=5, help="Paper-level concurrency (default: 5)")
    args = parser.parse_args()

    # API Key
    api_key = (
        args.api_key
        or os.environ.get("BENCHMARK_API_KEY")
        or os.environ.get("JUDGE_API_KEY")
        or os.environ.get("ANTHROPIC_AUTH_TOKEN")
        or os.environ.get("LLM_API_KEY")
        or ""
    )
    base_url = (
        args.base_url
        or os.environ.get("BENCHMARK_BASE_URL")
        or os.environ.get("JUDGE_BASE_URL")
        or os.environ.get("ANTHROPIC_BASE_URL")
        or os.environ.get("LLM_API_BASE")
        or "https://api.opensii.ai"
    )
    if not api_key:
        print("Error: provide an API key with --api-key or BENCHMARK_API_KEY/JUDGE_API_KEY/LLM_API_KEY")
        sys.exit(1)

    # Load inputs.
    gt_path = resolve_input_path(args.gt)
    pred_path = resolve_input_path(args.pred)
    with open(gt_path, "r", encoding="utf-8") as f:
        ground_truth = annotate_categories(json.load(f))
    with open(pred_path, "r", encoding="utf-8") as f:
        predictions = json.load(f)

    subset = normalize_subset(args.subset)
    ground_truth = filter_ground_truth(ground_truth, subset)
    if args.papers:
        ground_truth = {k: v for k, v in ground_truth.items() if k in args.papers}
    predictions = {k: v for k, v in predictions.items() if k in ground_truth}

    if not ground_truth:
        print(f"Error: no evaluable papers for subset={subset}. Check --gt, --subset, and --papers.")
        sys.exit(1)

    # Initialize the judge. The RPM setting is raised for concurrent paper scoring.
    judge = LLMJudge(api_key=api_key, base_url=base_url, model=args.model,
                     requests_per_minute=500)
    os.makedirs(args.output, exist_ok=True)
    cache_path = os.path.join(args.output, "llm_judge_cache.json")
    judge.load_cache(cache_path)

    print(f"\n{'='*60}")
    print(f"  Antibody Literature Extraction Benchmark v3")
    print(f"{'='*60}")
    print(f"  Ground truth papers: {len(ground_truth)}")
    print(f"  Prediction papers: {len(predictions)}")
    print(f"  Subset: {subset}")
    print(f"  Judge model: {args.model}")
    print(f"  Scoring fields: 22 (core 4 / standard 9 / auxiliary 9)")
    print(f"  Field weights: core 2.0 / standard 1.0 / auxiliary 0.5")
    print(f"  Penalty formula: max(0, 1.0 - 0.01*floor(NFP/5) - 0.05*NFN)")
    print(f"  Paper concurrency: {args.paper_concurrency}")
    print()

    # Run evaluation.
    result = evaluate_benchmark(ground_truth, predictions, judge,
                                paper_concurrency=args.paper_concurrency)
    result.metadata = {
        "gt_path": args.gt,
        "pred_path": args.pred,
        "subset": subset,
        "paper_ids": list(ground_truth.keys()),
    }

    # Save judge cache.
    judge.save_cache(cache_path)
    print(
        f"\n  LLM stats: API calls={judge.call_count}, "
        f"cache hits={judge.cache_hit}, cache entries={len(judge.cache)}"
    )

    # Print summary.
    print(f"\n{'='*60}")
    print(f"  Overall score: {result.accuracy:.1f} / 100")
    print(f"{'='*60}")
    print(f"\n  Paper-level details:")
    print(f"  {'Paper ID':<30} {'GT':>3} {'Match':>5} {'Miss':>4} {'Extra':>5} "
          f"{'Raw':>6} {'Penalty':>7} {'Final':>6}")
    print(f"  {'-'*80}")
    for ps in result.paper_scores:
        print(f"  {ps.paper_id:<30} {ps.gt_antibody_count:>3} {ps.matched_count:>4} "
              f"{ps.false_negative_count:>4} {ps.false_positive_count:>4} "
              f"{ps.raw_accuracy:>6.1f} "
              f"{ps.penalty_coeff:>6.2f} {ps.accuracy:>6.1f}")
    print()

    # Write result files.
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    rj = os.path.join(args.output, f"eval_result_{ts}.json")
    rm = os.path.join(args.output, f"eval_report_{ts}.md")

    with open(rj, "w", encoding="utf-8") as f:
        json.dump(result_to_dict(result), f, ensure_ascii=False, indent=2)
    with open(rm, "w", encoding="utf-8") as f:
        f.write(generate_markdown_report(result))

    # Latest files.
    for name, content_func in [
        ("eval_result_latest.json",
         lambda: json.dumps(result_to_dict(result), ensure_ascii=False, indent=2)),
        ("eval_report_latest.md",
         lambda: generate_markdown_report(result)),
    ]:
        with open(os.path.join(args.output, name), "w", encoding="utf-8") as f:
            f.write(content_func())

    print(f"  Result JSON: {rj}")
    print(f"  Report MD:   {rm}")
    print(f"  Latest JSON: {os.path.join(args.output, 'eval_result_latest.json')}")
    print()


if __name__ == "__main__":
    main()
