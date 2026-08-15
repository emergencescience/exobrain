# Copyright (c) 2026 Symbol Science. All rights reserved.
"""Named, package-local system prompt loading for auditable LLM calls."""
from __future__ import annotations

from pathlib import Path

PROMPTS_DIRECTORY = Path(__file__).with_name("prompts")
SEMANTIC_PROOF_SYSTEM_PROMPT_FILE = "semantic_proof_structure_v2.md"


def load_system_prompt(filename: str) -> str:
    """Load one package prompt by its file name without accepting path traversal."""
    candidate = Path(filename)
    if candidate.name != filename or candidate.suffix != ".md":
        raise ValueError("System prompt names must be simple Markdown file names")
    prompt_path = PROMPTS_DIRECTORY / candidate
    if not prompt_path.is_file():
        raise FileNotFoundError(f"System prompt does not exist: {filename}")
    return prompt_path.read_text(encoding="utf-8").strip()
