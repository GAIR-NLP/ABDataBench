#!/usr/bin/env python3
"""Fetch VH/VL chain info from GenBank nucleotide accessions."""

import argparse
import json
import os
import sys


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tools.api_client import APIClient


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch VH/VL CDS translation info from GenBank accessions."
    )
    parser.add_argument("accessions", nargs="+", help="GenBank nucleotide accession(s)")
    parser.add_argument(
        "--chain",
        choices=["VH", "VL"],
        help="Only return the requested chain type.",
    )
    parser.add_argument(
        "--email",
        default=os.environ.get("NCBI_EMAIL", ""),
        help="NCBI email. Defaults to $NCBI_EMAIL.",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("NCBI_API_KEY", ""),
        help="NCBI API key. Defaults to $NCBI_API_KEY.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON instead of text.",
    )
    return parser


def format_chain_info(info: dict) -> str:
    lines = [
        f"accession: {info.get('accession', '')}",
        f"normalized_from: {info.get('normalized_from', '')}",
        f"chain_type: {info.get('chain_type', '')}",
        f"location: {info.get('location', '')}",
        f"product: {info.get('product', '')}",
        f"protein_id: {info.get('protein_id', '')}",
        f"translation: {info.get('translation', '')}",
    ]
    return "\n".join(lines)


def format_text_output(results: dict[str, list[dict] | dict | None], preferred_chain: str | None) -> str:
    blocks = []
    for accession, payload in results.items():
        if payload is None:
            if preferred_chain:
                blocks.append(f"{accession}\n  no {preferred_chain} chain found")
            else:
                blocks.append(f"{accession}\n  no CDS translation found")
            continue

        if isinstance(payload, dict) and payload.get("error"):
            blocks.append(f"{accession}\n  error: {payload['error']}")
            continue

        if isinstance(payload, dict):
            infos = [payload]
        else:
            infos = payload

        lines = [accession]
        for info in infos:
            formatted = format_chain_info(info).splitlines()
            lines.extend(f"  {line}" for line in formatted)
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def fetch_results(accessions: list[str], preferred_chain: str | None, email: str, api_key: str):
    client = APIClient(ncbi_email=email, ncbi_api_key=api_key or None)
    results = {}
    for accession in accessions:
        normalized = APIClient.normalize_accession(accession) or accession
        try:
            results[normalized] = client.fetch_genbank_chain_infos(accession, preferred_chain=preferred_chain)
        except Exception as exc:
            error_payload = {"accession": normalized, "error": str(exc)}
            if normalized != accession:
                error_payload["normalized_from"] = accession
            results[normalized] = error_payload
    return results


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    results = fetch_results(args.accessions, args.chain, args.email, args.api_key)
    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        print(format_text_output(results, args.chain))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
