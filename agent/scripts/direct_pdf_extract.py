#!/usr/bin/env python3
"""Directly extract structured antibody records from a PDF via a Responses-compatible API."""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from json import JSONDecoder
from pathlib import Path
from typing import Any

import httpx


SYSTEM_PROMPT = """You extract structured antibody information from scientific papers and patents.

Return exactly one JSON object and nothing else.
Do not use markdown fences.
Do not invent values that are not supported by the PDF.
Use null for unknown values.
Preserve numeric values and units exactly when available.
If multiple supported values belong in one field, join them with '; '.
The output must follow the requested schema exactly.
"""


def build_user_prompt(
    paper_id: str,
    *,
    page_size: int,
    seen_names: list[str],
) -> str:
    seen_text = ", ".join(seen_names) if seen_names else "None"
    return f"""Read the attached PDF and extract antibody records into this exact JSON shape:

{{
  "paper": {{
    "paper_id": "{paper_id}",
    "title": "document title",
    "antibodies": [
      {{
        "Master_ID": 1,
        "Antibody_Name": "string or null",
        "Antibody_Type": "string or null",
        "Antibody_Isotype": "string or null",
        "source": "string or null",
        "Target_Name": "string or null",
        "Target_Type": "string or null",
        "Cross_Reactivity": "string or null",
        "Epitope": "string or null",
        "Experiment": "string or null",
        "Binding_Kinetics_KD": "string or null",
        "Binding_Kinetics_kon": "string or null",
        "Binding_Kinetics_koff": "string or null",
        "Binding_EC50": "string or null",
        "Mechanism_of_Action": "string or null",
        "Structure": "string or null",
        "CDRH3_Sequence": "string or null",
        "vh_sequence_aa": "string or null",
        "vl_sequence_aa": "string or null",
        "In_Vivo_Half_Life": "string or null",
        "In_Vivo_Efficacy": "string or null",
        "Thermal_Stability_Tm": "string or null",
        "Reference_Source": "string or null",
        "Quantitative_Metric": "string or null"
      }}
    ]
  }}
}}

Extraction rules:
- Include only antibody-level records that the document actually characterizes.
- Exclude isolated VH/VL chain labels, germline names, template antibodies, purely control/reference entries, and chain-swap fragments unless the document clearly treats them as standalone antibodies.
- In patents, clone labels such as `Clone 1`, `Clone 15`, or named antibody clones count as valid antibody records when the PDF gives them sequence or assay data.
- `Antibody_Type` is format/class such as mAb, IgG, Fab, scFv, VHH, bispecific antibody.
- `Antibody_Isotype` is subtype such as human IgG1, human IgG4, mouse IgG2a.
- `Experiment` should be concise assay names only, for example SPR, BLI, ELISA, Flow Cytometry, Neutralization assay.
- `Binding_Kinetics_*`, `Binding_EC50`, `In_Vivo_Half_Life`, `Thermal_Stability_Tm`, and `Quantitative_Metric` must keep concrete values with units if present.
- `vh_sequence_aa`, `vl_sequence_aa`, and `CDRH3_Sequence` must be amino-acid sequences only. Do not put accession IDs or prose there.
- `Structure` should be compact, for example a PDB ID or short structure label.
- `Reference_Source` should be a compact citation for this document, using the patent or paper identity from the PDF.
- Number `Master_ID` from 1 in document order.
- Return at most {page_size} antibodies on this page.
- Do not repeat any antibody names already returned in earlier pages.
- Already returned antibody names: {seen_text}
- If all remaining antibody names are already excluded or no antibody records are present, return an empty `antibodies` array.

Return only the final JSON object.
"""


def encode_pdf(pdf_path: Path) -> str:
    return base64.b64encode(pdf_path.read_bytes()).decode("ascii")


def build_payload(
    *,
    model: str,
    paper_id: str,
    pdf_path: Path,
    max_output_tokens: int,
    page_size: int,
    seen_names: list[str],
) -> dict[str, Any]:
    return {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": SYSTEM_PROMPT}],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_file",
                        "filename": pdf_path.name,
                        "file_data": encode_pdf(pdf_path),
                    },
                    {
                        "type": "input_text",
                        "text": build_user_prompt(
                            paper_id,
                            page_size=page_size,
                            seen_names=seen_names,
                        ),
                    },
                ],
            },
        ],
        "temperature": 0.0,
        "max_output_tokens": max_output_tokens,
        "text": {"format": {"type": "text"}},
    }


def extract_output_text(response_json: dict[str, Any]) -> str:
    output_text = response_json.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text

    texts: list[str] = []
    for item in response_json.get("output", []) or []:
        for content in item.get("content", []) or []:
            text = content.get("text")
            if isinstance(text, str) and text.strip():
                texts.append(text)
    if texts:
        return "\n".join(texts)
    raise ValueError("No textual output found in API response")


def strip_code_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return cleaned


