# 🧠 Exobrain

**AI-powered Markdown + LaTeX paper editor.** Build academic papers through natural language conversation. Works with any OpenAI-compatible LLM.

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="License MIT">
  <img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/next.js-15-black" alt="Next.js 15">
</p>

---

## Quick Start

```bash
# Set your LLM API key
export EXOBRAIN_LLM_API_KEY="sk-your-deepseek-key"

# Start everything
docker-compose up -d

# Open http://localhost:3000
```

That's it. No auth, no credits, no cloud dependency — just your LLM key and a browser.

## Development and test

The standalone application consists only of `frontend/` and `backend/`. It has no account, credit, or JWT requirement: an absent `X-User-Id` uses the backend's local development namespace.

### 1. Start the FastAPI backend

```bash
cd backend

# First run: create the project environment and install runtime/test dependencies.
uv sync --extra test

# Copy/edit .env as needed. An OpenAI-compatible key is optional for canned demos,
# but needed for live chat.
export EXOBRAIN_CORS_ORIGINS="http://localhost:3000,http://127.0.0.1:3000"
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8080
```

RAG is optional and installs the larger `sentence-transformers`/PyTorch stack only when requested:

```bash
uv sync --extra rag
```

Confirm it is running:

```bash
curl http://127.0.0.1:8080/health
```

### 2. Start the standalone frontend in a second terminal

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`. The frontend directly calls `http://localhost:8080` by default. It offers standalone Markdown editing, LaTeX rendering, document storage, chat, and formula verification.

To use another backend URL, set `NEXT_PUBLIC_EXOBRAIN_API_URL` before starting the frontend.

### Local API and test checks

```bash
# In backend
uv run pytest tests/test_verify_api_integration.py

# Example: local direct verification, no JWT required
curl -X POST http://127.0.0.1:8080/api/verify \
  -H 'Content-Type: application/json' \
  -d '{"markdown":"For $x=2$, $x^2=4$.","locale":"en"}'
```

The direct backend assigns an absent `X-User-Id` to `local`. Do not expose the local development server to an untrusted network.

## Features

- 🗣️ **Natural language chat** — describe what you want, get a polished paper
- 📐 **LaTeX math rendering** — KaTeX for inline `$E=mc^2$` and block `$$...$$` equations
- 📝 **Paragraph-level comments** — hover any paragraph, add inline notes
- 📄 **Source/Preview toggle** — switch between rendered output and raw Markdown
- ⚡ **Instant suggestions** — 4 pre-built STEM topics with zero-latency responses
- 🔌 **Any LLM provider** — DeepSeek, OpenAI, Anthropic, Ollama, anything OpenAI-compatible
- 🧠 **RAG support** — optional knowledge base for grounding (see [RAG](#retrieval-augmented-generation))

## Configuration

All via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `EXOBRAIN_LLM_API_KEY` | (required) | Your LLM API key |
| `EXOBRAIN_LLM_BASE_URL` | `https://api.deepseek.com` | OpenAI-compatible base URL |
| `EXOBRAIN_LLM_MODEL` | `deepseek-chat` | Model name |
| `EXOBRAIN_RAG_INDEX` | (empty) | Path to pre-built RAG index JSON |
| `EXOBRAIN_RAG_TOP_K` | `3` | Number of RAG chunks to retrieve |
| `EXOBRAIN_CORS_ORIGINS` | `*` | Allowed CORS origins (comma-separated) |

## Retrieval-Augmented Generation (RAG)

Exobrain ships with a **built-in MPC textbook knowledge base** (Model Predictive Control: From Foundations to Advanced Topics, CC BY-NC 4.0). When enabled, every query retrieves the most relevant textbook sections and injects them into the LLM context — dramatically reducing hallucination.

### How it works

```
User asks: "What is a state-space model?"
  → Retrieve top-3 chunks from mpc_rag.json (cosine similarity)
  → Inject into system prompt as "REFERENCE MATERIAL"
  → LLM answers grounded in textbook content
```

### Building the index

```bash
# One-time: clone MPC textbook and build embeddings
cd backend
pip install sentence-transformers
python build_rag_index.py --clone

# Output: app/data/mpc_rag.json (232 chunks, 2.6 MB)
```

The index is mounted via `docker-compose.yml`:
```yaml
volumes:
  - ./backend/app/data:/app/data
environment:
  - EXOBRAIN_RAG_INDEX=/app/data/mpc_rag.json
```

### Using your own knowledge base

Replace `mpc_rag.json` with any index built from your own LaTeX content:

```python
from app.rag.retrieve import build_index
build_index("/path/to/your/latex/chapters", "app/data/my_rag.json")
```

Set `EXOBRAIN_RAG_INDEX=/app/data/my_rag.json` in docker-compose. Any structured LaTeX textbook works — the parser handles `\section{}`, `\subsection{}`, `\begin{equation}`, and strips formatting commands.

## API

### `POST /api/chat`

```json
{
  "messages": [{"role": "user", "content": "Derive the quadratic formula"}],
  "suggestion_id": "quadratic_derivation",  // optional, for instant pre-canned responses
  "document": "# Current paper...",           // optional, current document context
  "comments": {"0": ["needs citation"]},      // optional, inline comments
  "enable_rag": true                          // optional, enable RAG retrieval
}
```

### `GET /health`

```json
{"status": "ok", "version": "0.1.0"}
```

## Retrieval-Augmented Generation (RAG)

Exobrain supports optional knowledge-base grounding to reduce hallucination:

```bash
# Build a RAG index from LaTeX source
python -m app.rag.retrieve build --tex-dir /path/to/latex/chapters --output rag_index.json

# Set the index path
export EXOBRAIN_RAG_INDEX=/path/to/rag_index.json
```

The built-in RAG pipeline:
1. Parses LaTeX chapter files
2. Chunks by section/subsection
3. Computes embeddings with `all-MiniLM-L6-v2` (384-dim, free)
4. Retrieves top-k chunks via cosine similarity at query time
5. Injects into the system prompt as ground truth

## Architecture

```
Browser (localStorage)
  │  POST /api/chat
  ▼
FastAPI backend (Python)
  │  ┌─ Suggestion? → return canned response (zero LLM cost)
  │  ├─ RAG enabled? → retrieve chunks → inject into system prompt
  │  └─ Call LLM (DeepSeek/OpenAI/Ollama) → return reply + document
  ▼
Next.js frontend (React)
  │  Left: Chat panel (45%)
  │  Right: Markdown + LaTeX preview (55%)
  │  Toggle: Source/Preview modes
```

## Self-Hosted vs Emergence Science

| | Self-Hosted (this repo) | [emergence.science](https://emergence.science/play/exobrain) |
|---|---|---|
| Auth | None | Emergence Science login |
| LLM | Your own API key | Built-in DeepSeek |
| Cost | Your LLM provider's pricing | 10,000 micro-credits/chat |
| RAG | Build your own index | Pre-built MPC textbook index |
| Customization | Full source access | Managed service |

## License

MIT — use it, fork it, ship it.

---

Built by [Emergence Science](https://emergence.science) — the protocol for the agent economy.
