#!/usr/bin/env python3
"""
Multi-agent antibody sequence extraction framework.

Usage:
  python main.py <input_markdown> [-o output_dir] [--verbose]
  python main.py --batch <ocr_dir> -o output/

Example:
  python main.py /path/to/paper.md -o runs/fimmu-15
"""

import argparse
import asyncio
import logging
import os
import sys
import json
import glob
import time
import re
from pathlib import Path
import httpx

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from orchestrator import Orchestrator
from tools.llm_client import RateLimiter
from tools.trace_recorder import TraceRecorder
from tools.batch_progress import BatchProgressDisplay
from tools.file_utils import FileUtils


GERMLINE_NAME_RE = re.compile(r"^IG[HKL][VJD][A-Z0-9*./-]*$", re.IGNORECASE)
CHAIN_CHILD_NAME_RE = re.compile(r".*-[HL]\d+$", re.IGNORECASE)
CHAIN_COMPONENT_RE = re.compile(r"/(?:KJ|HJ|HD)\d+$", re.IGNORECASE)
RETRYABLE_HTTP_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}
RETRYABLE_ERROR_PATTERNS = (
    "504 gateway time-out",
    "502 bad gateway",
    "503 service unavailable",
    "timed out",
    "timeout",
    "connection reset",
    "temporarily unavailable",
)


def _is_benchmark_auxiliary_antibody(name: str) -> bool:
    text = (name or "").strip()
    if not text:
        return False
    if GERMLINE_NAME_RE.match(text):
        return True
    if CHAIN_CHILD_NAME_RE.match(text):
        return True
    if CHAIN_COMPONENT_RE.search(text):
        return True
    return False


def _benchmark_normalize_antibody_type(antibody: dict) -> dict:
    normalized = dict(antibody or {})
    ab_type = str(normalized.get("Antibody_Type") or "").strip()
    ab_type_key = re.sub(r"[^a-z0-9]+", "", ab_type.lower())
    if ab_type_key not in {"mab", "monoclonalantibody"}:
        return normalized

    isotype = str(normalized.get("Antibody_Isotype") or "").strip()
    upper = isotype.upper()
    canonical = {
        "IGG": "IgG",
        "IGA": "IgA",
        "IGM": "IgM",
        "IGD": "IgD",
        "IGE": "IgE",
    }
    for token, label in canonical.items():
        if token in upper:
            normalized["Antibody_Type"] = label
            return normalized
    return normalized


def _is_retryable_paper_error(exc: Exception) -> bool:
    if isinstance(
        exc,
        (
            httpx.ConnectError,
            httpx.ReadTimeout,
            httpx.WriteTimeout,
            httpx.RemoteProtocolError,
            httpx.PoolTimeout,
        ),
    ):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in RETRYABLE_HTTP_STATUS
    message = str(exc).lower()
    return any(pattern in message for pattern in RETRYABLE_ERROR_PATTERNS)


def _paper_retry_delay_seconds(attempt_index: int) -> int:
    return min(60, 5 * (2 ** attempt_index))


def build_benchmark_predictions(all_predictions: dict) -> tuple[dict, dict]:
    benchmark_predictions = {}
    stats = {"kept": 0, "dropped": 0}
    for paper_id, payload in all_predictions.items():
        antibodies = list((payload or {}).get("antibodies") or [])
        filtered = []
        for antibody in antibodies:
            if _is_benchmark_auxiliary_antibody(antibody.get("Antibody_Name", "")):
                stats["dropped"] += 1
                continue
            filtered.append(_benchmark_normalize_antibody_type(antibody))
            stats["kept"] += 1
        benchmark_predictions[paper_id] = {**payload, "antibodies": filtered}
    return benchmark_predictions, stats


def setup_logging(verbose: bool):
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
    logging.basicConfig(level=level, format=fmt, datefmt="%H:%M:%S")
    # Quiet noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


