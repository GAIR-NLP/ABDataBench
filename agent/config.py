"""Global configuration."""

from dataclasses import dataclass, field
from typing import Any, Optional
import os


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_str(name: str, default: str) -> str:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value


@dataclass
class Config:
    # LLM
    llm_api_base: str = "https://api.opensii.ai"
    llm_api_key: str = ""
    llm_model: str = "gzy/claude-4.6-sonnet"
    llm_review_model: str = ""
    llm_temperature: float = 0.1
    llm_max_tokens: int = 12_288
    skeleton_max_input_chars: int = 200_000
    skeleton_max_continuations: int = 10
    skeleton_page_size: int = 8
    skeleton_max_pages: int = 10
    skeleton_max_antibodies: int = 30
    enable_text_reduce: bool = True
    text_reduce_min_chars: int = 200_000
    text_reduce_chunk_chars: int = 4_000
    text_reduce_max_tokens: int = 4_000
    text_reduce_temperature: float = 0.0
    text_reduce_model: str = ""
    text_reduce_concurrency: int = 10
    enable_ocr_repair: bool = True
    ocr_repair_model: str = ""
    ocr_repair_min_chars: int = 2_000
    ocr_repair_chunk_chars: int = 12_000
    ocr_repair_max_tokens: int = 6_000
    ocr_repair_temperature: float = 0.0
    ocr_repair_concurrency: int = 6
    enable_hard_paper_focus_analyzer: bool = True
    hard_paper_focus_model: str = ""
    hard_paper_focus_max_tokens: int = 3000
    hard_paper_focus_temperature: float = 0.0
    hard_paper_focus_max_input_chars: int = 60_000
    llm_timeout: int = 2400
    llm_use_bearer_auth: bool = True
    llm_disable_proxy: bool = True
    llm_enable_thinking: bool = False
    mock_llm: bool = False
    mock_llm_latency_ms: int = 700
    mock_llm_jitter_ms: int = 250

    # VLM (Vision-Language Model)
    vlm_api_base: str = ""
    vlm_api_key: str = ""
    vlm_model: str = "gzy/gemini-3.1-pro-thinking"
    vlm_concurrency: int = 10
    vlm_timeout: int = 1200
    vlm_retry_count: int = 5
    vlm_use_bearer_auth: bool = True
    vlm_disable_proxy: bool = True
    enable_image_extract: bool = True
    vlm_min_image_pixels: int = 10000
    vlm_max_images_per_paper: int = 40
    vlm_top_k_images: int = 30

    # PDB post-process
    enable_pdb_llm_postprocess: bool = True
    pdb_llm_postprocess_model: str = ""
    pdb_llm_postprocess_max_tokens: int = 3000
    pdb_llm_postprocess_temperature: float = 0.0
    pdb_llm_postprocess_max_fasta_entries: int = 8

    # Sequence Image Tool (Responses API)
    enable_sequence_image_tool: bool = True
    sequence_vlm_api_base: str = ""
    sequence_vlm_api_key: str = ""
    sequence_vlm_model: str = "gzy/gemini-3.1-pro-thinking"
    sequence_vlm_timeout: int = 2400
    sequence_vlm_concurrency: int = 10
    sequence_vlm_retry_count: int = 5
    sequence_vlm_max_images: int = 30
    sequence_vlm_top_k_images: int = 30
    sequence_vlm_max_output_tokens: int = 20000

    # External API
    ncbi_api_key: Optional[str] = None
    ncbi_email: str = ""

    # Pipeline
    max_retries: int = 2
    parallel_extract: bool = True
    enable_supplement: bool = True

    # Output
    output_dir: str = "./output"
    save_intermediate: bool = True
    verbose: bool = True

    # Validation
    strict_validation: bool = False

    # Batch
    llm_concurrency: int = 50
    llm_rpm: int = 500
    llm_tpm: int = 2_000_000
    papers_per_worker: int = 30
    num_workers: int = 8
    max_paper_retries: int = 2
    timeout_per_paper: int = 8400
    skip_on_error: bool = True
    checkpoint_interval: int = 100
    result_backend: str = "sqlite"
    trace_enabled: bool = False
    trace_recorder: Any = field(default=None, repr=False)

    def __post_init__(self):
        self.llm_api_key = _env_str("LLM_API_KEY", self.llm_api_key)
        self.llm_api_base = _env_str("LLM_API_BASE", self.llm_api_base)
        self.llm_model = _env_str("LLM_MODEL", self.llm_model)
        self.llm_review_model = _env_str(
            "LLM_REVIEW_MODEL", self.llm_review_model or self.llm_model
        )
        self.llm_max_tokens = int(os.environ.get("LLM_MAX_TOKENS", self.llm_max_tokens))
        self.skeleton_max_input_chars = int(
            os.environ.get("SKELETON_MAX_INPUT_CHARS", self.skeleton_max_input_chars)
        )
        self.skeleton_max_continuations = int(
            os.environ.get("SKELETON_MAX_CONTINUATIONS", self.skeleton_max_continuations)
        )
        self.skeleton_page_size = int(
            os.environ.get("SKELETON_PAGE_SIZE", self.skeleton_page_size)
        )
        self.skeleton_max_pages = int(
            os.environ.get("SKELETON_MAX_PAGES", self.skeleton_max_pages)
        )
        self.skeleton_max_antibodies = int(
            os.environ.get("SKELETON_MAX_ANTIBODIES", self.skeleton_max_antibodies)
        )
        self.enable_text_reduce = _env_bool("ENABLE_TEXT_REDUCE", self.enable_text_reduce)
        self.text_reduce_min_chars = int(
            os.environ.get("TEXT_REDUCE_MIN_CHARS", self.text_reduce_min_chars)
        )
        self.text_reduce_chunk_chars = int(
            os.environ.get("TEXT_REDUCE_CHUNK_CHARS", self.text_reduce_chunk_chars)
        )
        self.text_reduce_max_tokens = int(
            os.environ.get("TEXT_REDUCE_MAX_TOKENS", self.text_reduce_max_tokens)
        )
        self.text_reduce_temperature = float(
            os.environ.get("TEXT_REDUCE_TEMPERATURE", self.text_reduce_temperature)
        )
        self.text_reduce_model = _env_str("TEXT_REDUCE_MODEL", self.text_reduce_model)
        self.text_reduce_concurrency = int(
            os.environ.get("TEXT_REDUCE_CONCURRENCY", self.text_reduce_concurrency)
        )
        self.enable_ocr_repair = _env_bool("ENABLE_OCR_REPAIR", self.enable_ocr_repair)
        self.ocr_repair_model = _env_str("OCR_REPAIR_MODEL", self.ocr_repair_model)
        self.ocr_repair_min_chars = int(
            os.environ.get("OCR_REPAIR_MIN_CHARS", self.ocr_repair_min_chars)
        )
        self.ocr_repair_chunk_chars = int(
            os.environ.get("OCR_REPAIR_CHUNK_CHARS", self.ocr_repair_chunk_chars)
        )
        self.ocr_repair_max_tokens = int(
            os.environ.get("OCR_REPAIR_MAX_TOKENS", self.ocr_repair_max_tokens)
        )
        self.ocr_repair_temperature = float(
            os.environ.get("OCR_REPAIR_TEMPERATURE", self.ocr_repair_temperature)
        )
        self.ocr_repair_concurrency = int(
            os.environ.get("OCR_REPAIR_CONCURRENCY", self.ocr_repair_concurrency)
        )
        self.enable_hard_paper_focus_analyzer = _env_bool(
            "ENABLE_HARD_PAPER_FOCUS_ANALYZER",
            self.enable_hard_paper_focus_analyzer,
        )
        self.hard_paper_focus_model = _env_str(
            "HARD_PAPER_FOCUS_MODEL", self.hard_paper_focus_model
        )
        self.hard_paper_focus_max_tokens = int(
            os.environ.get(
                "HARD_PAPER_FOCUS_MAX_TOKENS",
                self.hard_paper_focus_max_tokens,
            )
        )
        self.hard_paper_focus_temperature = float(
            os.environ.get(
                "HARD_PAPER_FOCUS_TEMPERATURE",
                self.hard_paper_focus_temperature,
            )
        )
        self.hard_paper_focus_max_input_chars = int(
            os.environ.get(
                "HARD_PAPER_FOCUS_MAX_INPUT_CHARS",
                self.hard_paper_focus_max_input_chars,
            )
        )
        self.llm_timeout = int(os.environ.get("LLM_TIMEOUT", self.llm_timeout))
        self.llm_use_bearer_auth = _env_bool("LLM_USE_BEARER_AUTH", self.llm_use_bearer_auth)
        self.llm_disable_proxy = _env_bool("LLM_DISABLE_PROXY", self.llm_disable_proxy)
        self.llm_enable_thinking = _env_bool("LLM_ENABLE_THINKING", self.llm_enable_thinking)
        self.vlm_api_key = _env_str("VLM_API_KEY", self.vlm_api_key or self.llm_api_key)
        self.vlm_api_base = _env_str("VLM_API_BASE", self.vlm_api_base or self.llm_api_base)
        self.vlm_model = _env_str("VLM_MODEL", self.vlm_model)
        self.vlm_concurrency = int(os.environ.get("VLM_CONCURRENCY", self.vlm_concurrency))
        self.vlm_timeout = int(os.environ.get("VLM_TIMEOUT", self.vlm_timeout))
        self.vlm_retry_count = int(os.environ.get("VLM_RETRY_COUNT", self.vlm_retry_count))
        self.vlm_use_bearer_auth = _env_bool("VLM_USE_BEARER_AUTH", self.vlm_use_bearer_auth)
        self.vlm_disable_proxy = _env_bool("VLM_DISABLE_PROXY", self.vlm_disable_proxy)
        self.vlm_top_k_images = int(
            os.environ.get("VLM_TOP_K_IMAGES", self.vlm_top_k_images)
        )
        self.enable_pdb_llm_postprocess = _env_bool(
            "ENABLE_PDB_LLM_POSTPROCESS", self.enable_pdb_llm_postprocess
        )
        self.pdb_llm_postprocess_model = _env_str(
            "PDB_LLM_POSTPROCESS_MODEL", self.pdb_llm_postprocess_model
        )
        self.pdb_llm_postprocess_max_tokens = int(
            os.environ.get("PDB_LLM_POSTPROCESS_MAX_TOKENS", self.pdb_llm_postprocess_max_tokens)
        )
        self.pdb_llm_postprocess_temperature = float(
            os.environ.get(
                "PDB_LLM_POSTPROCESS_TEMPERATURE",
                self.pdb_llm_postprocess_temperature,
            )
        )
        self.pdb_llm_postprocess_max_fasta_entries = int(
            os.environ.get(
                "PDB_LLM_POSTPROCESS_MAX_FASTA_ENTRIES",
                self.pdb_llm_postprocess_max_fasta_entries,
            )
        )
        self.sequence_vlm_api_base = _env_str(
            "SEQUENCE_VLM_API_BASE",
            self.sequence_vlm_api_base or self.llm_api_base,
        )
        self.sequence_vlm_api_key = _env_str(
            "SEQUENCE_VLM_API_KEY",
            self.sequence_vlm_api_key or self.llm_api_key,
        )
        self.sequence_vlm_model = _env_str(
            "SEQUENCE_VLM_MODEL", self.sequence_vlm_model
        )
        self.sequence_vlm_timeout = int(
            os.environ.get("SEQUENCE_VLM_TIMEOUT", self.sequence_vlm_timeout)
        )
        self.sequence_vlm_concurrency = int(
            os.environ.get("SEQUENCE_VLM_CONCURRENCY", self.sequence_vlm_concurrency)
        )
        self.sequence_vlm_retry_count = int(
            os.environ.get("SEQUENCE_VLM_RETRY_COUNT", self.sequence_vlm_retry_count)
        )
        self.sequence_vlm_max_images = int(
            os.environ.get("SEQUENCE_VLM_MAX_IMAGES", self.sequence_vlm_max_images)
        )
        self.sequence_vlm_top_k_images = int(
            os.environ.get("SEQUENCE_VLM_TOP_K_IMAGES", self.sequence_vlm_top_k_images)
        )
        self.sequence_vlm_max_output_tokens = int(
            os.environ.get("SEQUENCE_VLM_MAX_OUTPUT_TOKENS", self.sequence_vlm_max_output_tokens)
        )
        self.ncbi_email = _env_str("NCBI_EMAIL", self.ncbi_email)
        self.ncbi_api_key = _env_str("NCBI_API_KEY", self.ncbi_api_key)
        self.llm_concurrency = int(
            os.environ.get("LLM_CONCURRENCY", self.llm_concurrency)
        )
        self.llm_rpm = int(os.environ.get("LLM_RPM", self.llm_rpm))
        self.llm_tpm = int(os.environ.get("LLM_TPM", self.llm_tpm))
        self.papers_per_worker = int(
            os.environ.get("PAPERS_PER_WORKER", self.papers_per_worker)
        )
        self.num_workers = int(os.environ.get("NUM_WORKERS", self.num_workers))
        self.max_paper_retries = int(
            os.environ.get("MAX_PAPER_RETRIES", self.max_paper_retries)
        )
        self.timeout_per_paper = int(
            os.environ.get("TIMEOUT_PER_PAPER", self.timeout_per_paper)
        )
