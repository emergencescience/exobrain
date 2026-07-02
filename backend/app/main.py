"""Exobrain FastAPI application."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import config
from app.routes.chat import router as chat_router
from app.routes.documents import router as documents_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("exobrain")

app = FastAPI(
    title="Exobrain",
    description="AI-powered Markdown + LaTeX paper editor — bring your own LLM key.",
    version="0.1.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(chat_router)
app.include_router(documents_router)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


@app.get("/")
async def root():
    return {
        "service": "Exobrain",
        "docs": "/docs",
        "endpoints": {"chat": "POST /api/chat", "health": "GET /health"},
    }
