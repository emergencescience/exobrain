"""Chat route — the core Exobrain endpoint."""

import logging
import time

import httpx
from fastapi import APIRouter, HTTPException, Request

from app.config import config
from app.prompts.system import SYSTEM_PROMPT, SYSTEM_PROMPT_WITH_RAG
from app.rag.retrieve import format_rag_context, retrieve

logger = logging.getLogger("exobrain.chat")

router = APIRouter(prefix="/api", tags=["chat"])

# ── Pre-canned responses (same as hosted version) ──

EXOBRAIN_CANNED: dict = {
    "riemann_intro": {
        "en": {
            "reply": (
                "Here's a polished introduction for your paper on the Riemann zeta function.\n\n"
                "I've set up the historical context, the formal definition, the Euler product connection, "
                "and a brief overview of the Riemann Hypothesis. All equations use proper LaTeX.\n\n"
                "```markdown\n"
                "# Introduction to the Riemann Zeta Function\n\n"
                "## 1. Historical Background\n\n"
                'The Riemann zeta function $\\zeta(s)$ was first studied by Leonhard Euler in the 18th century, '
                "who discovered its remarkable connection to the prime numbers via the product formula:\n\n"
                "$$\\zeta(s) = \\sum_{n=1}^{\\infty} \\frac{1}{n^s} = \\prod_{p \\text{ prime}} \\frac{1}{1 - p^{-s}} \\quad (\\Re(s) > 1)$$\n\n"
                'In 1859, Bernhard Riemann extended $\\zeta(s)$ to the entire complex plane '
                'via analytic continuation, and proposed the now-famous Riemann Hypothesis.\n\n'
                "## 2. Definition and Basic Properties\n\n"
                'The Riemann zeta function is defined for $\\Re(s) > 1$ by:\n\n'
                "$$\\zeta(s) = \\sum_{n=1}^{\\infty} \\frac{1}{n^s}$$\n\n"
                'Riemann showed that $\\zeta(s)$ satisfies the functional equation:\n\n'
                "$$\\zeta(s) = 2^s \\pi^{s-1} \\sin\\left(\\frac{\\pi s}{2}\\right) \\Gamma(1-s) \\zeta(1-s)$$\n\n"
                "```"
            ),
            "document": (
                "# Introduction to the Riemann Zeta Function\n\n"
                "## 1. Historical Background\n\n"
                'The Riemann zeta function $\\zeta(s)$ was first studied by Leonhard Euler in the 18th century, '
                "who discovered its remarkable connection to the prime numbers via the product formula:\n\n"
                "$$\\zeta(s) = \\sum_{n=1}^{\\infty} \\frac{1}{n^s} = \\prod_{p \\text{ prime}} \\frac{1}{1 - p^{-s}} \\quad (\\Re(s) > 1)$$\n\n"
                'In 1859, Bernhard Riemann extended $\\zeta(s)$ to the entire complex plane '
                'via analytic continuation, and proposed the now-famous Riemann Hypothesis.\n\n'
                "## 2. Definition and Basic Properties\n\n"
                'The Riemann zeta function is defined for $\\Re(s) > 1$ by:\n\n'
                "$$\\zeta(s) = \\sum_{n=1}^{\\infty} \\frac{1}{n^s}$$\n\n"
                'Riemann showed that $\\zeta(s)$ satisfies the functional equation:\n\n'
                "$$\\zeta(s) = 2^s \\pi^{s-1} \\sin\\left(\\frac{\\pi s}{2}\\right) \\Gamma(1-s) \\zeta(1-s)$$\n\n"
                "## 3. The Riemann Hypothesis\n\n"
                "The Riemann Hypothesis asserts that **all non-trivial zeros** of $\\zeta(s)$ "
                "lie on the critical line $\\Re(s) = \\frac{1}{2}$."
            ),
        },
        "zh": {
            "reply": (
                "以下是为您撰写的黎曼 zeta 函数论文引言。\n\n"
                "```markdown\n"
                "# 黎曼 Zeta 函数导论\n\n"
                "## 1. 历史渊源\n\n"
                "黎曼 zeta 函数 $\\zeta(s)$ 最早由欧拉在 18 世纪研究，他发现了该函数与素数的深刻联系：\n\n"
                "$$\\zeta(s) = \\sum_{n=1}^{\\infty} \\frac{1}{n^s} = \\prod_{p \\text{ 为素数}} \\frac{1}{1 - p^{-s}} \\quad (\\Re(s) > 1)$$\n\n"
                "1859 年，黎曼在其传世论文中将 $\\zeta(s)$ 解析延拓至整个复平面，并提出了著名的黎曼猜想。\n\n"
                "## 2. 定义与基本性质\n\n"
                "$$\\zeta(s) = \\sum_{n=1}^{\\infty} \\frac{1}{n^s}$$\n\n"
                "函数方程：\n\n"
                "$$\\zeta(s) = 2^s \\pi^{s-1} \\sin\\left(\\frac{\\pi s}{2}\\right) \\Gamma(1-s) \\zeta(1-s)$$\n\n"
                "```"
            ),
            "document": (
                "# 黎曼 Zeta 函数导论\n\n"
                "## 1. 历史渊源\n\n"
                "黎曼 zeta 函数 $\\zeta(s)$ 最早由欧拉在 18 世纪研究，他发现了该函数与素数的深刻联系：\n\n"
                "$$\\zeta(s) = \\sum_{n=1}^{\\infty} \\frac{1}{n^s} = \\prod_{p \\text{ 为素数}} \\frac{1}{1 - p^{-s}} \\quad (\\Re(s) > 1)$$\n\n"
                "1859 年，黎曼在其传世论文中将 $\\zeta(s)$ 解析延拓至整个复平面，并提出了著名的黎曼猜想。\n\n"
                "## 2. 定义与基本性质\n\n"
                "$$\\zeta(s) = \\sum_{n=1}^{\\infty} \\frac{1}{n^s}$$\n\n"
                "函数方程：\n\n"
                "$$\\zeta(s) = 2^s \\pi^{s-1} \\sin\\left(\\frac{\\pi s}{2}\\right) \\Gamma(1-s) \\zeta(1-s)$$\n\n"
                "## 3. 黎曼猜想\n\n"
                "黎曼猜想断言：$\\zeta(s)$ 的所有非平凡零点均位于临界线 $\\Re(s) = \\frac{1}{2}$ 上。"
            ),
        },
    },
    "quadratic_derivation": {
        "en": {
            "reply": (
                "Here's a complete step-by-step derivation of the quadratic formula.\n\n"
                "```markdown\n"
                "# Derivation of the Quadratic Formula\n\n"
                "## 1. The Standard Form\n\n"
                "$$ax^2 + bx + c = 0 \\quad (a \\neq 0)$$\n\n"
                "## 2. Divide by $a$\n\n"
                "$$x^2 + \\frac{b}{a}x + \\frac{c}{a} = 0$$\n\n"
                "## 3. Move the Constant Term\n\n"
                "$$x^2 + \\frac{b}{a}x = -\\frac{c}{a}$$\n\n"
                "## 4. Complete the Square\n\n"
                "$$x^2 + \\frac{b}{a}x + \\frac{b^2}{4a^2} = \\frac{b^2}{4a^2} - \\frac{c}{a}$$\n\n"
                "$$\\left(x + \\frac{b}{2a}\\right)^2 = \\frac{b^2 - 4ac}{4a^2}$$\n\n"
                "## 5. Square Root Both Sides\n\n"
                "$$x + \\frac{b}{2a} = \\pm \\frac{\\sqrt{b^2 - 4ac}}{2a}$$\n\n"
                "## 6. Solve for $x$\n\n"
                "$$x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}$$\n\n"
                "```"
            ),
            "document": (
                "# Derivation of the Quadratic Formula\n\n"
                "## 1. The Standard Form\n\n"
                "$$ax^2 + bx + c = 0 \\quad (a \\neq 0)$$\n\n"
                "## 2. Divide by $a$\n\n"
                "$$x^2 + \\frac{b}{a}x + \\frac{c}{a} = 0$$\n\n"
                "## 3. Move the Constant Term\n\n"
                "$$x^2 + \\frac{b}{a}x = -\\frac{c}{a}$$\n\n"
                "## 4. Complete the Square\n\n"
                "$$x^2 + \\frac{b}{a}x + \\frac{b^2}{4a^2} = \\frac{b^2}{4a^2} - \\frac{c}{a}$$\n\n"
                "$$\\left(x + \\frac{b}{2a}\\right)^2 = \\frac{b^2 - 4ac}{4a^2}$$\n\n"
                "## 5. Square Root Both Sides\n\n"
                "$$x + \\frac{b}{2a} = \\pm \\frac{\\sqrt{b^2 - 4ac}}{2a}$$\n\n"
                "## 6. Solve for $x$\n\n"
                "$$x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}$$\n\n"
                "## 7. The Discriminant\n\n"
                "$\\Delta = b^2 - 4ac$ determines the nature of the roots."
            ),
        },
        "zh": {
            "reply": (
                "以下是二次公式的完整逐步推导。\n\n"
                "```markdown\n"
                "# 二次公式的推导\n\n"
                "## 1. 标准形式\n\n"
                "$$ax^2 + bx + c = 0 \\quad (a \\neq 0)$$\n\n"
                "## 2. 除以 $a$\n\n"
                "$$x^2 + \\frac{b}{a}x + \\frac{c}{a} = 0$$\n\n"
                "## 3. 移项\n\n"
                "$$x^2 + \\frac{b}{a}x = -\\frac{c}{a}$$\n\n"
                "## 4. 配方\n\n"
                "$$\\left(x + \\frac{b}{2a}\\right)^2 = \\frac{b^2 - 4ac}{4a^2}$$\n\n"
                "## 5. 开平方\n\n"
                "$$x + \\frac{b}{2a} = \\pm \\frac{\\sqrt{b^2 - 4ac}}{2a}$$\n\n"
                "## 6. 解出 $x$\n\n"
                "$$x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}$$\n\n"
                "```"
            ),
            "document": (
                "# 二次公式的推导\n\n"
                "## 1. 标准形式\n\n"
                "$$ax^2 + bx + c = 0 \\quad (a \\neq 0)$$\n\n"
                "## 2. 除以 $a$\n\n"
                "$$x^2 + \\frac{b}{a}x + \\frac{c}{a} = 0$$\n\n"
                "## 3. 移项\n\n"
                "$$x^2 + \\frac{b}{a}x = -\\frac{c}{a}$$\n\n"
                "## 4. 配方\n\n"
                "$$\\left(x + \\frac{b}{2a}\\right)^2 = \\frac{b^2 - 4ac}{4a^2}$$\n\n"
                "## 5. 开平方\n\n"
                "$$x + \\frac{b}{2a} = \\pm \\frac{\\sqrt{b^2 - 4ac}}{2a}$$\n\n"
                "## 6. 解出 $x$\n\n"
                "$$x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}$$\n\n"
                "## 7. 判别式\n\n"
                "$\\Delta = b^2 - 4ac$ 决定根的性质。"
            ),
        },
    },
}


