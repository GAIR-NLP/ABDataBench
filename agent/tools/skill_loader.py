"""Load agent prompt assets through local SKILL.md metadata."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping


AGENT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SKILLS_DIR = AGENT_ROOT / "skills"


class SkillLoadError(RuntimeError):
    """Raised when a skill exists but cannot provide the requested prompt."""


def _parse_front_matter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}

    lines = text.splitlines()
    end_index = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_index = index
            break
    if end_index is None:
        return {}

    metadata: dict[str, str] = {}
    for raw_line in lines[1:end_index]:
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip("\"'")
    return metadata


def _skills_dir() -> Path:
    configured = os.environ.get("AGENT_SKILLS_DIR", "").strip()
    return Path(configured).expanduser().resolve() if configured else DEFAULT_SKILLS_DIR


def load_skill_metadata(skill_name: str) -> dict[str, str]:
    skill_path = _skills_dir() / skill_name / "SKILL.md"
    if not skill_path.exists():
        return {}
    return _parse_front_matter(skill_path.read_text(encoding="utf-8"))


def _read_prompt(path_value: str, *, skill_name: str) -> str:
    skill_dir = _skills_dir() / skill_name
    prompt_path = (skill_dir / path_value).resolve()
    try:
        prompt_path.relative_to(AGENT_ROOT.resolve())
    except ValueError as exc:
        raise SkillLoadError(
            f"Skill {skill_name!r} points outside the agent directory: {path_value}"
        ) from exc
    if not prompt_path.exists():
        raise SkillLoadError(f"Skill {skill_name!r} prompt file not found: {prompt_path}")
    return prompt_path.read_text(encoding="utf-8")


def load_skill_prompt(
    skill_name: str,
    prompt_key: str,
    fallback_path: str | os.PathLike[str],
) -> str:
    """Read a prompt through skill metadata, falling back to the legacy prompt path."""

    metadata = load_skill_metadata(skill_name)
    if prompt_key in metadata:
        return _read_prompt(metadata[prompt_key], skill_name=skill_name)
    return Path(fallback_path).read_text(encoding="utf-8")


def load_skill_prompt_set(
    skill_name: str,
    prompt_paths: Mapping[str, str | os.PathLike[str]],
) -> dict[str, str]:
    return {
        key: load_skill_prompt(skill_name, key, fallback_path)
        for key, fallback_path in prompt_paths.items()
    }
