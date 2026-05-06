"""Tests for agent skill prompt loading."""

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.skill_loader import load_skill_metadata, load_skill_prompt


class TestSkillLoader(unittest.TestCase):
    def test_loads_skill_metadata(self):
        metadata = load_skill_metadata("antibody-skeleton-extraction")
        self.assertEqual(metadata["agent"], "skeleton")
        self.assertEqual(metadata["system_prompt"], "../../prompts/skeleton_system.txt")

    def test_skill_prompt_matches_legacy_prompt_asset(self):
        agent_root = Path(__file__).resolve().parent.parent
        legacy_path = agent_root / "prompts" / "reviewer_system.txt"
        prompt = load_skill_prompt("reviewer-qa", "system_prompt", legacy_path)
        self.assertEqual(prompt, legacy_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
