"""Exobrain FastAPI application."""

import logging

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import config
from app.routes.chat import router as chat_router
from app.routes.compute import router as compute_router
from app.routes.documents import router as documents_router
from app.routes.dashboard import router as dashboard_router
from app.routes.evidence import router as evidence_router
from app.routes.verify import router as verify_router
from app.internal_auth import InternalKeyMiddleware
from app.routes.run import router as run_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("exobrain")
logger.info(
    "llm_config provider=%s model=%s api_key_configured=%s",
    config.llm_provider_host,
    config.llm_model,
    bool(config.llm_api_key),
)

app = FastAPI(
    title="Exobrain",
    description="AI-powered Markdown + LaTeX paper editor — bring your own LLM key.",
    version="0.1.0",
)

app.add_middleware(InternalKeyMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(chat_router)
app.include_router(compute_router)
app.include_router(documents_router)
app.include_router(dashboard_router)
app.include_router(evidence_router)
app.include_router(verify_router)
app.include_router(run_router)


# Static files — mobile web app served at /m/
MOBILE_DIR = os.path.join(os.path.dirname(__file__), "mobile_dist")
if os.path.isdir(MOBILE_DIR):
    app.mount("/m", StaticFiles(directory=MOBILE_DIR, html=True), name="mobile")
    logger.info(f"Mobile app mounted at /m/ from {MOBILE_DIR}")

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
