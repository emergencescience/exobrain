# Copyright (c) 2026 Symbol Science. All rights reserved.
"""Configuration tests for the standard OpenAI-compatible provider contract."""
from app.config import Config


def test_openai_environment_names_are_the_only_llm_source(monkeypatch):
    monkeypatch.setenv("EXOBRAIN_LLM_API_KEY", "legacy-key-that-must-be-ignored")
    monkeypatch.setenv("EXOBRAIN_LLM_BASE_URL", "https://legacy.invalid")
    monkeypatch.setenv("EXOBRAIN_LLM_MODEL", "legacy-model")
    monkeypatch.setenv("OPENAI_API_KEY", "standard-key")
    monkeypatch.setenv("OPENAI_API_BASE", "https://provider.example/v1")
    monkeypatch.setenv("OPENAI_MODEL", "standard-model")
    config = Config()
    assert config.llm_api_key == "standard-key"
    assert config.llm_base_url == "https://provider.example/v1"
    assert config.llm_model == "standard-model"
    assert config.llm_chat_completions_url == "https://provider.example/v1/chat/completions"


def test_openai_base_without_v1_gets_one_canonical_v1_suffix(monkeypatch):
    monkeypatch.setenv("OPENAI_API_BASE", "https://provider.example/")
    assert Config().llm_chat_completions_url == "https://provider.example/v1/chat/completions"