async def run_single(config: Config, input_path: str, output_dir: str):
    limiter = RateLimiter(config.llm_rpm, config.llm_tpm, config.llm_concurrency)
    max_attempts = max(1, int(getattr(config, "max_paper_retries", 0)) + 1)
    logger = logging.getLogger(__name__)
    for attempt in range(max_attempts):
        orchestrator = Orchestrator(config, rate_limiter=limiter)
        try:
            return await asyncio.wait_for(
                orchestrator.run(input_path, output_dir),
                timeout=config.timeout_per_paper,
            )
        except asyncio.TimeoutError:
            if attempt < max_attempts - 1:
                delay = _paper_retry_delay_seconds(attempt)
                logger.warning(
                    "Single paper run timed out on attempt %s/%s; retrying in %ss",
                    attempt + 1,
                    max_attempts,
                    delay,
                )
                await asyncio.sleep(delay)
                continue
            raise
        except Exception as exc:
            if _is_retryable_paper_error(exc) and attempt < max_attempts - 1:
                delay = _paper_retry_delay_seconds(attempt)
                logger.warning(
                    "Single paper run failed with retryable error on attempt %s/%s; retrying in %ss: %s",
                    attempt + 1,
                    max_attempts,
                    delay,
                    exc,
                )
                await asyncio.sleep(delay)
                continue
            raise


def _batch_group_key(md_path: str, batch_dir: str) -> str:
    path = Path(md_path).resolve()
    batch_root = Path(batch_dir).resolve()
    if path.parent.name == "vlm":
        return str(path.parent.parent)
    if path.parent == batch_root:
        return str(path)
    return str(path.parent)


def _batch_md_priority(md_path: str) -> tuple[int, int, str]:
    path = Path(md_path)
    name = path.name
    stem = path.stem
    parent = path.parent.name
    if name == "images_ocr_merged.md":
        return (0, len(name), str(path))
    if stem.endswith("_enhanced"):
        return (1, len(name), str(path))
    if parent == "vlm":
        return (2, len(name), str(path))
    if stem == parent:
        return (3, len(name), str(path))
    return (9, len(name), str(path))


def discover_batch_markdowns(batch_dir: str) -> list[str]:
    patterns = [
        os.path.join(batch_dir, "*/vlm/*.md"),
        os.path.join(batch_dir, "*/*.md"),
        os.path.join(batch_dir, "*.md"),
    ]
    candidates = []
    for pat in patterns:
        candidates.extend(glob.glob(pat))

    grouped = {}
    for md_path in sorted(set(candidates)):
        base = os.path.basename(md_path)
        if base.startswith("."):
            continue
        group_key = _batch_group_key(md_path, batch_dir)
        current = grouped.get(group_key)
        if current is None or _batch_md_priority(md_path) < _batch_md_priority(current):
            grouped[group_key] = md_path

    return sorted(grouped.values())