# ── Endpoint ──────────────────────────────────────────────────────────


@router.post("/chat")
async def chat(request: Request):
    """Handle Exobrain chat.

    Request body:
        messages: list[{"role": "user"|"assistant", "content": str}]
        model: str (optional, default from config)
        document: str | None (current document for context)
        comments: dict | None (inline comments)
        suggestion_id: str | None (pre-canned response ID)
        enable_rag: bool (default True if RAG index available)
        doc_id: str | None (document ID for persistence — auto-saves snapshots)
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    messages = body.get("messages", [])
    if not messages:
        raise HTTPException(status_code=400, detail="messages is required")

    model = body.get("model", config.llm_model)
    document = body.get("document")
    comments = body.get("comments")
    suggestion_id = body.get("suggestion_id")
    enable_rag = body.get("enable_rag", True)
    doc_id = body.get("doc_id")

    # ── Pre-canned suggestion? Return immediately ──
    if suggestion_id:
        canned = EXOBRAIN_CANNED.get(suggestion_id)
        if canned:
            lang = "en"
            if messages:
                last_msg = messages[-1].get("content", "")
                if any("\u4e00" <= ch <= "\u9fff" for ch in last_msg):
                    lang = "zh"
            entry = canned.get(lang, canned["en"])
            return {"reply": entry["reply"], "document": entry.get("document"), "model": model, "canned": True}

    # ── Build LLM messages ──
    llm_messages = list(messages)

    # Inject system prompt
    has_system = any(m.get("role") == "system" for m in llm_messages)
    if not has_system:
        sys_content = SYSTEM_PROMPT

        # RAG augmentation
        if enable_rag and config.rag_index_path:
            last_user_msg = ""
            for m in reversed(llm_messages):
                if m.get("role") == "user":
                    last_user_msg = m["content"]
                    break
            if last_user_msg:
                rag_results = retrieve(last_user_msg, config.rag_index_path, config.rag_top_k)
                if rag_results:
                    rag_ctx = format_rag_context(rag_results)
                    sys_content = SYSTEM_PROMPT_WITH_RAG + "\n\n" + rag_ctx

        llm_messages.insert(0, {"role": "system", "content": sys_content})

    # Append document context
    if document:
        doc_ctx = f"Current document:\n```markdown\n{document}\n```"
        if comments:
            comment_lines = []
            for line_idx, cmts in comments.items():
                for cmt in cmts:
                    comment_lines.append(f"- Line {line_idx}: {cmt}")
            if comment_lines:
                doc_ctx += "\n\nActive comments:\n" + "\n".join(comment_lines)
        llm_messages.append({"role": "user", "content": doc_ctx})

    # ── Call LLM ──
    if not config.llm_api_key:
        raise HTTPException(
            status_code=503,
            detail="LLM not configured. Set EXOBRAIN_LLM_API_KEY environment variable.",
        )

    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{config.llm_base_url}/v1/chat/completions",
                json={
                    "model": model,
                    "messages": llm_messages,
                    "temperature": 0.7,
                    "max_tokens": 8192,
                },
                headers={
                    "Authorization": f"Bearer {config.llm_api_key}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            data = response.json()
            reply = data["choices"][0]["message"]["content"].strip()
            usage = data.get("usage", {})
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="LLM request timed out. Please try again.")
    except httpx.HTTPStatusError as e:
        logger.error("LLM returned %d: %s", e.response.status_code, e.response.text[:200])
        raise HTTPException(status_code=502, detail="LLM service error. Please try again.")

    elapsed = round(time.monotonic() - t0, 2)

    # ── Auto-save snapshot if doc_id provided ──
    snapshot_id = None
    if doc_id:
        try:
            from app.storage import get_storage
            storage = await get_storage()
            # Save current state as snapshot before update
            snap = await storage.save_snapshot(doc_id, document or "", list(messages))
            snapshot_id = snap.id
            # Update document with latest markdown + messages
            updated_doc = body.get("document")  # frontend passes updated document
            await storage.update_document(
                doc_id,
                updated_doc or "",
                list(messages),
            )
        except Exception:
            logger.exception("Failed to save snapshot for doc %s", doc_id)

    return {
        "reply": reply,
        "model": model,
        "usage": {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        },
        "elapsed_s": elapsed,
        "snapshot_id": snapshot_id,
    }
