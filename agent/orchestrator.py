"""Multi-agent workflow orchestrator."""

import asyncio
import copy
import logging
from pathlib import Path
import os
import re
import time
from difflib import SequenceMatcher

from agents.base_agent import AgentStatus
from agents.ocr_repair_agent import OCRRepairAgent
from agents.paper_focus_agent import PaperFocusAgent
from agents.scanner_agent import ScannerAgent
from agents.reducer_agent import ReducerAgent
from agents.skeleton_agent import SkeletonAgent
from agents.validator_agent import ValidatorAgent
from agents.reviewer_agent import ReviewerAgent
from agents.extract.api_fetch_agent import APIFetchAgent
from agents.extract.table_extract_agent import TableExtractAgent
from agents.extract.supplement_agent import SupplementAgent
from agents.extract.image_extract_agent import ImageExtractAgent
from agents.extract.sequence_image_agent import SequenceImageExtractAgent
from tools.api_client import APIClient
from tools.amino_acid_utils import STANDARD_AA, normalize_aa_sequence
from tools.llm_client import LLMClient
from tools.vlm_client import VLMClient
from tools.file_utils import FileUtils
from tools.text_sequence_extractor import extract_text_sequences
from tools.vlm_sequence_verifier import (
    verify_sequence_image_records_with_vlm,
    verify_sequences_with_vlm,
)

logger = logging.getLogger(__name__)


SEQUENCE_FIELD_NAMES = {"CDRH3_Sequence", "vh_sequence_aa", "vl_sequence_aa"}

VLM_TARGET_FIELDS = {
    "CDRH3_Sequence",
    "vh_sequence_aa",
    "vl_sequence_aa",
    "Binding_Kinetics_KD",
    "Binding_Kinetics_kon",
    "Binding_Kinetics_koff",
    "Binding_EC50",
    "Quantitative_Metric",
    "Thermal_Stability_Tm",
    "In_Vivo_Efficacy",
}


