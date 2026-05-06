"""Tests for LLM-based chunked paper reduction."""

import asyncio
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import Config
from agents.reducer_agent import ReducerAgent
from tools.paper_text_reducer import PaperTextReducer


class TestPaperTextReducer(unittest.TestCase):
    def test_chunk_text_splits_long_blocks_without_losing_order(self):
        reducer = PaperTextReducer(chunk_chars=60)
        text = """
# Results

Paragraph one with antibody Ab1 and KD 0.5 nM.

Paragraph two with antibody Ab2 and KD 1.2 nM.

Paragraph three with antibody Ab3 and KD 2.4 nM.
""".strip()

        chunks = reducer.chunk_text(text)

        self.assertGreaterEqual(len(chunks), 3)
        self.assertTrue(all(chunk["char_count"] <= 60 for chunk in chunks))
        merged = "\n\n".join(chunk["text"] for chunk in chunks)
        self.assertIn("Ab1", merged)
        self.assertIn("Ab2", merged)
        self.assertIn("Ab3", merged)

    def test_build_image_manifest_extracts_image_refs(self):
        reducer = PaperTextReducer(chunk_chars=100)
        text = """
![Figure 2](images/fig2.png)

Figure 2. Alignment of Ab1 heavy chain and light chain sequences.
""".strip()

        manifest = reducer.build_image_manifest(text)

        self.assertEqual(len(manifest), 1)
        self.assertEqual(manifest[0]["image_path"], "images/fig2.png")
        self.assertIn("Figure 2", manifest[0]["caption_excerpt"])


class TestReducerAgent(unittest.TestCase):
    def test_reducer_agent_filters_chunks_via_mock_llm(self):
        config = Config(mock_llm=True)
        config.enable_text_reduce = True
        config.text_reduce_min_chars = 1
        config.text_reduce_chunk_chars = 120
        config.text_reduce_max_tokens = 512
        agent = ReducerAgent(config)
        context = {
            "paper_id": "paper-1",
            "current_phase": "reduce",
            "markdown_text": """
# Results

Ab1 bound TREM2 with KD 0.5 nM.

# References

[1] Historical antibody discovery by ELISA should be dropped.

![Figure 2](images/fig2.png)

Figure 2. Alignment of Ab1 heavy chain and light chain sequences.
""".strip(),
        }

        result = asyncio.run(agent.execute(context))
        reduced = result.data["reduced_text"]
        meta = result.data["meta"]

        self.assertIn("Ab1 bound TREM2", reduced)
        self.assertIn("images/fig2.png", reduced)
        self.assertNotIn("Historical antibody discovery", reduced)
        self.assertGreater(meta["total_chunks"], 0)
        self.assertEqual(meta["llm_calls"], meta["total_chunks"])


if __name__ == "__main__":
    unittest.main()
