# Copyright (c) 2026 Symbol Science. All rights reserved.
"""Tests for named, auditable package system prompts."""
from __future__ import annotations

import pytest

from app.prompt_loader import SEMANTIC_PROOF_SYSTEM_PROMPT_FILE, load_system_prompt
from app.semantic_proof import SEMANTIC_PROOF_SYSTEM_PROMPT, SEMANTIC_PROOF_SYSTEM_PROMPT_NAME


def test_semantic_prompt_name_is_the_loaded_file_name():
    assert SEMANTIC_PROOF_SYSTEM_PROMPT_NAME == SEMANTIC_PROOF_SYSTEM_PROMPT_FILE
    assert SEMANTIC_PROOF_SYSTEM_PROMPT_NAME == "semantic_proof_structure_v2.md"
    assert load_system_prompt(SEMANTIC_PROOF_SYSTEM_PROMPT_NAME) == SEMANTIC_PROOF_SYSTEM_PROMPT
    assert "polar coordinates" in SEMANTIC_PROOF_SYSTEM_PROMPT.lower()


def test_prompt_loader_rejects_path_traversal():
    with pytest.raises(ValueError):
        load_system_prompt("../secret.md")