def parse_first_json(text: str) -> Any:
    decoder = JSONDecoder()
    stripped = strip_code_fences(text)

    for idx, ch in enumerate(stripped):
        if ch not in "{[":
            continue
        try:
            obj, end = decoder.raw_decode(stripped[idx:])
        except json.JSONDecodeError:
            continue
        tail = stripped[idx + end :].strip()
        if not tail:
            return obj
    raise ValueError("Could not parse a JSON object from model output")


def normalize_page_payload(parsed: Any, paper_id: str) -> dict[str, Any]:
    if not isinstance(parsed, dict):
        raise ValueError("Model output JSON is not an object")

    nested = parsed.get(paper_id)
    if isinstance(nested, dict) and "antibodies" in nested:
        return nested

    if "antibodies" in parsed:
        return parsed

    raise ValueError("Could not find `antibodies` in model output")


def merge_antibodies(existing: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> int:
    index = {}
    for pos, antibody in enumerate(existing):
        name = str(antibody.get("Antibody_Name") or "").strip()
        if name:
            index[name.casefold()] = pos

    added = 0
    for antibody in incoming:
        name = str(antibody.get("Antibody_Name") or "").strip()
        if not name:
            continue
        key = name.casefold()
        if key in index:
            continue
        existing.append(antibody)
        index[key] = len(existing) - 1
        added += 1
    return added


def post_response(
    *,
    api_base: str,
    api_key: str,
    payload: dict[str, Any],
    timeout: int,
) -> dict[str, Any]:
    url = api_base.rstrip("/") + "/v1/responses"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=timeout, trust_env=False) as client:
        response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()


def main() -> int:
    parser = argparse.ArgumentParser(description="Direct PDF extraction via Responses API")
    parser.add_argument("--pdf", required=True, help="Path to the input PDF")
    parser.add_argument("--output", required=True, help="Output JSON path")
    parser.add_argument("--raw-output", default=None, help="Optional raw API response JSON path")
    parser.add_argument(
        "--api-base",
        default=os.getenv("PDF_EXTRACT_API_BASE") or os.getenv("LLM_API_BASE", "https://api.opensii.ai"),
        help="Responses-compatible API base URL; defaults to PDF_EXTRACT_API_BASE or LLM_API_BASE",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("PDF_EXTRACT_API_KEY") or os.getenv("LLM_API_KEY") or os.getenv("VLM_API_KEY"),
        help="API key; defaults to PDF_EXTRACT_API_KEY, LLM_API_KEY, or VLM_API_KEY",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("PDF_EXTRACT_MODEL") or os.getenv("LLM_MODEL", "gzy/claude-4.6-sonnet"),
        help="Model name; defaults to PDF_EXTRACT_MODEL or LLM_MODEL",
    )
    parser.add_argument("--paper-id", default=None, help="Override paper_id")
    parser.add_argument("--max-output-tokens", type=int, default=24000)
    parser.add_argument("--timeout", type=int, default=3600)
    parser.add_argument("--page-size", type=int, default=4)
    parser.add_argument("--max-pages", type=int, default=20)
    args = parser.parse_args()

    if not args.api_key:
        print(
            "API key is required. Pass --api-key or set PDF_EXTRACT_API_KEY/LLM_API_KEY/VLM_API_KEY.",
            file=sys.stderr,
        )
        return 2

    pdf_path = Path(args.pdf).resolve()
    output_path = Path(args.output).resolve()
    raw_output_path = Path(args.raw_output).resolve() if args.raw_output else output_path.with_suffix(".raw.json")
    paper_id = args.paper_id or pdf_path.stem

    raw_output_path.parent.mkdir(parents=True, exist_ok=True)
    combined = {paper_id: {"paper_id": paper_id, "title": paper_id, "antibodies": []}}
    seen_names: list[str] = []
    raw_pages: list[dict[str, Any]] = []

    for page_index in range(1, args.max_pages + 1):
        payload = build_payload(
            model=args.model,
            paper_id=paper_id,
            pdf_path=pdf_path,
            max_output_tokens=args.max_output_tokens,
            page_size=args.page_size,
            seen_names=seen_names,
        )
        response_json = post_response(
            api_base=args.api_base,
            api_key=args.api_key,
            payload=payload,
            timeout=args.timeout,
        )
        raw_pages.append(response_json)

        output_text = extract_output_text(response_json)
        parsed = parse_first_json(output_text)
        paper = normalize_page_payload(parsed, paper_id)

        title = paper.get("title")
        if isinstance(title, str) and title.strip():
            combined[paper_id]["title"] = title.strip()

        page_antibodies = list(paper.get("antibodies") or [])
        added = merge_antibodies(combined[paper_id]["antibodies"], page_antibodies)
        seen_names = [
            str(ab.get("Antibody_Name") or "").strip()
            for ab in combined[paper_id]["antibodies"]
            if str(ab.get("Antibody_Name") or "").strip()
        ]

        if added == 0:
            break

    for idx, antibody in enumerate(combined[paper_id]["antibodies"], start=1):
        antibody["Master_ID"] = idx

    raw_output_path.write_text(
        json.dumps({"pages": raw_pages}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(combined, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(str(output_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
