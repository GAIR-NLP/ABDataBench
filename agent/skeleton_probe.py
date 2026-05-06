#!/usr/bin/env python3
"""Minimal one-shot probe for Phase 2 skeleton generation."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import httpx

from config import Config


CONTINUATION_PROMPT = """The previous assistant message contains the beginning of a JSON object, but it was cut off before completion.
Continue from exactly the next character after the existing text.

Rules:
- Do not repeat any previous text.
- Do not restart the JSON object.
- Do not add markdown fences or commentary.
- Output only the remaining raw JSON suffix needed to complete the same JSON object.
"""


def build_auth_header(api_key: str, use_bearer_auth: bool) -> str:
    if use_bearer_auth and not api_key.startswith("Bearer "):
        return f"Bearer {api_key}"
    return api_key


def load_prompt_texts(agent_dir: Path) -> tuple[str, str]:
    prompt_dir = agent_dir / "prompts"
    system = (prompt_dir / "skeleton_system.txt").read_text(encoding="utf-8")
    user = (prompt_dir / "skeleton_user.txt").read_text(encoding="utf-8")
    return system, user


def build_user_prompt(
    user_template: str,
    regex_hints_text: str,
    paper_id: str,
    markdown_text: str,
) -> str:
    return user_template.format(
        REGEX_HINTS=regex_hints_text,
        PAPER_ID=paper_id,
        DOCUMENT_TEXT=markdown_text,
    )


def infer_paper_id(doc_path: Path) -> str:
    return doc_path.parent.name


def load_regex_hints(doc_path: Path) -> str:
    regex_path = doc_path.with_name("regex_hints.json")
    if not regex_path.exists():
        return "[Regex Hints]:\n- None found"
    data = json.loads(regex_path.read_text(encoding="utf-8"))
    return data.get("regex_hints_text") or "[Regex Hints]:\n- None found"


def make_payload(
    model: str,
    system_prompt: str,
    messages: list[dict[str, str]],
    max_tokens: int,
    temperature: float,
    enable_thinking: bool,
    response_format_json: bool,
) -> dict:
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system_prompt}, *messages],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "chat_template_kwargs": {"enable_thinking": enable_thinking},
    }
    if response_format_json:
        payload["response_format"] = {"type": "json_object"}
    return payload


def build_initial_messages(user_prompt: str) -> list[dict[str, str]]:
    return [{"role": "user", "content": user_prompt}]


def build_continuation_messages(
    user_prompt: str,
    combined_content: str,
) -> list[dict[str, str]]:
    return [
        {"role": "user", "content": user_prompt},
        {"role": "assistant", "content": combined_content},
        {"role": "user", "content": CONTINUATION_PROMPT},
    ]


def artifact_path(output_prefix: Path, suffix: str) -> Path:
    return output_prefix.parent / f"{output_prefix.name}.{suffix}"


def write_json(path: Path, data: dict | list) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_response_payload(response: httpx.Response) -> tuple[dict | None, dict]:
    result_meta = {"http_status": response.status_code}
    data = response.json()
    choice = (data.get("choices") or [{}])[0]
    usage = data.get("usage") or {}
    content = ((choice.get("message") or {}).get("content")) or ""
    result_meta.update(
        {
            "response_model": data.get("model"),
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
            "finish_reason": choice.get("finish_reason"),
            "response_chars": len(content),
            "content": content,
        }
    )
    return data, result_meta


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe the skeleton LLM call directly.")
    parser.add_argument(
        "--doc",
        default=os.getenv("SKELETON_PROBE_DOC"),
        help="Path to reduced_text.md; defaults to SKELETON_PROBE_DOC",
    )
    parser.add_argument(
        "--paper-id",
        default=None,
        help="Override paper id; defaults to parent directory name of --doc",
    )
    parser.add_argument(
        "--max-input-chars",
        type=int,
        default=None,
        help="Optional hard cap on input chars before request",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help="Optional override for max output tokens",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=None,
        help="Optional override for HTTP timeout seconds",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Optional model override",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.1,
        help="Sampling temperature",
    )
    parser.add_argument(
        "--output-prefix",
        default=None,
        help="Output file prefix; defaults to <doc_dir>/skeleton_probe",
    )
    parser.add_argument(
        "--continue-on-length",
        action="store_true",
        help="If the first response is truncated, send continuation requests and stitch them.",
    )
    parser.add_argument(
        "--max-continuations",
        type=int,
        default=3,
        help="Maximum number of continuation requests after the first call.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = Config()

    if not args.doc:
        print("Document path is required. Pass --doc or set SKELETON_PROBE_DOC.", file=sys.stderr)
        return 2

    doc_path = Path(args.doc).resolve()
    if not doc_path.exists():
        print(f"Document not found: {doc_path}", file=sys.stderr)
        return 1

    agent_dir = Path(__file__).resolve().parent
    system_prompt, user_template = load_prompt_texts(agent_dir)

    paper_id = args.paper_id or infer_paper_id(doc_path)
    markdown_text = doc_path.read_text(encoding="utf-8")
    regex_hints_text = load_regex_hints(doc_path)

    max_input_chars = args.max_input_chars or config.skeleton_max_input_chars
    if len(markdown_text) > max_input_chars:
        markdown_text = markdown_text[:max_input_chars] + "\n\n[... truncated ...]"

    user_prompt = build_user_prompt(
        user_template=user_template,
        regex_hints_text=regex_hints_text,
        paper_id=paper_id,
        markdown_text=markdown_text,
    )

    model = args.model or config.llm_model
    max_tokens = args.max_tokens or config.llm_max_tokens
    timeout = args.timeout or config.llm_timeout

    headers = {
        "Authorization": build_auth_header(config.llm_api_key, config.llm_use_bearer_auth),
        "Content-Type": "application/json",
    }

    output_prefix = (
        Path(args.output_prefix).resolve()
        if args.output_prefix
        else doc_path.parent / "skeleton_probe"
    )
    output_prefix.parent.mkdir(parents=True, exist_ok=True)

    request_meta = {
        "paper_id": paper_id,
        "doc_path": str(doc_path),
        "model": model,
        "api_base": config.llm_api_base,
        "timeout": timeout,
        "input_chars": len(markdown_text),
        "regex_hint_chars": len(regex_hints_text),
        "system_chars": len(system_prompt),
        "user_chars": len(user_prompt),
        "max_tokens": max_tokens,
        "temperature": args.temperature,
        "continue_on_length": args.continue_on_length,
        "max_continuations": args.max_continuations,
    }
    write_json(artifact_path(output_prefix, "request.json"), request_meta)

    print(json.dumps(request_meta, ensure_ascii=False, indent=2))
    try:
        with httpx.Client(timeout=timeout, trust_env=not config.llm_disable_proxy) as client:
            attempts: list[dict] = []
            combined_content = ""
            combined_parse_ok = False
            last_response_success = False

            for attempt_idx in range(args.max_continuations + 1):
                is_initial = attempt_idx == 0
                messages = (
                    build_initial_messages(user_prompt)
                    if is_initial
                    else build_continuation_messages(user_prompt, combined_content)
                )
                payload = make_payload(
                    model=model,
                    system_prompt=system_prompt,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=args.temperature,
                    enable_thinking=config.llm_enable_thinking,
                    response_format_json=is_initial,
                )
                start = time.time()
                response = client.post(
                    f"{config.llm_api_base.rstrip('/')}/v1/chat/completions",
                    headers=headers,
                    json=payload,
                )
                elapsed = round(time.time() - start, 2)
                last_response_success = response.is_success

                raw_suffix = "raw.txt" if is_initial else f"attempt_{attempt_idx + 1}.raw.txt"
                response_suffix = (
                    "response.json" if is_initial else f"attempt_{attempt_idx + 1}.response.json"
                )
                artifact_path(output_prefix, raw_suffix).write_text(
                    response.text,
                    encoding="utf-8",
                )

                attempt_meta = {
                    "attempt": attempt_idx + 1,
                    "mode": "initial" if is_initial else "continuation",
                    "elapsed_seconds": elapsed,
                    "http_status": response.status_code,
                }

                try:
                    data, parsed_meta = parse_response_payload(response)
                    write_json(artifact_path(output_prefix, response_suffix), data)
                    attempt_meta.update(parsed_meta)
                    content = parsed_meta["content"]
                    combined_content += content
                    attempt_meta["combined_chars_after_append"] = len(combined_content)
                except Exception as exc:
                    attempt_meta["json_decode_error"] = str(exc)
                    attempts.append(attempt_meta)
                    break

                attempt_meta.pop("content", None)
                attempts.append(attempt_meta)
                artifact_path(output_prefix, "combined.txt").write_text(
                    combined_content,
                    encoding="utf-8",
                )

                try:
                    parsed_combined = json.loads(combined_content)
                    combined_parse_ok = True
                    write_json(artifact_path(output_prefix, "parsed.json"), parsed_combined)
                    break
                except Exception:
                    combined_parse_ok = False

                if not args.continue_on_length:
                    break
                if attempt_meta.get("finish_reason") != "length":
                    break
                if attempt_idx >= args.max_continuations:
                    break
    except Exception as exc:
        error_meta = {
            **request_meta,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
        write_json(artifact_path(output_prefix, "error.json"), error_meta)
        print(json.dumps(error_meta, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2

    result_meta = {
        **request_meta,
        "attempt_count": len(attempts),
        "combined_chars": len(combined_content),
        "combined_json_parse_ok": combined_parse_ok,
        "attempts": attempts,
    }

    write_json(artifact_path(output_prefix, "meta.json"), result_meta)
    print(json.dumps(result_meta, ensure_ascii=False, indent=2))
    if combined_parse_ok:
        return 0
    return 4 if last_response_success else 3


if __name__ == "__main__":
    raise SystemExit(main())
