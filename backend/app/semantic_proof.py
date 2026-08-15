# Copyright (c) 2026 Symbol Science. All rights reserved.
"""Schema-constrained LLM proposals for local proof-fragment structure.

This module never marks a mathematical relationship verified.  It only proposes
semantic roles, groupings, and which bounded deterministic rule could be tried.
All proposals are validated against existing source-step IDs and source spans.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.config import config

logger = logging.getLogger("exobrain.semantic_proof")

_ROLES = {"definition", "hypothesis", "lemma", "deduction", "conclusion"}
_TARGETS = {"none", "sympy", "rule"}
_SCHEMA = {
    "type": "object",
    "properties": {
        "fragments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "role": {"type": "string", "enum": sorted(_ROLES)},
                    "step_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["title", "role", "step_ids"],
                "additionalProperties": False,
            },
        },
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "step_id": {"type": "string"},
                    "role": {"type": "string", "enum": sorted(_ROLES)},
                    "verification_target": {"type": "string", "enum": sorted(_TARGETS)},
                    "rule_id": {"type": "string"},
                    "depends_on": {"type": "array", "items": {"type": "string"}},
                    "rationale": {"type": "string"},
                },
                "required": ["step_id", "role", "verification_target", "rule_id", "depends_on", "rationale"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["fragments", "steps"],
    "additionalProperties": False,
}


def _source_payload(graph: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": step["id"],
            "text": step["text"],
            "source": step["source"],
            "heuristic_kind": step["kind"],
            "is_formula": bool(step.get("is_formula")),
        }
        for fragment in graph.get("fragments", [])
        for step in fragment.get("steps", [])
    ]


def validate_semantic_proposal(raw: dict[str, Any], graph: dict[str, Any]) -> dict[str, Any] | None:
    """Reject LLM output that cannot be tied exactly to existing source steps."""
    known = {step["id"] for step in _source_payload(graph)}
    raw_steps = raw.get("steps")
    raw_fragments = raw.get("fragments")
    if not isinstance(raw_steps, list) or not isinstance(raw_fragments, list):
        return None
    normalized_steps: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw_steps:
        if not isinstance(item, dict):
            return None
        step_id = item.get("step_id")
        role = item.get("role")
        target = item.get("verification_target")
        dependencies = item.get("depends_on")
        if not isinstance(step_id, str) or step_id not in known or step_id in seen:
            return None
        if role not in _ROLES or target not in _TARGETS or not isinstance(dependencies, list):
            return None
        if any(not isinstance(dep, str) or dep not in known for dep in dependencies):
            return None
        seen.add(step_id)
        normalized_steps.append({
            "step_id": step_id,
            "role": role,
            "verification_target": target,
            "rule_id": str(item.get("rule_id", ""))[:120],
            "depends_on": dependencies,
            "rationale": str(item.get("rationale", ""))[:500],
        })
    normalized_fragments: list[dict[str, Any]] = []
    for item in raw_fragments:
        if not isinstance(item, dict) or item.get("role") not in _ROLES:
            return None
        step_ids = item.get("step_ids")
        if not isinstance(step_ids, list) or not step_ids or any(step_id not in known for step_id in step_ids):
            return None
        normalized_fragments.append({
            "title": str(item.get("title", "Untitled semantic fragment"))[:160],
            "role": item["role"],
            "step_ids": step_ids,
        })
    return {"fragments": normalized_fragments, "steps": normalized_steps}


async def propose_semantic_structure(graph: dict[str, Any], locale: str) -> dict[str, Any] | None:
    """Ask the configured server-side model for a source-bound structural proposal."""
    if not config.llm_api_key:
        return None
    payload = _source_payload(graph)
    if not payload:
        return None
    system = """You classify local mathematical proof source blocks. Return a structural proposal, not proof evidence. Preserve the supplied IDs and never invent a step. Definitions, hypotheses, and cited lemmas use verification_target=none. A deduction uses sympy only for closed local algebra/calculation; use rule for a named bounded rewrite or theorem-specific validator. A theorem citation is a lemma, not a verified deduction. An approximation with an omitted remainder must remain rule and identify the missing error-bound obligation. Do not claim anything verified."""
    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(
                f"{config.llm_base_url.rstrip('/')}/v1/chat/completions",
                headers={"Authorization": f"Bearer {config.llm_api_key}", "Content-Type": "application/json"},
                json={
                    "model": config.llm_model,
                    "temperature": 0,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": json.dumps({"locale": locale, "source_steps": payload}, ensure_ascii=False)},
                    ],
                    "response_format": {"type": "json_schema", "json_schema": {"name": "semantic_proof_structure", "strict": True, "schema": _SCHEMA}},
                },
            )
            response.raise_for_status()
            raw_content = response.json()["choices"][0]["message"]["content"]
            proposal = validate_semantic_proposal(json.loads(raw_content), graph)
            if proposal is None:
                logger.warning("Rejected source-unbound semantic proof proposal")
            return proposal
    except (httpx.HTTPError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        logger.info("Semantic proof proposal unavailable: %s", exc)
        return None


def apply_semantic_proposal(graph: dict[str, Any], proposal: dict[str, Any]) -> dict[str, Any]:
    """Attach a proposal without treating the LLM as a verification authority."""
    by_id = {
        step["id"]: step
        for fragment in graph.get("fragments", [])
        for step in fragment.get("steps", [])
    }
    for annotation in proposal["steps"]:
        step = by_id[annotation["step_id"]]
        step["semantic_role"] = annotation["role"]
        step["verification_target"] = annotation["verification_target"]
        step["semantic_rule_id"] = annotation["rule_id"]
        step["semantic_rationale"] = annotation["rationale"]
        step["semantic_depends_on"] = annotation["depends_on"]
        # A cited premise is intentionally not an unexecuted formula obligation.
        # This is a classification label, not mathematical evidence.
        if annotation["role"] in {"definition", "hypothesis", "lemma"} and annotation["verification_target"] == "none":
            step["local_status"] = "not_required"
    graph["semantic_proposal"] = {
        "status": "proposed",
        "model": config.llm_model,
        "fragments": proposal["fragments"],
        "notice": "LLM structure is a source-bound proposal; only rule validators or execution evidence may establish verification.",
    }
    graph.setdefault("limitations", []).append(
        "Semantic roles are LLM proposals bound to source steps; they do not constitute mathematical verification."
    )
    return graph