class Orchestrator:
    """5-Phase Pipeline Orchestrator"""

    MIN_VARIABLE_REGION_AA_LEN = 80
    MINOR_SEQUENCE_MISMATCH_MAX_EDITS = 3
    VARIANT_NAME_NOISE_PATTERNS = (
        r"\bwt\b",
        r"\bwild[- ]type\b",
        r"\bvariant\b",
        r"\bmutant\b",
        r"\bmutation\b",
        r"\bchimera\b",
        r"\bchimeric\b",
        r"\bdelet(?:e|ed|ion)\b",
        r"\bdel\b",
        r"\bfr\d+(?:[- ]\d+)?\b",
        r"\bcdr\d+(?:[- ]?[a-z0-9]+)?\b",
        r"\b[a-z]\d{1,3}[a-z]\b",
        r"\bls\b",
    )
    CHAIN_IDENTITY_KEYWORDS = ("identical", "same", "unchanged", "retain", "retained", "shared")
    CHAIN_REFERENCE_KEYWORDS = ("wt", "wild type", "wild-type", "parent", "template", "original")
    REFERENCE_ONLY_CONTEXT_PATTERNS = (
        r"\bcontrol mabs?\b",
        r"\bcontrol abs?\b",
        r"\bcontrol antibodies\b",
        r"\bused as control\b",
        r"\bpreviously described\b",
        r"\bpreviously published\b",
        r"\bpublished previously\b",
        r"\bother representative .* antibodies\b",
        r"\bpublic clonotypes?\b",
        r"\bpublic mabs?\b",
        r"\binfected patients and vaccinees\b",
        r"\bclonotyping\b",
        r"\bjunctional sequence analysis\b",
        r"\bparallel lineage\b",
        r"\binferred germline\b",
        r"\bigl mabs?\b",
        r"\bgroup [12] rbd bnabs?\b",
    )

    def __init__(self, config, rate_limiter=None):
        self.config = config
        self.llm = LLMClient(config, rate_limiter=rate_limiter)

        self.ocr_repairer = OCRRepairAgent(config, llm=self.llm)
        self.scanner = ScannerAgent(config)
        self.paper_focus_agent = PaperFocusAgent(config, llm=self.llm)
        self.reducer = ReducerAgent(config)
        self.skeleton_builder = SkeletonAgent(config, llm=self.llm)
        self.api_fetcher = APIFetchAgent(config)
        self.table_extractor = TableExtractAgent(config)
        self.supplement_agent = SupplementAgent(config)
        self.validator = ValidatorAgent(config)
        self.reviewer = ReviewerAgent(config, llm=self.llm)

        if config.enable_image_extract:
            self.vlm = VLMClient(config)
            self.image_extractor = ImageExtractAgent(config, vlm=self.vlm)
            self.sequence_image_extractor = SequenceImageExtractAgent(config)
        else:
            self.vlm = None
            self.image_extractor = None
            self.sequence_image_extractor = None

    async def run(self, input_md_path: str, output_dir: str) -> dict:
        FileUtils.ensure_dir(output_dir)
        paper_id = FileUtils.paper_id_from_path(input_md_path)
        md_text = FileUtils.read_text(input_md_path)
        tracer = getattr(self.config, "trace_recorder", None)

        context = {
            "input_file": input_md_path,
            "output_dir": output_dir,
            "paper_id": paper_id,
            "markdown_text": md_text,
            "markdown_text_full": md_text,
            "markdown_text_raw": md_text,
            "trace_recorder": tracer,
            "image_dir": str(Path(input_md_path).parent / "images"),
        }

        run_log = {"paper_id": paper_id, "input_file": input_md_path, "phases": []}
        t_start = time.time()
        paper_span = None
        if tracer:
            paper_span = tracer.start_span("paper", paper_id, paper_id=paper_id, input_file=input_md_path)

        # ── Phase 0.5: OCR REPAIR ──
        print(f"\n[Phase 0.5: OCR REPAIR] Repairing OCR formatting conservatively...")
        try:
            repair_span = self._start_phase_span(tracer, paper_id, "ocr_repair")
            context["current_phase"] = "ocr_repair"
            repair_result = await self.ocr_repairer.execute(context)
            repair_meta = repair_result.data.get("meta", {})
            repaired_text = repair_result.data.get("repaired_text", md_text)
            context["markdown_text"] = repaired_text
            context["markdown_text_full"] = repaired_text
            run_log["phases"].append(
                {
                    "phase": "ocr_repair",
                    "metrics": repair_result.metrics,
                    "summary": repair_meta,
                }
            )
            print(
                "  OCR text: "
                f"{repair_meta.get('original_chars', len(md_text))} -> "
                f"{repair_meta.get('repaired_chars', len(repaired_text))} chars"
            )
            self._end_phase_span(
                tracer,
                repair_span,
                used_repaired_text=repair_meta.get("used_repaired_text", False),
                changed_chunks=repair_meta.get("changed_chunks", 0),
            )
            if self.config.save_intermediate:
                FileUtils.write_json(
                    os.path.join(output_dir, "ocr_repair_report.json"),
                    repair_meta,
                )
                FileUtils.write_text(
                    os.path.join(output_dir, "ocr_repaired.md"),
                    repaired_text,
                )

        # ── Phase 1: SCAN ──
            print(f"\n[Phase 1: SCAN] Running regex scan...")
            scan_span = self._start_phase_span(tracer, paper_id, "scan")
            context["current_phase"] = "scan"
            scan_result = await self.scanner.execute(context)
            context["regex_hints"] = scan_result.data
            run_log["phases"].append({"phase": "scan", "metrics": scan_result.metrics,
                                       "routing": scan_result.data["routing_suggestions"]})
            self._print_scan_summary(scan_result.data)
            self._end_phase_span(tracer, scan_span, routing_count=len(scan_result.data["routing_suggestions"]))

            if self.config.save_intermediate:
                FileUtils.write_json(os.path.join(output_dir, "regex_hints.json"), scan_result.data)

            # ── Phase 1.1: PAPER FOCUS ──
            print(f"\n[Phase 1.1: PAPER FOCUS] Building heuristic paper-level extraction brief...")
            focus_span = self._start_phase_span(tracer, paper_id, "paper_focus")
            context["current_phase"] = "paper_focus"
            focus_result = await self.paper_focus_agent.execute(context)
            context["paper_focus"] = focus_result.data
            run_log["phases"].append(
                {
                    "phase": "paper_focus",
                    "metrics": focus_result.metrics,
                    "summary": focus_result.data.get("paper_focus_text", ""),
                }
            )
            self._print_paper_focus_summary(focus_result.data)
            self._end_phase_span(
                tracer,
                focus_span,
                hard_paper=focus_result.data.get("hard_paper", False),
                difficulty_count=len(focus_result.data.get("difficulty_flags") or []),
            )
            if self.config.save_intermediate:
                FileUtils.write_json(os.path.join(output_dir, "paper_focus.json"), focus_result.data)

            # ── Phase 1.2: REDUCE ──
            print(f"\n[Phase 1.2: REDUCE] Filtering long-context text for skeleton...")
            reduce_span = self._start_phase_span(tracer, paper_id, "reduce")
            context["current_phase"] = "reduce"
            reduce_result = await self.reducer.execute(context)
            reduced_meta = reduce_result.data.get("meta", {})
            context["markdown_text_reduced"] = reduce_result.data.get("reduced_text", md_text)
            context["markdown_text_reduced_meta"] = reduced_meta
            run_log["phases"].append(
                {
                    "phase": "reduce",
                    "metrics": reduce_result.metrics,
                    "summary": reduced_meta,
                }
            )
            print(
                "  Reduced text: "
                f"{reduced_meta.get('original_chars', len(md_text))} -> "
                f"{reduced_meta.get('reduced_chars', len(context['markdown_text_reduced']))} chars"
            )
            self._end_phase_span(
                tracer,
                reduce_span,
                used_reduced_text=reduced_meta.get("used_reduced_text", False),
                reduced_chars=reduced_meta.get("reduced_chars", len(context["markdown_text_reduced"])),
            )
            if self.config.save_intermediate:
                FileUtils.write_json(
                    os.path.join(output_dir, "reduced_text_report.json"),
                    reduced_meta,
                )
                FileUtils.write_text(
                    os.path.join(output_dir, "reduced_text.md"),
                    context["markdown_text_reduced"],
                )

            # ── Optional pre-skeleton sequence-image assist ──
            if self.sequence_image_extractor and "images/" in md_text:
                print(f"\n[Phase 1.5: SEQUENCE IMAGE] Pre-extracting sequence-only image evidence...")
                seq_img_span = self._start_phase_span(tracer, paper_id, "sequence_image")
                context["current_phase"] = "sequence_image"
                sequence_result = await self.sequence_image_extractor.execute(context)
                context["sequence_image_result"] = sequence_result.data
                context["sequence_image_agent_result"] = sequence_result
                run_log["phases"].append(
                    {
                        "phase": "sequence_image",
                        "metrics": sequence_result.metrics,
                        "records": len(sequence_result.data.get("table_records", [])),
                    }
                )
                self._end_phase_span(
                    tracer,
                    seq_img_span,
                    records=len(sequence_result.data.get("table_records", [])),
                    images_considered=sequence_result.metrics.get("images_considered", 0),
                )
                if self.config.save_intermediate:
                    FileUtils.write_json(
                        os.path.join(output_dir, "sequence_image_extracted.json"),
                        sequence_result.data,
                    )

            # ── Phase 2: SKELETON ──
            print(f"\n[Phase 2: SKELETON] Building LLM skeleton...")
            skeleton_span = self._start_phase_span(tracer, paper_id, "skeleton")
            context["current_phase"] = "skeleton"
            skeleton_result = await self.skeleton_builder.execute(context)
            context["skeleton"] = skeleton_result.data
            hint_backfill_count = self._hydrate_sequence_fields_from_hints(
                context["skeleton"].get(paper_id, {}).get("antibodies", [])
            )
            ab_count = len(skeleton_result.data.get(paper_id, {}).get("antibodies", []))
            run_log["phases"].append({"phase": "skeleton", "metrics": skeleton_result.metrics,
                                       "antibody_count": ab_count,
                                       "hint_sequence_backfills": hint_backfill_count})
            print(f"  Antibodies found: {ab_count}")
            self._end_phase_span(tracer, skeleton_span, antibody_count=ab_count)

            if self.config.save_intermediate:
                FileUtils.write_json(os.path.join(output_dir, "skeleton_v1.json"), skeleton_result.data)

            # ── Phase 3: ENRICH (structured first, then targeted VLM) ──
            print(f"\n[Phase 3: ENRICH] Structured extraction + targeted VLM supplementation...")
            enrich_span = self._start_phase_span(tracer, paper_id, "enrich")
            enrich_summary = await self._run_enrichment_pipeline(context, paper_id)
            run_log["phases"].append({"phase": "enrich", **enrich_summary})
            self._end_phase_span(
                tracer,
                enrich_span,
                structured_tracks=enrich_summary["structured"]["track_count"],
                vlm_executed=enrich_summary["vlm"]["executed"],
                vlm_records=enrich_summary["vlm"]["records"],
            )

            # ── Phase 4: VALIDATE ──
            print(f"\n[Phase 4: VALIDATE] Bio-validation...")
            validate_span = self._start_phase_span(tracer, paper_id, "validate")
            context["current_phase"] = "validate"
            validate_result = await self.validator.execute(context)
            context["validation"] = validate_result.data
            run_log["phases"].append({"phase": "validate", "metrics": validate_result.metrics,
                                       "summary": validate_result.data["summary"]})
            self._print_validation_summary(validate_result.data)
            self._end_phase_span(tracer, validate_span, overall=validate_result.data["summary"]["overall"])

            if self.config.save_intermediate:
                FileUtils.write_json(os.path.join(output_dir, "validation_report.json"),
                                     validate_result.data)

            # ── Phase 5: REVIEW + RETRY ──
            retry_count = 0
            while retry_count < self.config.max_retries:
                print(f"\n[Phase 5: REVIEW] Reviewing (attempt {retry_count + 1})...")
                review_span = self._start_phase_span(tracer, paper_id, "review", attempt=retry_count + 1)
                context["current_phase"] = "review"
                review_result = await self.reviewer.execute(context)

                if review_result.status == AgentStatus.SUCCESS:
                    print(f"  Review PASSED")
                    self._end_phase_span(tracer, review_span, review_status="approved")
                    break

                print(f"  Review found {review_result.data['fail_count']} fails → retrying...")
                context["corrections"] = review_result.data.get("corrections")
                self._end_phase_span(tracer, review_span, status="retry", fail_count=review_result.data["fail_count"])

                if tracer:
                    tracer.record_event(
                        "retry_requested",
                        "review_retry",
                        paper_id=paper_id,
                        phase="review",
                        fail_count=review_result.data["fail_count"],
                    )

                # Re-run Phase 2 with corrections
                retry_skeleton_span = self._start_phase_span(tracer, paper_id, "skeleton_retry", attempt=retry_count + 1)
                context["current_phase"] = "skeleton"
                skeleton_result = await self.skeleton_builder.execute(context)
                context["skeleton"] = skeleton_result.data
                self._end_phase_span(tracer, retry_skeleton_span, antibody_count=len(skeleton_result.data.get(paper_id, {}).get("antibodies", [])))

                # Re-run enrichment so table/VLM supplements are not lost after retry.
                retry_enrich_span = self._start_phase_span(tracer, paper_id, "enrich_retry", attempt=retry_count + 1)
                enrich_summary = await self._run_enrichment_pipeline(context, paper_id, retry_attempt=retry_count + 1)
                self._end_phase_span(
                    tracer,
                    retry_enrich_span,
                    structured_tracks=enrich_summary["structured"]["track_count"],
                    vlm_executed=enrich_summary["vlm"]["executed"],
                    vlm_records=enrich_summary["vlm"]["records"],
                )

                # Re-run Phase 4
                retry_validate_span = self._start_phase_span(tracer, paper_id, "validate_retry", attempt=retry_count + 1)
                context["current_phase"] = "validate"
                validate_result = await self.validator.execute(context)
                context["validation"] = validate_result.data
                self._end_phase_span(tracer, retry_validate_span, overall=validate_result.data["summary"]["overall"])

                retry_count += 1
                run_log["phases"].append(
                    {
                        "phase": f"retry_{retry_count}",
                        "enrich": enrich_summary,
                        "validation_summary": validate_result.data["summary"],
                    }
                )

            # ── FINALIZE ──
            print(f"\n[FINALIZE] Saving outputs...")
            finalize_span = self._start_phase_span(tracer, paper_id, "finalize")
            context["current_phase"] = "finalize"
            skeleton_final = self._strip_internal_metadata(copy.deepcopy(context["skeleton"]))
            final_ab_count = len(skeleton_final.get(paper_id, {}).get("antibodies", []))

            # Save final skeleton (eval-compatible format)
            final_path = os.path.join(output_dir, "skeleton_final.json")
            FileUtils.write_json(final_path, skeleton_final)

            # Save prediction.json (flat eval format)
            pred_path = os.path.join(output_dir, "prediction.json")
            FileUtils.write_json(pred_path, skeleton_final)

            elapsed = round(time.time() - t_start, 1)
            run_log["total_elapsed_seconds"] = elapsed
            run_log["llm_stats"] = self.llm.stats
            FileUtils.write_json(os.path.join(output_dir, "run_log.json"), run_log)
            self._end_phase_span(tracer, finalize_span, output_dir=output_dir)

            print(f"\n{'='*60}")
            print(f"  Done! {final_ab_count} antibodies extracted in {elapsed}s")
            print(f"  LLM calls: {self.llm.stats['total_calls']}, tokens: {self.llm.stats['total_tokens']}")
            print(f"  Output: {output_dir}/")
            print(f"    skeleton_final.json  — main output")
            print(f"    prediction.json      — eval-compatible")
            print(f"    validation_report.json")
            print(f"    run_log.json")
            print(f"{'='*60}")

            if tracer:
                tracer.end_span(
                    paper_span,
                    status="success",
                    paper_id=paper_id,
                    elapsed_seconds=elapsed,
                    antibody_count=final_ab_count,
                )

            return {
                "paper_id": paper_id,
                "status": "completed",
                "antibody_count": final_ab_count,
                "prediction": skeleton_final,
                "validation_summary": validate_result.data["summary"],
                "elapsed_seconds": elapsed,
            }
        except Exception as exc:
            if tracer:
                tracer.end_span(paper_span, status="error", paper_id=paper_id, error=str(exc))
            raise

    @classmethod
    def _strip_internal_metadata(cls, payload):
        if isinstance(payload, list):
            return [cls._strip_internal_metadata(item) for item in payload]
        if isinstance(payload, dict):
            return {
                key: cls._strip_internal_metadata(value)
                for key, value in payload.items()
                if not str(key).startswith("_")
            }
        return payload

    async def _run_enrichment_pipeline(self, context: dict, paper_id: str, retry_attempt: int | None = None) -> dict:
        context["current_phase"] = "extract"

        structured_results = []
        presequence_result = context.get("sequence_image_agent_result")
        if presequence_result is not None:
            # Mark duplicate sequence-image clusters from the same source image.
            # Some papers legitimately report antibodies with identical chain
            # sequences (for example sibling clones or explicitly shared-chain
            # pairs), so do not drop the extracted values here. Keep the
            # sequences and attach internal metadata for downstream review.
            presequence_result.data["table_records"] = self._dedup_sequence_image_records(
                presequence_result.data.get("table_records", [])
            )
            paper_dir = str(Path(context.get("image_dir", "")).parent) if context.get("image_dir") else ""
            if self.vlm and paper_dir and presequence_result.data.get("table_records"):
                try:
                    presequence_result.data["table_records"] = await verify_sequence_image_records_with_vlm(
                        self.vlm,
                        paper_dir,
                        presequence_result.data.get("table_records", []),
                    )
                    pre_vlm_corrected = sum(
                        1
                        for record in presequence_result.data.get("table_records", [])
                        if record.get("_vlm_corrections")
                    )
                    if pre_vlm_corrected:
                        print(f"  Sequence-image verify: {pre_vlm_corrected} record(s) corrected")
                except Exception as e:
                    logger.warning(f"Sequence-image VLM verification failed: {e}")
            structured_results.append(presequence_result)
        structured_results.extend(await self._run_structured_extraction(context))
        context["skeleton"], structured_merge = self._merge_extractions(
            context["skeleton"], paper_id, structured_results
        )

        # Text sequence extraction: extract VH/VL from OCR alignment blocks
        # Run AFTER first merge so skeleton antibody names are established,
        # and results can overwrite incorrect sequence-image VLM results.
        text_seq_records = self._run_text_sequence_extraction(context, paper_id)

        # VLM verification: for records that have a source image, ask VLM to
        # compare OCR text against the original figure and correct errors.
        if text_seq_records:
            has_source_images = any(r.get("_ocr_source_image") for r in text_seq_records)
            if has_source_images:
                image_dir = context.get("image_dir", "")
                if image_dir:
                    try:
                        vlm = VLMClient(self.config)
                        text_seq_records = await verify_sequences_with_vlm(
                            vlm, image_dir, text_seq_records
                        )
                        vlm_corrected = sum(
                            1 for r in text_seq_records if r.get("_vlm_corrections")
                        )
                        if vlm_corrected:
                            print(f"  Track D VLM Verify: {vlm_corrected} sequence(s) corrected")
                    except Exception as e:
                        logger.warning(f"VLM sequence verification failed: {e}")

        text_seq_merge = {"filled_fields": 0, "records": 0}
        if text_seq_records:
            from agents.base_agent import AgentResult
            text_result = AgentResult(
                status=AgentStatus.SUCCESS,
                data={"table_records": text_seq_records, "source": "text_sequence_extractor"},
                metrics={},
            )
            context["skeleton"], text_seq_merge_stats = self._merge_extractions(
                context["skeleton"], paper_id, [text_result]
            )
            text_seq_merge = {
                "filled_fields": text_seq_merge_stats["filled_fields"],
                "records": len(text_seq_records),
            }

        md_text_for_inference = context.get("markdown_text_reduced") or context.get("markdown_text", "")
        chain_combo_summary = self._propagate_chain_variant_combinations(
            context["skeleton"],
            paper_id,
        )
        chain_inference_summary = self._propagate_identical_variant_chains(
            context["skeleton"],
            paper_id,
            md_text_for_inference,
        )
        chain_inference_summary["filled_fields"] += chain_combo_summary["filled_fields"]
        chain_inference_summary["pairs_applied"] += chain_combo_summary["variants_filled"]
        chain_inference_summary["derived_cdrh3"] += chain_combo_summary["derived_cdrh3"]
        chain_inference_summary["chain_variant_combinations"] = chain_combo_summary["variants_filled"]
        gap_report = self._build_gap_report(context["skeleton"], paper_id)
        context["gap_report"] = gap_report

        known_sequence_images = self._sequence_image_known_images(context)
        sequence_validation_targets = (
            self._build_sequence_validation_targets(context["skeleton"], paper_id)
            if known_sequence_images
            else []
        )
        vlm_targets = self._combine_vlm_targets(gap_report["targets"], sequence_validation_targets)
        force_sequence_vlm = bool(sequence_validation_targets)
        vlm_summary = {
            "executed": False,
            "records": 0,
            "filled_fields": 0,
            "candidate_images": 0,
            "reason": "no_actionable_gaps",
            "gap_summary": gap_report["summary"],
            "sequence_validation_targets": len(sequence_validation_targets),
        }

        image_data = {}
        if self._should_run_vlm_gap_fill(context, gap_report, vlm_targets):
            print("  Targeted VLM supplementation: active")
            context["current_phase"] = "extract"
            context["vlm_targets"] = vlm_targets
            context["force_sequence_vlm"] = force_sequence_vlm
            context["sequence_image_known_images"] = known_sequence_images
            image_result = await self.image_extractor.execute(context)
            image_data = image_result.data
            image_data["table_records"] = self._validate_sequence_records(
                image_data.get("table_records", []),
                context.get("markdown_text", ""),
                context.get("sequence_image_result", {}),
            )
            image_result.data = image_data
            context["skeleton"], vlm_merge = self._merge_extractions(
                context["skeleton"], paper_id, [image_result]
            )
            post_vlm_chain_combo = self._propagate_chain_variant_combinations(
                context["skeleton"],
                paper_id,
            )
            post_vlm_chain_inference = self._propagate_identical_variant_chains(
                context["skeleton"],
                paper_id,
                md_text_for_inference,
            )
            chain_inference_summary["filled_fields"] += post_vlm_chain_combo["filled_fields"]
            chain_inference_summary["pairs_applied"] += post_vlm_chain_combo["variants_filled"]
            chain_inference_summary["derived_cdrh3"] += post_vlm_chain_combo["derived_cdrh3"]
            chain_inference_summary["chain_variant_combinations"] += post_vlm_chain_combo["variants_filled"]
            chain_inference_summary["filled_fields"] += post_vlm_chain_inference["filled_fields"]
            chain_inference_summary["pairs_applied"] += post_vlm_chain_inference["pairs_applied"]
            chain_inference_summary["derived_cdrh3"] += post_vlm_chain_inference["derived_cdrh3"]
            vlm_summary = {
                "executed": True,
                "records": len(image_data.get("table_records", [])),
                "filled_fields": vlm_merge["filled_fields"],
                "candidate_images": image_result.metrics.get("images_scanned", 0),
                "reason": image_data.get("note", ""),
                "gap_summary": gap_report["summary"],
                "metrics": image_result.metrics,
                "sequence_validation_targets": len(sequence_validation_targets),
            }
        else:
            reason = "disabled_or_no_images"
            if not self.image_extractor:
                reason = "vlm_disabled"
            elif "images/" not in context.get("markdown_text", ""):
                reason = "no_images"
            print(f"  Targeted VLM supplementation: skipped ({reason})")
            vlm_summary["reason"] = reason

        variant_summary = self._expand_multi_target_variants(
            context["skeleton"],
            paper_id,
            self._collect_table_records(structured_results) + image_data.get("table_records", []),
        )
        cross_split_summary = self._split_cross_reactivity_targets(
            context["skeleton"], paper_id
        )
        self._fix_cdrh3_from_vh(context["skeleton"], paper_id)
        experiment_summary = self._refine_experiment_fields(
            context["skeleton"],
            paper_id,
            context.get("markdown_text", ""),
            self._collect_table_records(structured_results) + image_data.get("table_records", []),
        )

        if self.config.save_intermediate:
            table_data = next(
                (
                    r.data
                    for r in structured_results
                    if r.data.get("source") != "sequence_image_tool"
                    and "api_fetched" in r.data
                ),
                {},
            )
            FileUtils.write_json(os.path.join(context["output_dir"], "figure_extracted.json"), table_data)
            FileUtils.write_json(os.path.join(context["output_dir"], "gap_report.json"), gap_report)
            if vlm_summary["executed"] or image_data:
                FileUtils.write_json(os.path.join(context["output_dir"], "image_extracted.json"), image_data)

        return {
            "retry_attempt": retry_attempt,
            "structured": {
                "track_count": len(structured_results),
                "tracks": [r.metrics for r in structured_results],
                "merge": structured_merge,
            },
            "variant_expansion": variant_summary,
            "chain_inference": chain_inference_summary,
            "experiment_refinement": experiment_summary,
            "vlm": vlm_summary,
        }

    async def _run_structured_extraction(self, context: dict) -> list:
        routing = context.get("regex_hints", {}).get("routing_suggestions", [])
        tasks = []
        tracer = context.get("trace_recorder")
        paper_id = context.get("paper_id")

        has_track_a = any("Track A" in r and "not applicable" not in r for r in routing)
        has_track_c = any("Track C" in r and "not applicable" not in r for r in routing)

        if has_track_a:
            print(f"  Track A (API Fetch): active")
            if tracer:
                tracer.record_event("task_scheduled", "extract_track", paper_id=paper_id, phase="extract",
                                    track="api_fetch", state="active")
            tasks.append(self.api_fetcher.execute(context))
        else:
            print(f"  Track A (API Fetch): skipped")
            if tracer:
                tracer.record_event("task_scheduled", "extract_track", paper_id=paper_id, phase="extract",
                                    track="api_fetch", state="skipped")

        if has_track_c:
            print(f"  Track C (Table Extract): active")
            if tracer:
                tracer.record_event("task_scheduled", "extract_track", paper_id=paper_id, phase="extract",
                                    track="table_extract", state="active")
            tasks.append(self.table_extractor.execute(context))
        else:
            print(f"  Track C (Table Extract): skipped")
            if tracer:
                tracer.record_event("task_scheduled", "extract_track", paper_id=paper_id, phase="extract",
                                    track="table_extract", state="skipped")

        if self.config.enable_supplement:
            print(f"  Track B (Supplement): checking...")
            if tracer:
                tracer.record_event("task_scheduled", "extract_track", paper_id=paper_id, phase="extract",
                                    track="supplement", state="active")
            tasks.append(self.supplement_agent.execute(context))

        if not tasks:
            return []

        results = await asyncio.gather(*tasks, return_exceptions=True)
        valid = []
        for r in results:
            if isinstance(r, Exception):
                logger.warning(f"Extract task failed: {r}")
            else:
                valid.append(r)
        return valid

    def _run_text_sequence_extraction(self, context: dict, paper_id: str) -> list[dict]:
        """Extract VH/VL from OCR text alignment blocks (non-table sequences)."""
        markdown_text = context.get("markdown_text", "")
        if not markdown_text:
            return []
        antibodies = context.get("skeleton", {}).get(paper_id, {}).get("antibodies", [])
        ab_names = [ab.get("Antibody_Name", "") for ab in antibodies if ab.get("Antibody_Name")]
        if not ab_names:
            return []
        records = extract_text_sequences(markdown_text, ab_names)
        if records:
            logger.info(f"Text sequence extractor: {len(records)} records from OCR text")
            print(f"  Track D (Text Sequence): {len(records)} records extracted")
        return records

    @staticmethod
    def _start_phase_span(tracer, paper_id: str, phase: str, **fields):
        if not tracer:
            return None
        return tracer.start_span("phase", phase, paper_id=paper_id, phase=phase, **fields)

    @staticmethod
    def _end_phase_span(tracer, span_id, status: str = "success", **fields):
        if tracer:
            tracer.end_span(span_id, status=status, **fields)

    @staticmethod
    def _is_empty_value(value) -> bool:
        return value in (None, "", "N/A", "null", "None")

    @classmethod
    def _build_gap_report(cls, skeleton: dict, paper_id: str) -> dict:
        antibodies = skeleton.get(paper_id, {}).get("antibodies", [])
        targets = []
        missing_counts = {field: 0 for field in sorted(VLM_TARGET_FIELDS)}

        for ab in antibodies:
            missing_fields = []
            for field in sorted(VLM_TARGET_FIELDS):
                if cls._is_empty_value(ab.get(field)):
                    missing_fields.append(field)
                    missing_counts[field] += 1
            if missing_fields:
                targets.append(
                    {
                        "antibody_name": ab.get("Antibody_Name", ""),
                        "missing_fields": missing_fields,
                    }
                )

        return {
            "targets": targets,
            "summary": {
                "total_antibodies": len(antibodies),
                "antibodies_with_gaps": len(targets),
                "missing_counts": {k: v for k, v in missing_counts.items() if v > 0},
            },
        }

    @staticmethod
    def _should_run_vlm_gap_fill(context: dict, gap_report: dict, vlm_targets: list[dict] | None = None) -> bool:
        effective_targets = gap_report["targets"] if vlm_targets is None else vlm_targets
        return bool(
            effective_targets
            and context.get("skeleton", {}).get(context.get("paper_id"), {}).get("antibodies")
            and "images/" in context.get("markdown_text", "")
        )

    @staticmethod
    def _sequence_image_known_images(context: dict) -> set[str]:
        result = context.get("sequence_image_result", {}) or {}
        return {
            str(record.get("_source_image") or "").strip()
            for record in result.get("table_records", [])
            if str(record.get("_source_image") or "").strip()
        }

    @classmethod
    def _build_sequence_validation_targets(cls, skeleton: dict, paper_id: str) -> list[dict]:
        antibodies = skeleton.get(paper_id, {}).get("antibodies", [])
        targets = []
        for ab in antibodies:
            name = (ab.get("Antibody_Name") or "").strip()
            if not name:
                continue
            targets.append(
                {
                    "antibody_name": name,
                    "missing_fields": sorted(SEQUENCE_FIELD_NAMES),
                    "validation_only": True,
                }
            )
        return targets

    @staticmethod
    def _combine_vlm_targets(primary_targets: list[dict], extra_targets: list[dict]) -> list[dict]:
        merged = {}
        for target in list(primary_targets or []) + list(extra_targets or []):
            name = (target.get("antibody_name") or target.get("Antibody_Name") or "").strip()
            if not name:
                continue
            item = merged.setdefault(name.lower(), {"antibody_name": name, "missing_fields": set(), "validation_only": True})
            item["missing_fields"].update(target.get("missing_fields", []))
            item["validation_only"] = item["validation_only"] and bool(target.get("validation_only", False))
        return [
            {
                "antibody_name": item["antibody_name"],
                "missing_fields": sorted(item["missing_fields"]),
                "validation_only": item["validation_only"],
            }
            for item in merged.values()
        ]

    @classmethod
    def _markdown_supports_sequence(cls, md_text: str, value: str) -> bool:
        seq = cls._normalize_aa_sequence(value)
        if len(seq) < 8:
            return False
        md_norm = cls._normalize_aa_sequence(md_text)
        for size in (18, 15, 12, 10, 8):
            if len(seq) < size:
                continue
            for start in range(0, len(seq) - size + 1, max(1, size // 2)):
                if seq[start : start + size] in md_norm:
                    return True
        return False

    @classmethod
    def _sequence_record_supported(cls, record: dict, md_text: str, presequence_by_name: dict[str, dict]) -> bool:
        name = (cls._extract_record_value(record, ("mAb", "Antibody_Name")) or "").strip().lower()
        corroboration = presequence_by_name.get(name, {}) if name else {}
        for field, keys in {
            "vh_sequence_aa": ("VH_sequence", "vh_sequence_aa"),
            "vl_sequence_aa": ("VL_sequence", "vl_sequence_aa"),
            "CDRH3_Sequence": ("CDRH3", "CDRH3_Sequence"),
        }.items():
            value = cls._extract_record_value(record, keys)
            if not value:
                continue
            if cls._markdown_supports_sequence(md_text, value):
                return True
            corroborated = cls._extract_record_value(corroboration, keys)
            if corroborated and cls._normalize_aa_sequence(value) == cls._normalize_aa_sequence(corroborated):
                return True
        return False

    @classmethod
    def _dedup_sequence_image_records(cls, records: list[dict]) -> list[dict]:
        """Mark duplicate sequence-image clusters without dropping sequence values.

        Multiple antibodies from the same figure can legitimately share the
        exact same heavy/light sequences. We therefore keep the extracted
        sequences and attach internal metadata so downstream logic can still
        inspect or review suspicious duplicate clusters.
        """
        if len(records) < 2:
            return records

        # Group by source image
        by_image: dict[str, list[int]] = {}
        for i, rec in enumerate(records):
            img = rec.get("_source_image", "")
            if img:
                by_image.setdefault(img, []).append(i)

        duplicated = set()
        for img, indices in by_image.items():
            if len(indices) < 2:
                continue
            # Check for identical VH sequences within the same image
            vh_groups: dict[str, list[int]] = {}
            for idx in indices:
                vh = cls._normalize_aa_sequence(
                    cls._extract_record_value(records[idx], ("VH_sequence", "vh_sequence_aa"))
                )
                if vh and len(vh) >= cls.MIN_VARIABLE_REGION_AA_LEN:
                    vh_groups.setdefault(vh, []).append(idx)
            for vh_val, dup_indices in vh_groups.items():
                if len(dup_indices) >= 2:
                    names = [records[i].get("mAb", "?") for i in dup_indices]
                    duplicated.update(dup_indices)
                    normalized_names = [str(name or "").strip() for name in names if str(name or "").strip()]
                    normalized_vl = {
                        cls._normalize_aa_sequence(
                            cls._extract_record_value(records[i], ("VL_sequence", "vl_sequence_aa"))
                        )
                        for i in dup_indices
                    }
                    normalized_vl.discard("")
                    normalized_cdrh3 = {
                        cls._normalize_aa_sequence(
                            cls._extract_record_value(records[i], ("CDRH3", "CDRH3_Sequence"))
                        )
                        for i in dup_indices
                    }
                    normalized_cdrh3.discard("")
                    shared_context = any(
                        cls._duplicate_cluster_context_mentions_names(
                            str(records[i].get("_source_context") or ""),
                            normalized_names,
                        )
                        for i in dup_indices
                    )
                    duplicate_note = (
                        "Identical VH extracted for multiple antibodies from the same image. "
                        "Values were preserved because papers can legitimately report shared sequences."
                    )
                    if len(normalized_vl) == 1 and normalized_vl:
                        duplicate_note += " VL also matched across the duplicate cluster."
                    if len(normalized_cdrh3) == 1 and normalized_cdrh3:
                        duplicate_note += " CDRH3 also matched across the duplicate cluster."
                    if shared_context:
                        duplicate_note += " Source context explicitly mentioned the duplicate antibody names together."

                    logger.warning(
                        "Sequence-image duplicate cluster: identical VH (%saa) for %s from %s — preserving sequences",
                        len(vh_val),
                        names,
                        img,
                    )
                    for idx in dup_indices:
                        rec = records[idx]
                        cluster = {
                            "duplicate_type": "identical_vh_same_image",
                            "cluster_size": len(dup_indices),
                            "source_image": img,
                            "antibody_names": normalized_names,
                            "shared_context_named_group": shared_context,
                            "shared_vl_sequence": bool(len(normalized_vl) == 1 and normalized_vl),
                            "shared_cdrh3": bool(len(normalized_cdrh3) == 1 and normalized_cdrh3),
                            "note": duplicate_note,
                        }
                        rec["_sequence_duplicate_cluster"] = cluster
                        rec["_sequence_duplicate_review_required"] = not (
                            cluster["shared_context_named_group"]
                            or cluster["shared_vl_sequence"]
                            or cluster["shared_cdrh3"]
                        )

        if not duplicated:
            return records
        return records

    @classmethod
    def _duplicate_cluster_context_mentions_names(cls, context: str, names: list[str]) -> bool:
        if not context or len(names) < 2:
            return False
        normalized_context = cls._normalize_entity_name(context)
        if not normalized_context:
            return False
        normalized_names = [
            cls._normalize_entity_name(name)
            for name in names
            if cls._normalize_entity_name(name)
        ]
        if len(normalized_names) < 2:
            return False
        return all(name in normalized_context for name in normalized_names)

    @classmethod
    def _validate_sequence_records(cls, records: list[dict], md_text: str, sequence_image_result: dict | None) -> list[dict]:
        presequence_by_name = {
            (str(record.get("mAb") or record.get("Antibody_Name") or "").strip().lower()): record
            for record in (sequence_image_result or {}).get("table_records", [])
            if str(record.get("mAb") or record.get("Antibody_Name") or "").strip()
        }
        validated = []
        for record in records:
            if record.get("_source_category") != "SEQUENCE_DATA":
                validated.append(record)
                continue
            if cls._sequence_record_supported(record, md_text, presequence_by_name):
                validated.append(record)
        return validated

    @staticmethod
    def _collect_table_records(results: list) -> list[dict]:
        records = []
        for result in results:
            records.extend(result.data.get("table_records", []))
        return records

    @staticmethod
    def _extract_record_value(record: dict, src_keys: tuple[str, ...]):
        for src_key in src_keys:
            value = record.get(src_key)
            if value is not None and str(value).strip():
                return str(value).strip()
        return ""

    @classmethod
    def _normalize_aa_sequence(cls, value: str) -> str:
        return normalize_aa_sequence(value)

    @classmethod
    def _normalize_variable_sequence_for_compare(cls, value: str) -> str:
        seq = cls._normalize_aa_sequence(value)
        return re.sub(r"H{5,10}$", "", seq)

    @classmethod
    def _normalize_cdrh3_core(cls, value: str) -> str:
        seq = cls._normalize_aa_sequence(value)
        if seq.startswith("C") and len(seq) > 8:
            seq = seq[1:]
        if seq.endswith("W") and len(seq) > 8:
            seq = seq[:-1]
        return seq

    @classmethod
    def _looks_like_full_variable_sequence(cls, value: str) -> bool:
        seq = cls._normalize_aa_sequence(value)
        return (
            bool(seq)
            and cls.MIN_VARIABLE_REGION_AA_LEN <= len(seq) <= 160
            and set(seq) <= set("ACDEFGHIKLMNPQRSTVWY")
        )

    @classmethod
    def _detect_variable_sequence_chain(cls, value: str) -> str:
        seq = cls._normalize_aa_sequence(value)
        if not cls._looks_like_full_variable_sequence(seq):
            return "unknown"

        heavy_positions = [pos for pos in APIClient._find_chain_start_positions(seq, "heavy") if pos <= 2]
        light_positions = [pos for pos in APIClient._find_chain_start_positions(seq, "light") if pos <= 2]
        heavy_start = min(heavy_positions) if heavy_positions else None
        light_start = min(light_positions) if light_positions else None

        if heavy_start is None and light_start is None:
            return "unknown"
        if heavy_start is None:
            return "light"
        if light_start is None:
            return "heavy"
        if heavy_start < light_start:
            return "heavy"
        if light_start < heavy_start:
            return "light"
        return "unknown"

    @classmethod
    def _sequence_matches_chain_field(cls, field: str, value: str) -> bool:
        if field not in {"vh_sequence_aa", "vl_sequence_aa"}:
            return True
        detected_chain = cls._detect_variable_sequence_chain(value)
        if detected_chain == "unknown":
            return True
        expected_chain = "heavy" if field == "vh_sequence_aa" else "light"
        return detected_chain == expected_chain

    @classmethod
    def _hydrate_sequence_fields_from_hints(cls, antibodies: list[dict]) -> int:
        filled = 0
        for ab in antibodies:
            field_hints = ab.get("_field_hints")
            if not isinstance(field_hints, dict):
                continue

            for field in ("vh_sequence_aa", "vl_sequence_aa", "CDRH3_Sequence"):
                if not cls._is_empty_value(ab.get(field)):
                    continue
                hint = field_hints.get(field)
                if not isinstance(hint, dict):
                    continue

                raw_value = str(hint.get("value") or "").strip()
                if not raw_value:
                    continue

                normalized = cls._normalize_aa_sequence(raw_value)
                if field in {"vh_sequence_aa", "vl_sequence_aa"}:
                    if not cls._looks_like_full_variable_sequence(normalized):
                        continue
                    if not cls._sequence_matches_chain_field(field, normalized):
                        continue
                else:
                    if not (
                        5 <= len(normalized) <= 40
                        and set(normalized) <= STANDARD_AA
                    ):
                        continue

                ab[field] = normalized
                cls._set_field_source(
                    ab,
                    field,
                    {
                        "source_type": "skeleton_hint_normalized",
                        "source_label": str(hint.get("pointer") or "Skeleton hint value").strip(),
                        "action": str(hint.get("action") or "").strip(),
                        "pointer": str(hint.get("pointer") or "").strip(),
                        "quote": str(hint.get("quote") or "").strip(),
                        "note": "Recovered from skeleton _field_hints value after normalizing three-letter amino-acid tokens.",
                    },
                )
                filled += 1

            if cls._is_empty_value(ab.get("CDRH3_Sequence")):
                vh = cls._normalize_aa_sequence(ab.get("vh_sequence_aa", ""))
                if cls._looks_like_full_variable_sequence(vh):
                    derived = APIClient.extract_cdrh3_from_variable_region(vh) or ""
                    if 5 <= len(derived) <= 40 and set(derived) <= STANDARD_AA:
                        ab["CDRH3_Sequence"] = derived
                        vh_source = copy.deepcopy((ab.get("field_sources") or {}).get("vh_sequence_aa", {}))
                        cls._set_field_source(
                            ab,
                            "CDRH3_Sequence",
                            {
                                **vh_source,
                                "source_type": vh_source.get("source_type", "derived_from_vh_hint"),
                                "source_label": vh_source.get("source_label", "Derived from VH sequence"),
                                "note": "Derived from VH sequence recovered from skeleton hint.",
                                "inherited_from_field": "vh_sequence_aa",
                            },
                        )
                        filled += 1

        return filled

    @staticmethod
    def _is_authoritative_sequence_record(record: dict) -> bool:
        return bool(str(record.get("_api_source_ids") or "").strip())

    @staticmethod
    def _is_pdb_sequence_record(record: dict) -> bool:
        return str(record.get("_api_source_kind") or "").strip().lower() == "pdb"

    @staticmethod
    def _levenshtein_distance(a: str, b: str) -> int:
        if a == b:
            return 0
        if not a:
            return len(b)
        if not b:
            return len(a)
        if len(a) < len(b):
            a, b = b, a
        previous = list(range(len(b) + 1))
        for i, ca in enumerate(a, start=1):
            current = [i]
            for j, cb in enumerate(b, start=1):
                current.append(min(
                    previous[j] + 1,
                    current[j - 1] + 1,
                    previous[j - 1] + (ca != cb),
                ))
            previous = current
        return previous[-1]

    @classmethod
    def _sequence_diff_preview(cls, current: str, incoming: str, limit: int = 5) -> list[dict]:
        diffs = []
        for tag, i1, i2, j1, j2 in SequenceMatcher(None, current, incoming).get_opcodes():
            if tag == "equal":
                continue
            diffs.append(
                {
                    "op": tag,
                    "current_start": i1 + 1,
                    "current_end": i2,
                    "current": current[i1:i2],
                    "incoming_start": j1 + 1,
                    "incoming_end": j2,
                    "incoming": incoming[j1:j2],
                }
            )
            if len(diffs) >= limit:
                break
        return diffs

    @classmethod
    def _analyze_sequence_conflict(cls, current: str, incoming: str) -> dict:
        current_cmp = cls._normalize_variable_sequence_for_compare(current)
        incoming_cmp = cls._normalize_variable_sequence_for_compare(incoming)
        if not current_cmp:
            return {
                "action": "replace_with_authoritative",
                "edit_distance": len(incoming_cmp),
                "minor_mismatch": True,
                "note": "Existing sequence is empty after normalization; prefer authoritative sequence.",
                "diff_preview": [],
            }
        if not cls._looks_like_full_variable_sequence(current):
            return {
                "action": "replace_with_authoritative",
                "edit_distance": cls._levenshtein_distance(current_cmp, incoming_cmp),
                "minor_mismatch": True,
                "note": "Existing sequence is not a valid full variable region; prefer authoritative sequence.",
                "diff_preview": cls._sequence_diff_preview(current_cmp, incoming_cmp),
            }
        if current_cmp == incoming_cmp:
            return {
                "action": "replace_with_authoritative",
                "edit_distance": 0,
                "minor_mismatch": True,
                "note": "Sequences agree after normalization/tag stripping; prefer authoritative sequence formatting.",
                "diff_preview": [],
            }

        max_len = max(len(current_cmp), len(incoming_cmp))
        threshold = min(cls.MINOR_SEQUENCE_MISMATCH_MAX_EDITS, max(1, round(max_len * 0.03)))
        edit_distance = cls._levenshtein_distance(current_cmp, incoming_cmp)
        minor = edit_distance <= threshold
        return {
            "action": "replace_with_authoritative" if minor else "keep_existing_review_required",
            "edit_distance": edit_distance,
            "minor_mismatch": minor,
            "note": (
                "Only minor OCR-like residue differences detected; prefer authoritative database sequence."
                if minor
                else "Sequence mismatch is too large for OCR noise; keep existing value and flag for review."
            ),
            "diff_preview": cls._sequence_diff_preview(current_cmp, incoming_cmp),
        }

    @staticmethod
    def _append_sequence_diagnostic(ab: dict, field: str, payload: dict):
        diagnostics = ab.setdefault("_sequence_diagnostics", [])
        entry = {"field": field, **payload}
        if entry not in diagnostics:
            diagnostics.append(entry)

    @staticmethod
    def _ensure_field_sources(ab: dict) -> dict:
        field_sources = ab.get("field_sources")
        if not isinstance(field_sources, dict):
            field_sources = {}
            ab["field_sources"] = field_sources
        return field_sources

    @staticmethod
    def _extract_paper_location(text: str) -> str:
        if not text:
            return ""
        match = re.search(
            r"\b(?:Supplementary\s+(?:Figure|Table)|Extended\s+Data\s+Figure|Figure|Fig\.?|Table|Page)\s*[A-Za-z0-9.\-]+",
            text,
            re.IGNORECASE,
        )
        return match.group(0).strip() if match else ""

    @classmethod
    def _record_source_type(cls, record: dict) -> str:
        if record.get("_discovered_from_text_sequence"):
            return "ocr_text_sequence"
        if str(record.get("_api_source_ids") or "").strip():
            return "api_fetch"
        if record.get("_discovered_from_sequence_image") or record.get("_source_category") == "SEQUENCE_DATA":
            return "sequence_image"
        if str(record.get("_source_image") or "").strip():
            return "figure_or_image"
        return "table_extract"

    @staticmethod
    def _sequence_source_priority(source_type: str) -> int:
        priority_map = {
            "ocr_text_sequence": 1,
            "figure_or_image": 1,
            "table_extract": 1,
            "sequence_image": 2,
            "api_fetch": 3,
        }
        return priority_map.get(str(source_type or "").strip(), 0)

    @classmethod
    def _record_sequence_priority(cls, record: dict) -> int:
        return cls._sequence_source_priority(cls._record_source_type(record))

    @classmethod
    def _existing_sequence_priority(cls, ab: dict, field: str) -> int:
        field_sources = ab.get("field_sources")
        if not isinstance(field_sources, dict):
            return 0
        source = field_sources.get(field, {})
        if not isinstance(source, dict):
            return 0
        return cls._sequence_source_priority(source.get("source_type", ""))

    @classmethod
    def _record_pointer(cls, record: dict) -> str:
        source_ids = str(record.get("_api_source_ids") or "").strip()
        source_kind = str(record.get("_api_source_kind") or "").strip().upper()
        if source_ids:
            prefix = source_kind if source_kind else "API"
            return f"{prefix} {source_ids}"
        source_image = str(record.get("_source_image") or record.get("_ocr_source_image") or "").strip()
        if source_image:
            return source_image
        source_context = str(record.get("_source_context") or "").strip()
        return cls._extract_paper_location(source_context)

    @classmethod
    def _record_source_label(cls, record: dict, source_type: str, pointer: str) -> str:
        if source_type == "api_fetch" and pointer:
            return f"API Fetch: {pointer}"
        if source_type == "ocr_text_sequence":
            return f"OCR text sequence: {pointer}" if pointer else "OCR text sequence"
        if source_type == "sequence_image":
            return f"Sequence image: {pointer}" if pointer else "Sequence image"
        if source_type == "figure_or_image":
            return f"Figure/image: {pointer}" if pointer else "Figure/image"
        if pointer:
            return pointer
        source_context = str(record.get("_source_context") or "").strip()
        return cls._extract_paper_location(source_context)

    @classmethod
    def _build_record_field_source(
        cls,
        record: dict,
        *,
        note: str = "",
        from_antibody: str = "",
        inherited_from_field: str = "",
    ) -> dict:
        source_type = cls._record_source_type(record)
        pointer = cls._record_pointer(record)
        source_context = str(record.get("_source_context") or "").strip()
        payload = {
            "source_type": source_type,
            "source_label": cls._record_source_label(record, source_type, pointer),
            "pointer": pointer,
            "paper_location": cls._extract_paper_location(pointer) or cls._extract_paper_location(source_context),
            "source_image": str(record.get("_source_image") or record.get("_ocr_source_image") or "").strip(),
            "source_context": source_context[:600],
            "api_source_ids": str(record.get("_api_source_ids") or "").strip(),
            "api_source_kind": str(record.get("_api_source_kind") or "").strip(),
            "note": note.strip(),
            "from_antibody": from_antibody.strip(),
            "inherited_from_field": inherited_from_field.strip(),
        }
        return {key: value for key, value in payload.items() if value not in ("", None)}

    @classmethod
    def _set_field_source(cls, ab: dict, field: str, payload: dict):
        clean_payload = {
            key: value
            for key, value in (payload or {}).items()
            if value not in ("", None, [])
        }
        if not clean_payload:
            return
        field_sources = cls._ensure_field_sources(ab)
        existing = field_sources.get(field, {})
        if not isinstance(existing, dict):
            existing = {}
        field_sources[field] = {**existing, **clean_payload}

    @classmethod
    def _set_field_source_from_record(cls, ab: dict, field: str, record: dict, *, note: str = ""):
        cls._set_field_source(
            ab,
            field,
            cls._build_record_field_source(record, note=note),
        )

    @classmethod
    def _clear_field_source(cls, ab: dict, field: str):
        field_sources = ab.get("field_sources")
        if isinstance(field_sources, dict):
            field_sources.pop(field, None)
            if not field_sources:
                ab.pop("field_sources", None)

    def _apply_record_to_antibody(self, ab: dict, record: dict, *, fill_only: bool) -> int:
        filled_fields = 0
        vh_from_record = self._extract_record_value(record, ("VH_sequence", "vh_sequence_aa"))
        vh_norm = self._normalize_aa_sequence(vh_from_record)
        vh_chain_compatible = self._sequence_matches_chain_field("vh_sequence_aa", vh_norm)
        derived_cdrh3 = (
            APIClient.extract_cdrh3_from_variable_region(vh_norm)
            if vh_norm and vh_chain_compatible
            else ""
        )
        authoritative_record = self._is_authoritative_sequence_record(record)
        pdb_record = self._is_pdb_sequence_record(record)
        text_sequence_record = bool(record.get("_discovered_from_text_sequence"))
        sequence_image_record = self._is_sequence_discovery_record(record)
        record_sequence_priority = self._record_sequence_priority(record)
        source_ids = str(record.get("_api_source_ids") or "").strip()
        current_vh_value = str(ab.get("vh_sequence_aa") or "").strip()
        vh_conflict_analysis = None
        if authoritative_record and fill_only and current_vh_value and self._looks_like_full_variable_sequence(vh_norm):
            vh_conflict_analysis = self._analyze_sequence_conflict(current_vh_value, vh_norm)
        for src_keys, dst_key in [
            (("CDRH3", "CDRH3_Sequence"), "CDRH3_Sequence"),
            (("VH_identity_pct",), "_vh_pct"),
            (("VL_identity_pct",), "_vl_pct"),
            (("KD", "Binding_Kinetics_KD"), "Binding_Kinetics_KD"),
            (("EC50", "Binding_EC50"), "Binding_EC50"),
            (("kon", "Binding_Kinetics_kon"), "Binding_Kinetics_kon"),
            (("koff", "Binding_Kinetics_koff"), "Binding_Kinetics_koff"),
            (("Tm", "Thermal_Stability_Tm"), "Thermal_Stability_Tm"),
            (("VH_sequence", "vh_sequence_aa"), "vh_sequence_aa"),
            (("VL_sequence", "vl_sequence_aa"), "vl_sequence_aa"),
            (("IC50", "Quantitative_Metric"), "Quantitative_Metric"),
            (("In_Vivo_Efficacy",), "In_Vivo_Efficacy"),
            (("Structure",), "Structure"),
        ]:
            val = self._extract_record_value(record, src_keys)
            if dst_key == "CDRH3_Sequence" and derived_cdrh3:
                current = self._normalize_aa_sequence(ab.get(dst_key, ""))
                direct = self._normalize_aa_sequence(val)
                if authoritative_record:
                    val = derived_cdrh3
                elif current and current not in vh_norm:
                    val = derived_cdrh3
                elif not direct:
                    val = derived_cdrh3
            if not val or dst_key.startswith("_"):
                continue
            if dst_key in {"vh_sequence_aa", "vl_sequence_aa"}:
                if not self._looks_like_full_variable_sequence(val):
                    continue
                val = self._normalize_aa_sequence(val)
                if not self._sequence_matches_chain_field(dst_key, val):
                    self._append_sequence_diagnostic(
                        ab,
                        dst_key,
                        {
                            "action": "skip_chain_mismatch",
                            "incoming_source_type": self._record_source_type(record),
                            "detected_chain": self._detect_variable_sequence_chain(val),
                            "expected_chain": "heavy" if dst_key == "vh_sequence_aa" else "light",
                            "incoming_length": len(val),
                            "note": "Incoming variable-domain sequence looks like the opposite chain type and was ignored.",
                        },
                    )
                    continue
            elif dst_key == "CDRH3_Sequence":
                val = self._normalize_aa_sequence(val)

            current_value = str(ab.get(dst_key) or "").strip()
            provenance_note = ""
            if dst_key == "CDRH3_Sequence" and derived_cdrh3 and val == derived_cdrh3:
                provenance_note = "Derived from VH variable-region sequence."
            if fill_only and not self._is_empty_value(current_value):
                existing_sequence_priority = 0
                if dst_key in {"vh_sequence_aa", "vl_sequence_aa"}:
                    existing_sequence_priority = self._existing_sequence_priority(ab, dst_key)
                    if current_value == val:
                        if record_sequence_priority > existing_sequence_priority:
                            self._clear_field_source(ab, dst_key)
                            self._set_field_source_from_record(ab, dst_key, record, note=provenance_note)
                        elif existing_sequence_priority == 0:
                            self._set_field_source_from_record(ab, dst_key, record, note=provenance_note)
                        continue
                    if record_sequence_priority < existing_sequence_priority:
                        self._append_sequence_diagnostic(
                            ab,
                            dst_key,
                            {
                                "action": "keep_existing_higher_priority",
                                "current_source_type": (
                                    ((ab.get("field_sources") or {}).get(dst_key) or {}).get("source_type", "")
                                ),
                                "incoming_source_type": self._record_source_type(record),
                                "note": "Lower-priority sequence source cannot overwrite an existing higher-priority value.",
                            },
                        )
                        continue
                if current_value == val:
                    self._set_field_source_from_record(ab, dst_key, record, note=provenance_note)
                    continue
                if dst_key in SEQUENCE_FIELD_NAMES and pdb_record:
                    if current_value != val:
                        self._append_sequence_diagnostic(
                            ab,
                            dst_key,
                            {
                                "action": "replace_with_pdb_authoritative",
                                "source_ids": source_ids,
                                "current_length": len(self._normalize_aa_sequence(current_value)),
                                "incoming_length": len(self._normalize_aa_sequence(val)),
                                "note": "RCSB PDB sequence available; overriding existing extracted value with PDB-derived sequence.",
                            },
                        )
                        if dst_key in {"vh_sequence_aa", "vl_sequence_aa"} and record_sequence_priority > existing_sequence_priority:
                            self._clear_field_source(ab, dst_key)
                elif dst_key == "CDRH3_Sequence" and authoritative_record:
                    if current_value != val:
                        self._append_sequence_diagnostic(
                            ab,
                            dst_key,
                            {
                                "action": "replace_with_pdb_authoritative" if pdb_record else "replace_with_authoritative",
                                "source_ids": source_ids,
                                "current_length": len(self._normalize_aa_sequence(current_value)),
                                "incoming_length": len(self._normalize_aa_sequence(val)),
                                "note": (
                                    "Authoritative database sequence available; overriding existing CDRH3 with database-derived value."
                                ),
                            },
                        )
                elif (
                    dst_key in {"vh_sequence_aa", "vl_sequence_aa"}
                    and sequence_image_record
                    and record_sequence_priority > existing_sequence_priority
                ):
                    self._append_sequence_diagnostic(
                        ab,
                        dst_key,
                        {
                            "action": "replace_with_higher_priority_sequence",
                            "current_source_type": (
                                ((ab.get("field_sources") or {}).get(dst_key) or {}).get("source_type", "")
                            ),
                            "incoming_source_type": self._record_source_type(record),
                            "note": "Replacing lower-priority sequence value with a higher-priority source.",
                        },
                    )
                    self._clear_field_source(ab, dst_key)
                elif dst_key in {"vh_sequence_aa", "vl_sequence_aa"} and text_sequence_record:
                    # Text-sequence (OCR alignment block) always overrides
                    # sequence-image VLM results — OCR text is more reliable.
                    logger.info(
                        f"Text-sequence override: {ab.get('Antibody_Name')} {dst_key} "
                        f"(old={len(self._normalize_aa_sequence(current_value))}aa → "
                        f"new={len(self._normalize_aa_sequence(val))}aa)"
                    )
                elif dst_key in {"vh_sequence_aa", "vl_sequence_aa"} and authoritative_record:
                    analysis = vh_conflict_analysis if dst_key == "vh_sequence_aa" and vh_conflict_analysis else self._analyze_sequence_conflict(current_value, val)
                    if current_value != val:
                        self._append_sequence_diagnostic(
                            ab,
                            dst_key,
                            {
                                "action": "replace_with_pdb_authoritative" if pdb_record else "replace_with_authoritative",
                                "source_ids": source_ids,
                                "current_length": len(self._normalize_aa_sequence(current_value)),
                                "incoming_length": len(self._normalize_aa_sequence(val)),
                                "edit_distance": analysis["edit_distance"],
                                "note": (
                                    "Authoritative database sequence available; overriding existing extracted value with database-derived sequence."
                                ),
                                "diff_preview": analysis["diff_preview"],
                            },
                        )
                elif (
                    dst_key in {"vh_sequence_aa", "vl_sequence_aa"}
                    and record_sequence_priority > existing_sequence_priority
                ):
                    # Table-extract or other higher-priority source can overwrite
                    # skeleton-generated sequences (priority 0).
                    self._append_sequence_diagnostic(
                        ab,
                        dst_key,
                        {
                            "action": "replace_with_higher_priority_sequence",
                            "current_source_type": (
                                ((ab.get("field_sources") or {}).get(dst_key) or {}).get("source_type", "")
                            ),
                            "incoming_source_type": self._record_source_type(record),
                            "note": "Replacing lower-priority sequence value with a higher-priority source.",
                        },
                    )
                    self._clear_field_source(ab, dst_key)
                elif dst_key != "CDRH3_Sequence":
                    continue
                else:
                    current = self._normalize_aa_sequence(ab.get(dst_key, ""))
                    incoming = self._normalize_aa_sequence(val)
                    current_source = ((ab.get("field_sources") or {}).get(dst_key) or {})
                    current_source_type = str(current_source.get("source_type") or "").strip().lower()
                    # Allow overwrite if: (a) derived CDRH3 corrects VH inconsistency
                    vh_correction = derived_cdrh3 and current and current not in vh_norm and val == derived_cdrh3
                    # (b) incoming is longer and contains the current as a substring
                    # (table parser gives full CDRH3 peptide vs skeleton's truncated core)
                    longer_superset = (
                        incoming and current
                        and len(incoming) > len(current)
                        and current in incoming
                    )
                    # If CDRH3 already comes from explicit paper/table text, do not let a
                    # non-authoritative VH-derived guess from sequence-image VLM output replace it.
                    if (
                        vh_correction
                        and not authoritative_record
                        and current_source_type in {"paper_text", "table", "ocr_text_sequence"}
                    ):
                        continue
                    if not (vh_correction or longer_superset):
                        continue
            if ab.get(dst_key) != val:
                ab[dst_key] = val
                filled_fields += 1
                self._set_field_source_from_record(ab, dst_key, record, note=provenance_note)
            elif val:
                self._set_field_source_from_record(ab, dst_key, record, note=provenance_note)

        return filled_fields

    @classmethod
    def _is_sequence_discovery_record(cls, record: dict) -> bool:
        return bool(
            record.get("_discovered_from_sequence_image")
            or record.get("_source_category") == "SEQUENCE_DATA"
            or record.get("_source") == "sequence_image_tool"
        )

    @classmethod
    def _record_looks_reference_only(cls, record: dict) -> bool:
        context = " ".join(
            str(record.get(key) or "")
            for key in ("_source_context", "_source_image", "_source_crop_image")
        )
        if not context:
            return False
        lowered = context.lower()
        return any(
            re.search(pattern, lowered, re.IGNORECASE)
            for pattern in cls.REFERENCE_ONLY_CONTEXT_PATTERNS
        )

    @classmethod
    def _record_supports_new_antibody(cls, record: dict) -> bool:
        vh = cls._extract_record_value(record, ("VH_sequence", "vh_sequence_aa"))
        vl = cls._extract_record_value(record, ("VL_sequence", "vl_sequence_aa"))
        cdrh3 = cls._normalize_aa_sequence(cls._extract_record_value(record, ("CDRH3", "CDRH3_Sequence")))
        has_sequence = (
            cls._looks_like_full_variable_sequence(vh)
            or cls._looks_like_full_variable_sequence(vl)
            or len(cdrh3) >= 5
        )
        has_quantitative_readout = any(
            cls._extract_record_value(record, keys)
            for keys in [
                ("KD", "Binding_Kinetics_KD"),
                ("kon", "Binding_Kinetics_kon"),
                ("koff", "Binding_Kinetics_koff"),
                ("EC50", "Binding_EC50"),
                ("IC50", "Quantitative_Metric"),
                ("Tm", "Thermal_Stability_Tm"),
            ]
        )
        if cls._record_looks_reference_only(record):
            return False
        # Allow new antibody creation from sequence-image records OR
        # from table records that have at least CDRH3 (≥5 AA)
        if cls._is_sequence_discovery_record(record) and has_sequence:
            return True
        if has_sequence and has_quantitative_readout:
            return True
        # Also allow table records with CDRH3 + isotype/constant-region info
        if has_sequence:
            isotype = cls._extract_record_value(record, (
                "Constant region genes", "Antibody_Isotype", "isotype",
                "Constant_region", "constant_region_genes",
            ))
            if isotype:
                return True
        return False

    @classmethod
    def _consensus_field(cls, antibodies: list[dict], field: str) -> str:
        values = []
        seen = set()
        for ab in antibodies:
            value = str(ab.get(field) or "").strip()
            if not value:
                continue
            canon = value.lower()
            if canon not in seen:
                seen.add(canon)
                values.append(value)
        return values[0] if len(values) == 1 else ""

    @classmethod
    def _build_discovered_antibody_shell(cls, antibodies: list[dict], paper_id: str, record: dict) -> dict:
        name = cls._extract_record_value(record, ("mAb", "Antibody_Name"))
        reference = cls._consensus_field(antibodies, "Reference_Source") or paper_id
        target_name = cls._extract_record_value(record, ("Target_Name",)) or cls._consensus_field(antibodies, "Target_Name")
        return {
            "Antibody_Name": name,
            "Antibody_Type": "",
            "Antibody_Isotype": "",
            "source": cls._consensus_field(antibodies, "source"),
            "Target_Name": target_name,
            "Target_Type": cls._consensus_field(antibodies, "Target_Type"),
            "Cross_Reactivity": "",
            "Epitope": "",
            "Experiment": "",
            "Binding_Kinetics_KD": "",
            "Binding_Kinetics_kon": "",
            "Binding_Kinetics_koff": "",
            "Binding_EC50": "",
            "Mechanism_of_Action": "",
            "Quantitative_Metric": "",
            "Structure": "",
            "CDRH3_Sequence": "",
            "vh_sequence_aa": "",
            "vl_sequence_aa": "",
            "Thermal_Stability_Tm": "",
            "In_Vivo_Half_Life": "",
            "In_Vivo_Efficacy": "",
            "Reference_Source": reference,
        }

    @staticmethod
    def _canonical_target(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()

    @classmethod
    def _split_candidate_targets(cls, value: str) -> list[str]:
        candidates = []
        for part in re.split(r"\s*[;|]\s*", value or ""):
            norm = part.strip()
            if norm and cls._canonical_target(norm) not in {cls._canonical_target(v) for v in candidates}:
                candidates.append(norm)
        return candidates

    @classmethod
    def _looks_like_target_label(cls, value: str) -> bool:
        canon = cls._canonical_target(value)
        return bool(canon and (re.search(r"\b[a-z]+\s*[a-z]*\s*\d+\b", canon) or "spike" in canon or "rbd" in canon))

    @classmethod
    def _target_candidates_for_antibody(cls, ab: dict) -> list[str]:
        candidates = []
        for raw in [ab.get("Target_Name", ""), ab.get("Cross_Reactivity", "")]:
            for value in cls._split_candidate_targets(raw):
                if value and (value == ab.get("Target_Name", "") or cls._looks_like_target_label(value)):
                    if cls._canonical_target(value) not in {cls._canonical_target(v) for v in candidates}:
                        candidates.append(value)
        return candidates

    @classmethod
    def _infer_record_target(cls, record: dict, base_ab: dict) -> str:
        explicit = cls._extract_record_value(record, ("Target_Name",))
        if explicit:
            return explicit

        context = " ".join(
            [
                cls._extract_record_value(record, ("_source_context",)),
                cls._extract_record_value(record, ("_source_image",)),
            ]
        )
        if re.search(r"VACV\s*A33|VACVA33", context, re.IGNORECASE):
            return "VACV A33"
        if re.search(r"MPXV\s*A35|A35\s*\+|Clade\s*IIb", context, re.IGNORECASE):
            return base_ab.get("Target_Name", "") or "MPXV A35 (Clade IIb)"
        return ""

    @staticmethod
    def _normalize_metric_value(value: str) -> str:
        return re.sub(r"\s+", "", (value or "").lower())

    @staticmethod
    def _extract_assay_methods(text: str) -> list[str]:
        methods = []
        patterns = [
            ("ELISA", r"\bELISA\b|enzyme-linked immunosorbent"),
            ("BLI", r"\bBLI\b|biolayer interferometry"),
            ("SPR", r"\bSPR\b|surface plasmon resonance"),
            ("Beacon", r"\bBeacon\b"),
        ]
        for label, pattern in patterns:
            if re.search(pattern, text or "", re.IGNORECASE):
                methods.append(label)
        return methods

    @classmethod
    def _needs_experiment_refinement(cls, current: str) -> bool:
        if not current:
            return True
        return not cls._extract_assay_methods(current)

    @classmethod
    def _record_has_kinetics(cls, record: dict) -> bool:
        return any(
            cls._extract_record_value(record, keys)
            for keys in [
                ("KD", "Binding_Kinetics_KD"),
                ("kon", "Binding_Kinetics_kon"),
                ("koff", "Binding_Kinetics_koff"),
                ("EC50", "Binding_EC50"),
            ]
        )

    @staticmethod
    def _looks_like_binding_panel(context: str) -> bool:
        return bool(re.search(r"virus-only|binding|time\s*\(seconds\)|a35|a33", context or "", re.IGNORECASE))

    def _refine_experiment_fields(self, skeleton: dict, paper_id: str, md_text: str, extract_records: list[dict]) -> dict:
        antibodies = skeleton.get(paper_id, {}).get("antibodies", [])
        if not antibodies:
            return {"updated": 0}

        global_methods = self._extract_assay_methods(md_text)
        by_name = {}
        for record in extract_records:
            name = self._extract_record_value(record, ("mAb", "Antibody_Name")).lower()
            if name:
                by_name.setdefault(name, []).append(record)

        updated = 0
        for ab in antibodies:
            if not self._needs_experiment_refinement(ab.get("Experiment", "")):
                continue

            methods = []
            name = (ab.get("Antibody_Name") or "").lower()
            records = by_name.get(name, [])
            if any(
                (record.get("_source_category") == "KINETICS_DATA")
                or self._record_has_kinetics(record)
                for record in records
            ):
                methods.append("BLI")

            methods.extend(method for method in global_methods if method not in methods)

            if (
                "ELISA" not in methods
                and ab.get("Target_Name")
                and (
                    ab.get("Cross_Reactivity")
                    or ab.get("CDRH3_Sequence")
                    or self._looks_like_binding_panel(" ".join(record.get("_source_context", "") for record in records))
                )
            ):
                methods.append("ELISA")

            new_value = ",".join(methods)
            if ab.get("Experiment", "") != new_value:
                ab["Experiment"] = new_value
                if records:
                    self._set_field_source_from_record(
                        ab,
                        "Experiment",
                        records[0],
                        note="Refined from kinetics/table evidence and assay mentions.",
                    )
                elif methods:
                    self._set_field_source(
                        ab,
                        "Experiment",
                        {
                            "source_type": "paper_text",
                            "source_label": "Paper text assay mentions",
                            "quote": ", ".join(methods),
                            "note": "Refined from direct assay mentions in the paper text.",
                        },
                    )
                updated += 1

        skeleton[paper_id]["antibodies"] = antibodies
        return {"updated": updated}

    @classmethod
    def _metric_signature(cls, record: dict) -> tuple[str, ...]:
        return (
            cls._normalize_metric_value(cls._extract_record_value(record, ("KD", "Binding_Kinetics_KD"))),
            cls._normalize_metric_value(cls._extract_record_value(record, ("kon", "Binding_Kinetics_kon"))),
            cls._normalize_metric_value(cls._extract_record_value(record, ("koff", "Binding_Kinetics_koff"))),
            cls._normalize_metric_value(cls._extract_record_value(record, ("EC50", "Binding_EC50"))),
            cls._normalize_metric_value(cls._extract_record_value(record, ("IC50", "Quantitative_Metric"))),
            cls._normalize_metric_value(cls._extract_record_value(record, ("Tm", "Thermal_Stability_Tm"))),
        )

    @classmethod
    def _kd_sort_key(cls, record: dict) -> float:
        value = cls._extract_record_value(record, ("KD", "Binding_Kinetics_KD"))
        if not value:
            return float("inf")
        cleaned = value.replace("μ", "u").replace("µ", "u").strip().lower()
        match = re.search(r"([<>]=?)?\s*([0-9]*\.?[0-9]+)\s*([a-z/0-9^()-]*)", cleaned)
        if not match:
            return float("inf")
        numeric = float(match.group(2))
        unit = match.group(3)
        multiplier = 1.0
        if unit.startswith("pm"):
            multiplier = 1e-3
        elif unit.startswith("um"):
            multiplier = 1e3
        elif unit.startswith("mm"):
            multiplier = 1e6
        value_nm = numeric * multiplier
        if match.group(1) and "<" in match.group(1):
            value_nm *= 0.5
        return value_nm

    @classmethod
    def _merge_profile_records(cls, records: list[dict], base_target: str) -> dict:
        merged = {}
        for record in records:
            for key, value in record.items():
                if key.startswith("_"):
                    continue
                if value is not None and str(value).strip() and (key not in merged or not str(merged[key]).strip()):
                    merged[key] = value
        merged["Target_Name"] = cls._extract_record_value(records[0], ("Target_Name",)) or base_target
        merged["_source_records"] = len(records)
        return merged

    @classmethod
    def _targets_compatible(cls, structure: str, target_name: str) -> bool:
        if not structure or not target_name:
            return True
        structure_l = structure.lower()
        target_l = target_name.lower()
        if "a35" in structure_l and "a35" not in target_l:
            return False
        if "a33" in structure_l and "a33" not in target_l:
            return False
        return True

    def _expand_multi_target_variants(self, skeleton: dict, paper_id: str, extract_records: list[dict]) -> dict:
        antibodies = skeleton.get(paper_id, {}).get("antibodies", [])
        if not antibodies or not extract_records:
            return {"expanded_records": 0, "profiles_seen": 0}

        by_name = {}
        for idx, ab in enumerate(antibodies):
            name = (ab.get("Antibody_Name") or "").strip().lower()
            if name:
                by_name.setdefault(name, []).append(idx)

        records_by_name = {}
        for record in extract_records:
            name = self._extract_record_value(record, ("mAb", "Antibody_Name")).lower()
            if name and name in by_name:
                records_by_name.setdefault(name, []).append(record)

        expanded_records = 0
        profiles_seen = 0

        for name, records in records_by_name.items():
            base_ab = antibodies[by_name[name][0]]
            target_candidates = self._target_candidates_for_antibody(base_ab)
            explicit_targets = []
            for record in records:
                target = self._infer_record_target(record, base_ab)
                if target and self._canonical_target(target) not in {self._canonical_target(v) for v in explicit_targets}:
                    explicit_targets.append(target)
            target_candidates.extend(
                target for target in explicit_targets
                if self._canonical_target(target) not in {self._canonical_target(v) for v in target_candidates}
            )
            if len(target_candidates) < 2:
                continue
            if len(explicit_targets) < 2:
                # Do not auto-split a single antibody into multiple target records
                # based only on broad cross-reactivity summaries or unresolved profiles.
                continue

            profile_map = {}
            for record in records:
                signature = self._metric_signature(record)
                if not any(signature):
                    continue
                profiles_seen += 1
                target = self._infer_record_target(record, base_ab)
                key = (self._canonical_target(target), signature)
                bucket = profile_map.setdefault(key, {"target": target, "records": []})
                bucket["records"].append(record)

            unique_profiles = list(profile_map.values())
            if len(unique_profiles) < 2:
                continue

            if any(not profile["target"] for profile in unique_profiles):
                continue

            grouped_profiles = {}
            for profile in unique_profiles:
                target = profile["target"]
                canon = self._canonical_target(target)
                grouped_profiles.setdefault(canon, {"target": target, "records": []})
                grouped_profiles[canon]["records"].extend(profile["records"])

            if len(grouped_profiles) < 2:
                continue

            existing_by_target = {}
            for idx in by_name[name]:
                canon = self._canonical_target(antibodies[idx].get("Target_Name", ""))
                if canon:
                    existing_by_target[canon] = idx

            for canon, profile in grouped_profiles.items():
                target_name = profile["target"]
                merged_record = self._merge_profile_records(profile["records"], target_name)
                idx = existing_by_target.get(canon)
                if idx is None:
                    clone = copy.deepcopy(base_ab)
                    clone["Target_Name"] = target_name
                    for field in (
                        "Binding_Kinetics_KD",
                        "Binding_Kinetics_kon",
                        "Binding_Kinetics_koff",
                        "Binding_EC50",
                        "Quantitative_Metric",
                        "Thermal_Stability_Tm",
                        "In_Vivo_Efficacy",
                    ):
                        clone[field] = ""
                        self._clear_field_source(clone, field)
                    if not self._targets_compatible(clone.get("Structure", ""), target_name):
                        clone["Structure"] = ""
                        self._clear_field_source(clone, "Structure")
                    antibodies.append(clone)
                    idx = len(antibodies) - 1
                    by_name[name].append(idx)
                    existing_by_target[canon] = idx
                    expanded_records += 1

                antibodies[idx]["Target_Name"] = target_name
                self._apply_record_to_antibody(antibodies[idx], merged_record, fill_only=False)

        skeleton[paper_id]["antibodies"] = antibodies
        return {"expanded_records": expanded_records, "profiles_seen": profiles_seen}

    @classmethod
    @classmethod
    def _derive_cdrh3_from_vh(cls, vh_seq: str) -> str | None:
        """Derive CDRH3 from VH sequence using conserved framework motifs.

        CDRH3 is located between the last Cys in the conserved C-x-x motif
        (typically CAR, CAK, etc.) before FW4 and the WGQG FW4 start.
        Returns the CDRH3 WITHOUT the leading C anchor, or None if not found.
        """
        if not vh_seq or len(vh_seq) < 80:
            return None
        vh = vh_seq.upper().strip()
        # Find FW4 start: WGQG or WG.G pattern near the end (last 15 residues)
        # Use a bounded search to avoid matching WGAG etc. in framework 1
        tail = vh[-15:] if len(vh) > 15 else vh
        tail_offset = len(vh) - len(tail)
        fw4_match = re.search(r'WG[A-Z]G', tail)
        if not fw4_match:
            return None
        fw4_start = tail_offset + fw4_match.start()
        # Walk backwards from fw4 to find the conserved Cys anchor
        # Typically: ...YYC + CDR3 + WGQG...
        # Search for YYC, YFC, YHC patterns before fw4
        prefix = vh[:fw4_start]
        cys_pos = None
        for pattern in ['YYC', 'YFC', 'FYC', 'YHC', 'YLC', 'YIC', 'FFC']:
            idx = prefix.rfind(pattern)
            if idx >= 0:
                cys_pos = idx + len(pattern) - 1  # position of C
                break
        if cys_pos is None:
            # Fallback: find last C before fw4 that's after position 80
            for i in range(fw4_start - 1, max(fw4_start - 30, 79), -1):
                if vh[i] == 'C':
                    cys_pos = i
                    break
        if cys_pos is None:
            return None
        # CDRH3 = residues between Cys anchor (exclusive) and FW4 start (exclusive)
        cdrh3 = vh[cys_pos + 1:fw4_start]
        if len(cdrh3) < 3:
            return None
        return cdrh3

    @classmethod
    def _fix_cdrh3_from_vh(cls, skeleton: dict, paper_id: str):
        """Fix CDRH3 contamination: derive CDRH3 from VH when available.

        Table S2-style CDRH3 columns sometimes concatenate VH CDR3 + VL CDR3.
        If we have the full VH sequence, derive the true CDRH3 from it.
        """
        antibodies = skeleton.get(paper_id, {}).get("antibodies", [])
        for ab in antibodies:
            vh = ab.get("vh_sequence_aa", "")
            if not vh or len(vh) < 80:
                continue
            current_cdrh3 = ab.get("CDRH3_Sequence", "")
            if not current_cdrh3:
                continue
            derived = cls._derive_cdrh3_from_vh(vh)
            if not derived:
                continue
            # Strip leading C from current if present (some conventions include it)
            current_clean = current_cdrh3.lstrip("C") if current_cdrh3.startswith("C") else current_cdrh3
            derived_clean = derived
            # Check if current CDRH3 is longer than derived and contains it as prefix
            # This indicates VL CDR3 contamination
            if (len(current_clean) > len(derived_clean) + 3
                    and current_clean.startswith(derived_clean[:min(10, len(derived_clean))])):
                old_val = ab["CDRH3_Sequence"]
                # Keep the C prefix convention if original had it
                if current_cdrh3.startswith("C") and not derived.startswith("C"):
                    ab["CDRH3_Sequence"] = "C" + derived
                else:
                    ab["CDRH3_Sequence"] = derived
                vh_source = {}
                if isinstance(ab.get("field_sources"), dict):
                    vh_source = copy.deepcopy(ab["field_sources"].get("vh_sequence_aa", {}))
                cls._set_field_source(
                    ab,
                    "CDRH3_Sequence",
                    {
                        **vh_source,
                        "source_type": "derived_from_vh",
                        "source_label": "Derived from VH sequence",
                        "inherited_from_field": "vh_sequence_aa",
                        "note": "CDRH3 corrected by deriving the heavy-chain CDR3 from VH and removing likely VL contamination.",
                    },
                )
                logger.info(
                    f"CDRH3 fix: {ab.get('Antibody_Name')} "
                    f"'{old_val}' ({len(old_val)}aa) → "
                    f"'{ab['CDRH3_Sequence']}' ({len(ab['CDRH3_Sequence'])}aa) "
                    f"[VL CDR3 contamination removed]"
                )

    def _split_cross_reactivity_targets(cls, skeleton: dict, paper_id: str) -> dict:
        """Split antibodies with explicit Cross_Reactivity into per-target records.

        When an antibody has Target_Name=X and Cross_Reactivity=Y (where Y is a
        specific target name, not just a species/family), create a duplicate record
        with Target_Name=Y. Binding metrics are cleared on the clone since they
        may be target-specific. Sequences and other identity fields are copied.
        """
        antibodies = skeleton.get(paper_id, {}).get("antibodies", [])
        if not antibodies:
            return {"split_records": 0}

        existing_keys = set()
        for ab in antibodies:
            name = (ab.get("Antibody_Name") or "").strip().lower()
            target = cls._canonical_target(ab.get("Target_Name", ""))
            if name and target:
                existing_keys.add((name, target))

        new_records = []
        for ab in antibodies:
            cross = (ab.get("Cross_Reactivity") or "").strip()
            if not cross:
                continue
            name = (ab.get("Antibody_Name") or "").strip().lower()
            if not name:
                continue
            for candidate in cls._split_candidate_targets(cross):
                if not cls._looks_like_target_label(candidate):
                    continue
                canon = cls._canonical_target(candidate)
                if (name, canon) in existing_keys:
                    continue
                # Create a new record for this target
                clone = copy.deepcopy(ab)
                clone["Target_Name"] = candidate
                clone["Cross_Reactivity"] = ab.get("Target_Name", "")
                # Clear target-specific metrics (they differ between targets)
                for field in (
                    "Binding_Kinetics_KD", "Binding_Kinetics_kon",
                    "Binding_Kinetics_koff", "Binding_EC50",
                    "Quantitative_Metric",
                ):
                    clone[field] = ""
                    cls._clear_field_source(clone, field)
                # Adjust in-vivo efficacy if it mentions the original target
                if clone.get("In_Vivo_Efficacy"):
                    clone["In_Vivo_Efficacy"] = ""
                    cls._clear_field_source(clone, "In_Vivo_Efficacy")
                # Remove structure if it's specific to the original target complex
                if not cls._targets_compatible(clone.get("Structure", ""), candidate):
                    clone["Structure"] = ""
                    cls._clear_field_source(clone, "Structure")
                new_records.append(clone)
                existing_keys.add((name, canon))
                logger.info(f"Cross-reactivity split: {ab.get('Antibody_Name')} → {candidate}")

        antibodies.extend(new_records)
        skeleton[paper_id]["antibodies"] = antibodies
        return {"split_records": len(new_records)}

    @classmethod
    def _synchronize_entity_sequence_fields(cls, antibodies: list[dict]) -> int:
        groups = {}
        for idx, ab in enumerate(antibodies):
            name = (ab.get("Antibody_Name") or "").strip().lower()
            if name:
                groups.setdefault(name, []).append(idx)

        filled = 0
        for indices in groups.values():
            if len(indices) < 2:
                continue

            best_values = {}
            for field in ("CDRH3_Sequence", "vh_sequence_aa", "vl_sequence_aa"):
                candidates = []
                for idx in indices:
                    value = str(antibodies[idx].get(field) or "").strip()
                    if not value:
                        continue
                    if field in {"vh_sequence_aa", "vl_sequence_aa"}:
                        if not cls._looks_like_full_variable_sequence(value):
                            continue
                        value = cls._normalize_aa_sequence(value)
                        if not cls._sequence_matches_chain_field(field, value):
                            continue
                    candidates.append(value)
                if candidates:
                    best_values[field] = max(candidates, key=len)

            for idx in indices:
                ab = antibodies[idx]
                for field, best_value in best_values.items():
                    if cls._is_empty_value(ab.get(field)):
                        ab[field] = best_value
                        donor_source = {}
                        for candidate_idx in indices:
                            candidate = antibodies[candidate_idx]
                            candidate_value = str(candidate.get(field) or "").strip()
                            if field in {"vh_sequence_aa", "vl_sequence_aa"}:
                                candidate_value = cls._normalize_aa_sequence(candidate_value)
                            if candidate_value == best_value and isinstance(candidate.get("field_sources"), dict):
                                donor_source = copy.deepcopy(candidate["field_sources"].get(field, {}))
                                if donor_source:
                                    break
                        cls._set_field_source(
                            ab,
                            field,
                            {
                                **donor_source,
                                "source_type": donor_source.get("source_type", "entity_sync"),
                                "source_label": donor_source.get("source_label", "Synchronized across same antibody entity"),
                                "note": "Copied from another record with the same antibody name.",
                            },
                        )
                        filled += 1

        return filled

    @staticmethod
    def _normalize_entity_name(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", (value or "").lower())

    @classmethod
    def _tokenize_antibody_name(cls, value: str) -> list[str]:
        return [token for token in re.split(r"[^a-z0-9]+", (value or "").lower()) if token]

    @classmethod
    def _strip_variant_name_noise(cls, value: str) -> str:
        text = (value or "").lower()
        for pattern in cls.VARIANT_NAME_NOISE_PATTERNS:
            text = re.sub(pattern, " ", text, flags=re.IGNORECASE)
        return cls._normalize_entity_name(text)

    @classmethod
    def _candidate_parent_names(cls, antibody_name: str, available_names: list[str]) -> list[str]:
        child_norm = cls._normalize_entity_name(antibody_name)
        stripped_child = cls._strip_variant_name_noise(antibody_name)
        candidates = []
        for candidate in available_names:
            if candidate == antibody_name:
                continue
            candidate_norm = cls._normalize_entity_name(candidate)
            if not candidate_norm or len(candidate_norm) >= len(child_norm):
                continue
            if stripped_child and stripped_child == candidate_norm:
                candidates.append((candidate, 3, len(candidate_norm)))
                continue
            if child_norm.startswith(candidate_norm) or child_norm.endswith(candidate_norm):
                candidates.append((candidate, 2, len(candidate_norm)))
                continue
            if stripped_child and (
                stripped_child.startswith(candidate_norm) or stripped_child.endswith(candidate_norm)
            ):
                candidates.append((candidate, 1, len(candidate_norm)))
        ordered = []
        for candidate, _, _ in sorted(candidates, key=lambda item: (item[1], item[2]), reverse=True):
            if candidate not in ordered:
                ordered.append(candidate)
        return ordered

    @classmethod
    def _text_windows(cls, text: str) -> list[str]:
        windows = []
        seen = set()
        for block in re.split(r"\n+", text or ""):
            block = re.sub(r"\s+", " ", block).strip()
            if not block:
                continue
            for part in re.split(r"(?<=[.;:])\s+", block):
                part = part.strip()
                if part and part not in seen:
                    seen.add(part)
                    windows.append(part)
        return windows

    @classmethod
    def _chain_field_context(cls, field: str) -> tuple[list[str], list[str]]:
        if field == "vh_sequence_aa":
            return (
                ["heavy chain", "vh", "heavy-chain"],
                ["light chain", "vl", "light-chain"],
            )
        return (
            ["light chain", "vl", "light-chain", "kappa chain", "lambda chain"],
            ["heavy chain", "vh", "heavy-chain"],
        )

    @classmethod
    def _window_supports_chain_identity(
        cls,
        window: str,
        child_name: str,
        parent_name: str,
        field: str,
    ) -> bool:
        lowered = (window or "").lower()
        if not lowered:
            return False

        positive_terms, negative_terms = cls._chain_field_context(field)
        if not any(term in lowered for term in positive_terms):
            return False
        if any(term in lowered for term in negative_terms) and not any(term in lowered for term in positive_terms):
            return False
        if not any(keyword in lowered for keyword in cls.CHAIN_IDENTITY_KEYWORDS):
            return False

        child_norm = cls._normalize_entity_name(child_name)
        parent_norm = cls._normalize_entity_name(parent_name)
        window_norm = cls._normalize_entity_name(window)
        child_tokens = cls._tokenize_antibody_name(child_name)
        parent_tokens = set(cls._tokenize_antibody_name(parent_name))
        extra_tokens = [
            token for token in child_tokens
            if token not in parent_tokens and token not in {"wt", "wild", "type"}
        ]

        mentions_child = child_norm and child_norm in window_norm
        mentions_parent = parent_norm and parent_norm in window_norm
        mentions_variant_suffix = any(token in lowered for token in extra_tokens if len(token) >= 2)
        mentions_reference = any(keyword in lowered for keyword in cls.CHAIN_REFERENCE_KEYWORDS)

        return (mentions_child or mentions_parent or mentions_variant_suffix) and (mentions_parent or mentions_reference)

    @classmethod
    def _find_chain_identity_evidence(
        cls,
        text: str,
        child_name: str,
        parent_name: str,
        field: str,
    ) -> str:
        for window in cls._text_windows(text):
            if cls._window_supports_chain_identity(window, child_name, parent_name, field):
                return window
        return ""

    @classmethod
    def _select_best_parent_record(cls, antibodies: list[dict], parent_name: str) -> dict | None:
        candidates = [
            ab for ab in antibodies
            if (ab.get("Antibody_Name") or "").strip().lower() == parent_name.lower()
        ]
        if not candidates:
            return None
        return max(
            candidates,
            key=lambda ab: (
                len(cls._normalize_aa_sequence(ab.get("vh_sequence_aa", ""))),
                len(cls._normalize_aa_sequence(ab.get("vl_sequence_aa", ""))),
                len(cls._normalize_aa_sequence(ab.get("CDRH3_Sequence", ""))),
            ),
        )

    @classmethod
    def _append_sequence_inheritance(
        cls,
        ab: dict,
        *,
        field: str,
        parent_name: str,
        evidence: str,
    ):
        inheritance = ab.setdefault("_sequence_inheritance", [])
        payload = {
            "field": field,
            "from_antibody": parent_name,
            "evidence": evidence,
        }
        if payload not in inheritance:
            inheritance.append(payload)

    @staticmethod
    def _normalized_name_tokens(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", (value or "").lower())

    @classmethod
    def _extract_chain_combo_tokens(cls, value: str) -> tuple[str, str] | None:
        normalized = cls._normalized_name_tokens(value)
        match = re.search(r"h(\d+)l(\d+)", normalized)
        if not match:
            return None
        return match.group(1), match.group(2)

    @classmethod
    def _extract_single_chain_token(cls, value: str) -> tuple[str, str] | None:
        normalized = cls._normalized_name_tokens(value)
        if re.search(r"h\d+l\d+", normalized):
            return None
        matches = re.findall(r"([hl])(\d+)", normalized)
        if len(matches) != 1:
            return None
        chain_type, chain_id = matches[0]
        return chain_type.upper(), chain_id

    @classmethod
    def _prefer_chain_source_record(cls, current: dict | None, candidate: dict) -> dict:
        if current is None:
            return candidate
        current_seq_len = max(
            len(cls._normalize_aa_sequence(current.get("vh_sequence_aa", ""))),
            len(cls._normalize_aa_sequence(current.get("vl_sequence_aa", ""))),
            len(cls._normalize_aa_sequence(current.get("CDRH3_Sequence", ""))),
        )
        candidate_seq_len = max(
            len(cls._normalize_aa_sequence(candidate.get("vh_sequence_aa", ""))),
            len(cls._normalize_aa_sequence(candidate.get("vl_sequence_aa", ""))),
            len(cls._normalize_aa_sequence(candidate.get("CDRH3_Sequence", ""))),
        )
        if candidate_seq_len > current_seq_len:
            return candidate
        return current

    @classmethod
    def _propagate_chain_variant_combinations(cls, skeleton: dict, paper_id: str) -> dict:
        antibodies = skeleton.get(paper_id, {}).get("antibodies", [])
        if not antibodies:
            return {"filled_fields": 0, "variants_filled": 0, "derived_cdrh3": 0}

        heavy_by_id: dict[str, dict] = {}
        light_by_id: dict[str, dict] = {}
        for ab in antibodies:
            name = (ab.get("Antibody_Name") or "").strip()
            token = cls._extract_single_chain_token(name)
            if not token:
                continue
            chain_type, chain_id = token
            if chain_type == "H":
                if (
                    cls._looks_like_full_variable_sequence(ab.get("vh_sequence_aa", ""))
                    or cls._normalize_aa_sequence(ab.get("CDRH3_Sequence", ""))
                ):
                    heavy_by_id[chain_id] = cls._prefer_chain_source_record(heavy_by_id.get(chain_id), ab)
            elif chain_type == "L":
                if cls._looks_like_full_variable_sequence(ab.get("vl_sequence_aa", "")):
                    light_by_id[chain_id] = cls._prefer_chain_source_record(light_by_id.get(chain_id), ab)

        filled_fields = 0
        variants_filled = 0
        derived_cdrh3 = 0

        for ab in antibodies:
            combo = cls._extract_chain_combo_tokens(ab.get("Antibody_Name", ""))
            if not combo:
                continue
            heavy_id, light_id = combo
            heavy_record = heavy_by_id.get(heavy_id)
            light_record = light_by_id.get(light_id)
            if not heavy_record and not light_record:
                continue

            filled_for_variant = False

            if heavy_record:
                vh = cls._normalize_aa_sequence(heavy_record.get("vh_sequence_aa", ""))
                if (
                    cls._looks_like_full_variable_sequence(vh)
                    and cls._sequence_matches_chain_field("vh_sequence_aa", vh)
                    and cls._is_empty_value(ab.get("vh_sequence_aa"))
                ):
                    ab["vh_sequence_aa"] = vh
                    cls._set_field_source(
                        ab,
                        "vh_sequence_aa",
                        {
                            **cls._build_record_field_source(
                                heavy_record,
                                note="Filled from heavy-chain variant record matching the HxLy naming pattern.",
                                from_antibody=heavy_record.get("Antibody_Name", ""),
                            ),
                            "source_type": "combined_chain_variant",
                            "source_label": f"Combined from {heavy_record.get('Antibody_Name', '')}",
                            "from_antibody": heavy_record.get("Antibody_Name", ""),
                            "inherited_from_field": "vh_sequence_aa",
                        },
                    )
                    filled_fields += 1
                    filled_for_variant = True

                heavy_cdrh3 = cls._normalize_aa_sequence(heavy_record.get("CDRH3_Sequence", ""))
                if not heavy_cdrh3 and vh and cls._sequence_matches_chain_field("vh_sequence_aa", vh):
                    heavy_cdrh3 = APIClient.extract_cdrh3_from_variable_region(vh) or ""
                    if heavy_cdrh3:
                        derived_cdrh3 += 1
                if heavy_cdrh3 and cls._is_empty_value(ab.get("CDRH3_Sequence")):
                    ab["CDRH3_Sequence"] = heavy_cdrh3
                    cls._set_field_source(
                        ab,
                        "CDRH3_Sequence",
                        {
                            **cls._build_record_field_source(
                                heavy_record,
                                note="Filled from heavy-chain variant record matching the HxLy naming pattern.",
                                from_antibody=heavy_record.get("Antibody_Name", ""),
                            ),
                            "source_type": "combined_chain_variant",
                            "source_label": f"Combined from {heavy_record.get('Antibody_Name', '')}",
                            "from_antibody": heavy_record.get("Antibody_Name", ""),
                            "inherited_from_field": "CDRH3_Sequence",
                        },
                    )
                    filled_fields += 1
                    filled_for_variant = True

            if light_record:
                vl = cls._normalize_aa_sequence(light_record.get("vl_sequence_aa", ""))
                if (
                    cls._looks_like_full_variable_sequence(vl)
                    and cls._sequence_matches_chain_field("vl_sequence_aa", vl)
                    and cls._is_empty_value(ab.get("vl_sequence_aa"))
                ):
                    ab["vl_sequence_aa"] = vl
                    cls._set_field_source(
                        ab,
                        "vl_sequence_aa",
                        {
                            **cls._build_record_field_source(
                                light_record,
                                note="Filled from light-chain variant record matching the HxLy naming pattern.",
                                from_antibody=light_record.get("Antibody_Name", ""),
                            ),
                            "source_type": "combined_chain_variant",
                            "source_label": f"Combined from {light_record.get('Antibody_Name', '')}",
                            "from_antibody": light_record.get("Antibody_Name", ""),
                            "inherited_from_field": "vl_sequence_aa",
                        },
                    )
                    filled_fields += 1
                    filled_for_variant = True

            if filled_for_variant:
                variants_filled += 1

        skeleton[paper_id]["antibodies"] = antibodies
        return {
            "filled_fields": filled_fields,
            "variants_filled": variants_filled,
            "derived_cdrh3": derived_cdrh3,
        }

    @classmethod
    def _propagate_identical_variant_chains(cls, skeleton: dict, paper_id: str, md_text: str) -> dict:
        antibodies = skeleton.get(paper_id, {}).get("antibodies", [])
        if not antibodies or not md_text:
            return {"filled_fields": 0, "pairs_applied": 0, "derived_cdrh3": 0}

        available_names = sorted(
            {
                (ab.get("Antibody_Name") or "").strip()
                for ab in antibodies
                if (ab.get("Antibody_Name") or "").strip()
            }
        )
        by_name = {}
        for idx, ab in enumerate(antibodies):
            name = (ab.get("Antibody_Name") or "").strip()
            if name:
                by_name.setdefault(name, []).append(idx)

        filled_fields = 0
        pairs_applied = 0
        derived_cdrh3 = 0

        for child_name in available_names:
            parent_names = cls._candidate_parent_names(child_name, available_names)
            if not parent_names:
                continue

            for parent_name in parent_names:
                parent_record = cls._select_best_parent_record(antibodies, parent_name)
                if not parent_record:
                    continue

                evidence_by_field = {}
                for field in ("vh_sequence_aa", "vl_sequence_aa"):
                    parent_value = cls._normalize_aa_sequence(parent_record.get(field, ""))
                    if not cls._looks_like_full_variable_sequence(parent_value):
                        continue
                    if not any(cls._is_empty_value(antibodies[idx].get(field)) for idx in by_name.get(child_name, [])):
                        continue
                    evidence = cls._find_chain_identity_evidence(md_text, child_name, parent_name, field)
                    if evidence:
                        evidence_by_field[field] = evidence

                if not evidence_by_field:
                    continue

                applied_for_pair = False
                for idx in by_name.get(child_name, []):
                    child = antibodies[idx]
                    for field, evidence in evidence_by_field.items():
                        if not cls._is_empty_value(child.get(field)):
                            continue
                        value = cls._normalize_aa_sequence(parent_record.get(field, ""))
                        if not cls._looks_like_full_variable_sequence(value):
                            continue
                        if not cls._sequence_matches_chain_field(field, value):
                            continue
                        child[field] = value
                        cls._append_sequence_inheritance(
                            child,
                            field=field,
                            parent_name=parent_name,
                            evidence=evidence,
                        )
                        parent_source = {}
                        if isinstance(parent_record.get("field_sources"), dict):
                            parent_source = copy.deepcopy(parent_record["field_sources"].get(field, {}))
                        cls._set_field_source(
                            child,
                            field,
                            {
                                **parent_source,
                                "source_type": "inherited_from_parent",
                                "source_label": f"Inherited from {parent_name}",
                                "from_antibody": parent_name,
                                "inherited_from_field": field,
                                "quote": evidence,
                                "note": "Inherited from parent antibody because the paper states this chain is identical or unchanged.",
                            },
                        )
                        filled_fields += 1
                        applied_for_pair = True
                        if field == "vh_sequence_aa" and cls._is_empty_value(child.get("CDRH3_Sequence")):
                            cdrh3 = APIClient.extract_cdrh3_from_variable_region(value)
                            if cdrh3:
                                child["CDRH3_Sequence"] = cdrh3
                                inherited_source = {}
                                if isinstance(child.get("field_sources"), dict):
                                    inherited_source = copy.deepcopy(child["field_sources"].get("vh_sequence_aa", {}))
                                cls._set_field_source(
                                    child,
                                    "CDRH3_Sequence",
                                    {
                                        **inherited_source,
                                        "source_type": "derived_from_vh",
                                        "source_label": f"Derived from inherited VH of {parent_name}",
                                        "from_antibody": parent_name,
                                        "inherited_from_field": "vh_sequence_aa",
                                        "quote": evidence,
                                        "note": "Derived from inherited VH sequence.",
                                    },
                                )
                                filled_fields += 1
                                derived_cdrh3 += 1
                    if applied_for_pair:
                        child.setdefault("_variant_parent", parent_name)

                if applied_for_pair:
                    pairs_applied += 1
                    break

        skeleton[paper_id]["antibodies"] = antibodies
        return {
            "filled_fields": filled_fields,
            "pairs_applied": pairs_applied,
            "derived_cdrh3": derived_cdrh3,
        }

    def _merge_extractions(self, skeleton: dict, paper_id: str, extract_results: list) -> tuple[dict, dict]:
        """Merge extraction results into skeleton by antibody name matching"""
        antibodies = skeleton.get(paper_id, {}).get("antibodies", [])
        if not antibodies:
            return skeleton, {"matched_antibodies": 0, "filled_fields": 0, "records_seen": 0}

        # Build name index
        name_idx = {}
        for i, ab in enumerate(antibodies):
            name = (ab.get("Antibody_Name") or "").lower().strip()
            if name:
                name_idx.setdefault(name, []).append(i)

        matched_antibodies = set()
        filled_fields = 0
        records_seen = 0

        for result in extract_results:
            data = result.data
            # Merge table records
            for record in data.get("table_records", []):
                records_seen += 1
                mab = (record.get("mAb") or record.get("Antibody_Name") or "").lower().strip()
                if mab and mab not in name_idx and self._record_supports_new_antibody(record):
                    shell = self._build_discovered_antibody_shell(antibodies, paper_id, record)
                    antibodies.append(shell)
                    name_idx[mab] = [len(antibodies) - 1]
                if mab in name_idx:
                    matched_antibodies.add(mab)
                    primary_idx = name_idx[mab][0]
                    ab = antibodies[primary_idx]
                    is_new_shell = (
                        not ab.get("CDRH3_Sequence")
                        and not ab.get("vh_sequence_aa")
                        and not ab.get("vl_sequence_aa")
                        and not ab.get("Binding_Kinetics_KD")
                    )
                    filled_fields += self._apply_record_to_antibody(
                        ab,
                        record,
                        fill_only=not is_new_shell,
                    )

        filled_fields += self._hydrate_sequence_fields_from_hints(antibodies)
        filled_fields += self._synchronize_entity_sequence_fields(antibodies)

        skeleton[paper_id]["antibodies"] = antibodies
        return skeleton, {
            "matched_antibodies": len(matched_antibodies),
            "filled_fields": filled_fields,
            "records_seen": records_seen,
        }

    def _print_scan_summary(self, data):
        t = data["tables"]
        cdr3 = data["cdr3_sequences"]
        print(f"  PDB={len(data['pdb_ids'])}, GenBank={len(data['genbank']['likely_genbank'])}"
              f" (nuc={len(data['genbank'].get('likely_nucleotide', []))},"
              f" protein={len(data['genbank'].get('likely_protein', []))}), "
              f"Germline={len(data['germline_genes'].get('IMGT_V_genes', []))}, "
              f"CDR3_H={len(cdr3['CDRH3_candidates'])}, CDR3_L={len(cdr3['CDRL3_candidates'])}, "
              f"Tables={t['html_table_count']}H+{t['markdown_table_count']}M")
        for r in data["routing_suggestions"]:
            print(f"  → {r}")

    def _print_validation_summary(self, data):
        s = data["summary"]
        print(f"  {s['total_antibodies']} antibodies: "
              f"pass={s['pass']} warn={s['warn']} fail={s['fail']} skip={s['skip']} "
              f"→ {s['overall']}")
        if data["duplicates"]:
            print(f"  + {len(data['duplicates'])} duplicate sequences")

    def _print_paper_focus_summary(self, data):
        paper_type = "; ".join(data.get("paper_type") or ["unknown"])
        difficulty_flags = data.get("difficulty_flags") or []
        priority_names = data.get("priority_antibody_names") or []
        print(f"  Profile={paper_type}")
        if difficulty_flags:
            print(f"  Difficulty flags: {', '.join(difficulty_flags)}")
        if priority_names:
            print(f"  Priority names: {', '.join(priority_names[:5])}")