async def run_batch(config: Config, batch_dir: str, output_base: str):
    """Batch process all papers in a directory with live progress display"""
    md_files = discover_batch_markdowns(batch_dir)

    if not md_files:
        print(f"No markdown files found in {batch_dir}")
        return

    paper_ids = [FileUtils.paper_id_from_path(f) for f in md_files]

    all_predictions = {}
    results_summary = []
    rate_limiter = RateLimiter(config.llm_rpm, config.llm_tpm, config.llm_concurrency)
    tracer = config.trace_recorder
    if config.trace_enabled and tracer is None:
        tracer = TraceRecorder()
        config.trace_recorder = tracer
    batch_span = None
    if tracer:
        batch_span = tracer.start_span("batch", "batch_run", batch_dir=batch_dir, output_dir=output_base)

    sem = asyncio.Semaphore(config.papers_per_worker)
    progress = BatchProgressDisplay(paper_ids)

    async def process_one(md_path, paper_id):
        async with sem:
            out_dir = os.path.join(output_base, paper_id)
            t0 = time.time()
            max_attempts = max(1, int(getattr(config, "max_paper_retries", 0)) + 1)
            if tracer:
                tracer.record_event("paper_queued", "paper_dispatch",
                                    paper_id=paper_id, batch_dir=batch_dir)

            for attempt in range(max_attempts):
                progress.update_paper(
                    paper_id,
                    status="running",
                    phase="scan" if attempt == 0 else "retry",
                    retries=attempt,
                )
                try:
                    orchestrator = Orchestrator(config, rate_limiter=rate_limiter)
                    result = await asyncio.wait_for(
                        orchestrator.run(md_path, out_dir),
                        timeout=config.timeout_per_paper,
                    )

                    elapsed = round(time.time() - t0, 1)
                    ab_count = result.get("antibody_count", 0)
                    llm_stats = orchestrator.llm.stats

                    if "prediction" in result:
                        all_predictions.update(result["prediction"])
                    results_summary.append({
                        "paper_id": paper_id, "status": "completed",
                        "antibodies": ab_count,
                        "elapsed": elapsed,
                        "llm_calls": llm_stats["total_calls"],
                        "tokens": llm_stats["total_tokens"],
                        "retries": attempt,
                    })
                    progress.update_paper(
                        paper_id,
                        status="completed", phase="completed",
                        antibodies=ab_count,
                        elapsed=elapsed,
                        llm_calls=llm_stats["total_calls"],
                        tokens=llm_stats["total_tokens"],
                        retries=attempt,
                    )
                    if tracer:
                        tracer.record_event(
                            "paper_completed",
                            "paper_dispatch",
                            paper_id=paper_id,
                            retry_attempt=attempt,
                        )
                    return result

                except asyncio.TimeoutError as e:
                    retryable = attempt < max_attempts - 1
                    elapsed = round(time.time() - t0, 1)
                    if retryable:
                        delay = _paper_retry_delay_seconds(attempt)
                        logging.getLogger(__name__).warning(
                            "Paper %s timed out on attempt %s/%s; retrying in %ss",
                            paper_id,
                            attempt + 1,
                            max_attempts,
                            delay,
                        )
                        progress.update_paper(
                            paper_id,
                            status="running",
                            phase="retry",
                            elapsed=elapsed,
                            retries=attempt + 1,
                        )
                        if tracer:
                            tracer.record_event(
                                "paper_retry",
                                "paper_dispatch",
                                paper_id=paper_id,
                                retry_attempt=attempt + 1,
                                reason="timeout",
                                retry_delay_seconds=delay,
                            )
                        await asyncio.sleep(delay)
                        continue

                    results_summary.append({
                        "paper_id": paper_id,
                        "status": "timeout",
                        "elapsed": elapsed,
                        "retries": attempt,
                    })
                    progress.update_paper(
                        paper_id,
                        status="timeout",
                        phase="timeout",
                        elapsed=elapsed,
                        retries=attempt,
                    )
                    if tracer:
                        tracer.record_event(
                            "paper_timeout",
                            "paper_dispatch",
                            paper_id=paper_id,
                            retry_attempt=attempt,
                        )

                except Exception as e:
                    retryable = _is_retryable_paper_error(e) and attempt < max_attempts - 1
                    elapsed = round(time.time() - t0, 1)
                    if retryable:
                        delay = _paper_retry_delay_seconds(attempt)
                        logging.getLogger(__name__).warning(
                            "Paper %s failed with retryable error on attempt %s/%s; retrying in %ss: %s",
                            paper_id,
                            attempt + 1,
                            max_attempts,
                            delay,
                            e,
                        )
                        progress.update_paper(
                            paper_id,
                            status="running",
                            phase="retry",
                            elapsed=elapsed,
                            retries=attempt + 1,
                        )
                        if tracer:
                            tracer.record_event(
                                "paper_retry",
                                "paper_dispatch",
                                paper_id=paper_id,
                                retry_attempt=attempt + 1,
                                reason=str(e),
                                retry_delay_seconds=delay,
                            )
                        await asyncio.sleep(delay)
                        continue

                    results_summary.append({
                        "paper_id": paper_id, "status": "error",
                        "error": str(e), "elapsed": elapsed,
                        "retries": attempt,
                    })
                    progress.update_paper(
                        paper_id, status="error", phase="error", elapsed=elapsed, retries=attempt,
                    )
                    if tracer:
                        tracer.record_event("paper_error", "paper_dispatch",
                                            paper_id=paper_id, error=str(e), retry_attempt=attempt)
                    if not config.skip_on_error:
                        raise
                    return None

    with progress:
        tasks = [process_one(f, pid) for f, pid in zip(md_files, paper_ids)]
        await asyncio.gather(*tasks)

    # Save merged predictions
    os.makedirs(output_base, exist_ok=True)
    pred_path = os.path.join(output_base, "predictions.json")
    with open(pred_path, "w", encoding="utf-8") as f:
        json.dump(all_predictions, f, indent=2, ensure_ascii=False)

    benchmark_predictions, benchmark_stats = build_benchmark_predictions(all_predictions)
    benchmark_pred_path = os.path.join(output_base, "benchmark_predictions.json")
    with open(benchmark_pred_path, "w", encoding="utf-8") as f:
        json.dump(benchmark_predictions, f, indent=2, ensure_ascii=False)

    # Summary
    completed = sum(1 for r in results_summary if r["status"] == "completed")
    batch_summary = {
        "total_papers": len(md_files),
        "completed_papers": completed,
        "failed_papers": len([r for r in results_summary if r["status"] == "error"]),
        "timed_out_papers": len([r for r in results_summary if r["status"] == "timeout"]),
        "total_antibodies": sum(r.get("antibodies", 0) for r in results_summary),
        "total_llm_calls": sum(r.get("llm_calls", 0) for r in results_summary),
        "total_tokens": sum(r.get("tokens", 0) for r in results_summary),
        "results": results_summary,
        "prediction_path": pred_path,
        "benchmark_prediction_path": benchmark_pred_path,
        "benchmark_prediction_kept": benchmark_stats["kept"],
        "benchmark_prediction_dropped": benchmark_stats["dropped"],
    }
    summary_path = os.path.join(output_base, "batch_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(batch_summary, f, indent=2, ensure_ascii=False)

    if tracer:
        tracer.end_span(batch_span, status="success",
                        total_papers=len(md_files), completed_papers=completed)
        trace_path = os.path.join(output_base, "trace_events.json")
        tracer.write_json(trace_path)

    # Final summary
    print(f"\n{'='*60}")
    print(f"  Batch complete: {completed}/{len(md_files)} papers")
    print(f"  Total antibodies: {batch_summary['total_antibodies']}")
    print(f"  Total LLM calls: {batch_summary['total_llm_calls']}")
    print(f"  Total tokens: {batch_summary['total_tokens']:,}")
    print(f"  Predictions saved: {pred_path}")
    print(f"  Benchmark predictions saved: {benchmark_pred_path} "
          f"(kept={benchmark_stats['kept']}, dropped={benchmark_stats['dropped']})")
    print(f"  Batch summary: {summary_path}")
    if tracer:
        print(f"  Trace events: {os.path.join(output_base, 'trace_events.json')}")
        print(f"\n  Run visualization:")
        print(f"    python tools/visualize_trace.py {os.path.join(output_base, 'trace_events.json')}")
    print(f"{'='*60}")
    return batch_summary


def main():
    parser = argparse.ArgumentParser(description="Multi-Agent Antibody Sequence Extraction")
    parser.add_argument("input", nargs="?", help="Input markdown file path")
    parser.add_argument("-o", "--output", default="./output", help="Output directory")
    parser.add_argument("--batch", help="Batch mode: directory containing papers")
    parser.add_argument("--model", help="LLM model override")
    parser.add_argument("--api-base", help="LLM API base URL override")
    parser.add_argument("--api-key", help="LLM API key override")
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--strict", action="store_true", help="Strict validation")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--no-supplement", action="store_true", help="Disable Track B")
    parser.add_argument("--mock-llm", action="store_true", help="Use deterministic mock LLM responses")
    parser.add_argument("--trace", action="store_true", help="Enable structured trace capture")
    parser.add_argument("--papers-per-worker", type=int, help="Batch paper concurrency override")
    parser.add_argument("--llm-concurrency", type=int, help="Shared LLM concurrency override")
    args = parser.parse_args()

    config = Config(
        max_retries=args.max_retries,
        strict_validation=args.strict,
        verbose=args.verbose,
        enable_supplement=not args.no_supplement,
        mock_llm=args.mock_llm,
        trace_enabled=args.trace,
    )
    if args.model:
        config.llm_model = args.model
        config.llm_review_model = args.model
    if args.api_base:
        config.llm_api_base = args.api_base
    if args.api_key:
        config.llm_api_key = args.api_key
    if args.papers_per_worker:
        config.papers_per_worker = args.papers_per_worker
    if args.llm_concurrency:
        config.llm_concurrency = args.llm_concurrency

    if not config.mock_llm and not config.llm_api_key:
        parser.error(
            "LLM API key is required for live runs. Set LLM_API_KEY or pass --api-key. "
            "Use --mock-llm for local smoke tests without external API calls."
        )

    setup_logging(args.verbose)

    if args.batch:
        asyncio.run(run_batch(config, args.batch, args.output))
    elif args.input:
        asyncio.run(run_single(config, args.input, args.output))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
