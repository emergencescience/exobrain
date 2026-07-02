"""RAG pipeline — build and retrieve from a knowledge base."""

import json
import logging
import os
import re
from pathlib import Path

import numpy as np

logger = logging.getLogger("exobrain.rag")

# We lazy-load sentence-transformers since it's only needed for building/querying
_embedder = None
_index: list[dict] | None = None


def _get_embedder():
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer

        _embedder = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedder


# ── LaTeX Parsing ────────────────────────────────────────────────────


def _strip_latex_commands(text: str) -> str:
    """Strip common LaTeX commands but preserve math and structure."""
    # Remove \section{}, \subsection{}, \textbf{} — keep inner text
    text = re.sub(r"\\(section|subsection|subsubsection|chapter|textbf|textit|emph|texttt)\{([^}]*)\}", r"\2", text)
    # Remove \begin{...} and \end{...} but keep content
    text = re.sub(r"\\begin\{[^}]*\}", "", text)
    text = re.sub(r"\\end\{[^}]*\}", "", text)
    # Remove \label{...}, \ref{...}, \cite{...}
    text = re.sub(r"\\(label|ref|cite|eqref)\{[^}]*\}", "", text)
    # Remove \\ (line breaks) — replace with space
    text = text.replace("\\\\", " ")
    # Remove comments
    text = re.sub(r"(?<!\\)%.*$", "", text, flags=re.MULTILINE)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_latex_chapters(tex_dir: str) -> list[dict]:
    """Parse all .tex chapter files and return chunked sections.

    Each chunk: {"chapter": str, "section": str, "text": str, "source": str}
    """
    chunks = []
    tex_path = Path(tex_dir)

    for tex_file in sorted(tex_path.glob("Chapter*.tex")):
        chapter_name = tex_file.stem
        content = tex_file.read_text(encoding="utf-8")

        # Split by \section and \subsection
        sections = re.split(r"\\(?:sub)?section\{([^}]*)\}", content)
        # sections[0] = text before first section heading
        # sections[1] = heading, sections[2] = body, etc.

        for i in range(1, len(sections), 2):
            heading = sections[i].strip()
            body = sections[i + 1] if i + 1 < len(sections) else ""
            clean = _strip_latex_commands(body)

            if len(clean) > 100:  # Skip tiny chunks
                chunks.append(
                    {
                        "chapter": chapter_name,
                        "section": heading,
                        "text": clean,
                        "source": str(tex_file),
                    }
                )

    logger.info("Parsed %d chunks from %d chapters in %s", len(chunks), len(list(tex_path.glob("Chapter*.tex"))), tex_dir)
    return chunks


# ── Index Building ────────────────────────────────────────────────────


def build_index(tex_dir: str, output_path: str) -> str:
    """Parse LaTeX, compute embeddings, save JSON index.

    Returns path to the built index file.
    """
    chunks = parse_latex_chapters(tex_dir)
    if not chunks:
        raise ValueError(f"No chunks found in {tex_dir}")

    model = _get_embedder()
    texts = [c["text"] for c in chunks]
    logger.info("Computing embeddings for %d chunks...", len(texts))
    embeddings = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)

    # Attach embeddings to chunks
    for chunk, emb in zip(chunks, embeddings):
        chunk["embedding"] = emb.tolist()

    index = {"chunks": chunks, "model": "all-MiniLM-L6-v2", "dim": 384}

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(index, ensure_ascii=False))
    logger.info("RAG index saved to %s (%d chunks)", output_path, len(chunks))
    return str(out)


# ── Retrieval ─────────────────────────────────────────────────────────


def load_index(index_path: str) -> list[dict]:
    """Load RAG index from JSON file."""
    global _index
    if _index is not None:
        return _index

    if not index_path or not os.path.exists(index_path):
        logger.warning("RAG index not found at %s — retrieval disabled", index_path)
        _index = []
        return _index

    data = json.loads(Path(index_path).read_text(encoding="utf-8"))
    _index = data.get("chunks", [])
    logger.info("Loaded RAG index: %d chunks", len(_index))
    return _index


def retrieve(query: str, index_path: str, top_k: int = 3) -> list[dict]:
    """Retrieve top-k relevant chunks for a query."""
    chunks = load_index(index_path)
    if not chunks:
        return []

    model = _get_embedder()
    query_emb = model.encode([query], normalize_embeddings=True)[0]

    # Cosine similarity with pre-normalized embeddings = dot product
    scores = []
    for chunk in chunks:
        emb = np.array(chunk["embedding"])
        score = float(np.dot(query_emb, emb))
        scores.append((score, chunk))

    scores.sort(key=lambda x: x[0], reverse=True)

    results = []
    for score, chunk in scores[:top_k]:
        results.append(
            {
                "chapter": chunk["chapter"],
                "section": chunk["section"],
                "text": chunk["text"],
                "score": round(score, 4),
            }
        )

    return results


def format_rag_context(results: list[dict]) -> str:
    """Format retrieved chunks as a system prompt context block."""
    if not results:
        return ""

    lines = ["REFERENCE MATERIAL (from MPC textbook):", ""]
    for r in results:
        lines.append(f"## {r['chapter']} — {r['section']} (relevance: {r['score']})")
        lines.append(r["text"])
        lines.append("")
    return "\n".join(lines)
