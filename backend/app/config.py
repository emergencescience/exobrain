"""Exobrain configuration — all via environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


@dataclass
class Config:
    """Server configuration using standard OpenAI-compatible environment names.

    `OPENAI_API_BASE` may include `/v1` or omit it. The endpoint property
    normalizes that variation without ever logging a credential.
    """

    llm_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    llm_base_url: str = field(
        default_factory=lambda: os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
    )
    llm_model: str = field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-5-mini"))

    @property
    def llm_chat_completions_url(self) -> str:
        base_url = self.llm_base_url.rstrip("/")
        suffix = "/chat/completions" if base_url.endswith("/v1") else "/v1/chat/completions"
        return f"{base_url}{suffix}"

    @property
    def llm_provider_host(self) -> str:
        """Safe provider metadata for logs; credentials are never included."""
        return urlparse(self.llm_base_url).netloc or "configured-provider"

    host: str = field(default_factory=lambda: os.getenv("EXOBRAIN_HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("EXOBRAIN_PORT", "8080")))
    rag_index_path: str = field(default_factory=lambda: os.getenv("EXOBRAIN_RAG_INDEX", ""))
    rag_top_k: int = field(default_factory=lambda: int(os.getenv("EXOBRAIN_RAG_TOP_K", "3")))
    cors_origins: list[str] = field(default_factory=lambda: os.getenv("EXOBRAIN_CORS_ORIGINS", "*").split(","))
    rate_limit_rpm: int = field(default_factory=lambda: int(os.getenv("EXOBRAIN_RATE_LIMIT_RPM", "10")))
    max_document_chars: int = field(default_factory=lambda: int(os.getenv("EXOBRAIN_MAX_DOCUMENT_CHARS", "30000")))


config = Config()
