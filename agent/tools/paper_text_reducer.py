"""Chunking and merge helpers for LLM-based paper reduction."""

from __future__ import annotations

import re


class PaperTextReducer:
    """Prepare long paper text for chunked LLM filtering and merge the results."""

    IMAGE_PATTERN = re.compile(r"!\[[^\]]*\]\(([^)]+)\)|\b(images/[^\s)]+)")

    def __init__(self, chunk_chars: int = 4_000):
        self.chunk_chars = chunk_chars

    def chunk_text(self, text: str) -> list[dict]:
        blocks = self._split_blocks(text)
        chunks: list[dict] = []
        current_blocks: list[str] = []
        current_chars = 0

        def flush_current() -> None:
            nonlocal current_blocks, current_chars
            if not current_blocks:
                return
            chunk_text = "\n\n".join(current_blocks).strip()
            chunks.append(
                {
                    "chunk_index": len(chunks) + 1,
                    "text": chunk_text,
                    "char_count": len(chunk_text),
                    "block_count": len(current_blocks),
                }
            )
            current_blocks = []
            current_chars = 0

        for block in blocks:
            block = block.strip()
            if not block:
                continue
            if len(block) > self.chunk_chars:
                flush_current()
                for piece in self._split_large_block(block):
                    chunks.append(
                        {
                            "chunk_index": len(chunks) + 1,
                            "text": piece,
                            "char_count": len(piece),
                            "block_count": 1,
                        }
                    )
                continue

            projected = current_chars + len(block) + (2 if current_blocks else 0)
            if current_blocks and projected > self.chunk_chars:
                flush_current()
            current_blocks.append(block)
            current_chars += len(block) + (2 if len(current_blocks) > 1 else 0)

        flush_current()
        if not chunks and text.strip():
            trimmed = text.strip()
            chunks.append(
                {
                    "chunk_index": 1,
                    "text": trimmed,
                    "char_count": len(trimmed),
                    "block_count": 1,
                }
            )
        return chunks

    def merge_filtered_chunks(self, original_text: str, chunk_results: list[dict], paper_id: str = "") -> dict:
        kept_parts: list[str] = []
        kept_chunks = 0
        dropped_chunks = 0
        failed_chunks = 0
        chunk_summaries = []

        for item in chunk_results:
            filtered_text = (item.get("filtered_text") or "").strip()
            keep = bool(filtered_text)
            if item.get("error"):
                failed_chunks += 1
            if keep:
                kept_chunks += 1
                kept_parts.append(filtered_text)
            else:
                dropped_chunks += 1
            chunk_summaries.append(
                {
                    "chunk_index": item.get("chunk_index"),
                    "original_chars": item.get("original_chars", 0),
                    "filtered_chars": len(filtered_text),
                    "kept": keep,
                    "evidence_types": item.get("evidence_types", []),
                    "notes": item.get("notes", ""),
                    "error": item.get("error"),
                }
            )

        reduced_text = "\n\n".join(part for part in kept_parts if part).strip()
        if not reduced_text:
            reduced_text = original_text.strip()

        image_manifest = self.build_image_manifest(reduced_text)
        reduced_chars = len(reduced_text)
        original_chars = len(original_text)
        return {
            "reduced_text": reduced_text,
            "meta": {
                "paper_id": paper_id,
                "chunk_chars": self.chunk_chars,
                "original_chars": original_chars,
                "reduced_chars": reduced_chars,
                "reduction_ratio": round(reduced_chars / max(original_chars, 1), 3),
                "total_chunks": len(chunk_results),
                "kept_chunks": kept_chunks,
                "dropped_chunks": dropped_chunks,
                "failed_chunks": failed_chunks,
                "used_reduced_text": reduced_chars < original_chars,
                "image_manifest": image_manifest,
                "chunk_summaries": chunk_summaries,
            },
        }

    def build_image_manifest(self, text: str) -> list[dict]:
        blocks = self._split_blocks(text)
        manifest = []
        seen = set()
        for index, block in enumerate(blocks):
            refs = self._extract_image_refs(block)
            if not refs:
                continue
            caption_parts = [block]
            if index + 1 < len(blocks):
                caption_parts.append(blocks[index + 1])
            caption_excerpt = " ".join(part.strip() for part in caption_parts if part.strip())[:400]
            figure_label = self._extract_figure_label(" ".join(caption_parts))
            for ref in refs:
                if ref in seen:
                    continue
                seen.add(ref)
                manifest.append(
                    {
                        "image_path": ref,
                        "figure_label": figure_label,
                        "caption_excerpt": caption_excerpt,
                    }
                )
        return manifest

    @staticmethod
    def _split_blocks(text: str) -> list[str]:
        return [chunk.strip() for chunk in re.split(r"\n\s*\n+", text) if chunk and chunk.strip()]

    def _split_large_block(self, block: str) -> list[str]:
        lines = [line.rstrip() for line in block.splitlines()]
        pieces: list[str] = []
        current: list[str] = []
        current_chars = 0

        def flush_current() -> None:
            nonlocal current, current_chars
            if not current:
                return
            piece = "\n".join(current).strip()
            if piece:
                pieces.append(piece)
            current = []
            current_chars = 0

        for line in lines:
            projected = current_chars + len(line) + (1 if current else 0)
            if current and projected > self.chunk_chars:
                flush_current()
            if len(line) > self.chunk_chars:
                flush_current()
                for i in range(0, len(line), self.chunk_chars):
                    piece = line[i:i + self.chunk_chars].strip()
                    if piece:
                        pieces.append(piece)
                continue
            current.append(line)
            current_chars += len(line) + (1 if len(current) > 1 else 0)

        flush_current()
        return [piece for piece in pieces if piece]

    def _extract_image_refs(self, block: str) -> list[str]:
        refs = []
        for match in self.IMAGE_PATTERN.finditer(block):
            ref = match.group(1) or match.group(2)
            if ref:
                refs.append(ref)
        return refs

    @staticmethod
    def _extract_figure_label(block: str) -> str:
        match = re.search(r"\b(Fig(?:ure)?\.?\s*[A-Za-z0-9]+|Table\s*[A-Za-z0-9]+)\b", block, re.IGNORECASE)
        return match.group(1) if match else ""
