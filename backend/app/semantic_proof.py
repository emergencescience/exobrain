# Copyright (c) 2026 Symbol Science. All rights reserved.
"""Schema-constrained LLM proposals for local proof-fragment structure.

This module never marks a mathematical relationship verified.  It only proposes
semantic roles, groupings, and which bounded deterministic rule could be tried.
All proposals are validated against existing source-step IDs and source spans.
"""
from __future__ import annotations

import json
import logging
from hashlib import sha256
from typing import Any

import httpx

from app.config import config

logger = logging.getLogger("exobrain.semantic_proof")

SEMANTIC_PROOF_SYSTEM_PROMPT_NAME = "semantic-proof-structure-v1"
SEMANTIC_PROOF_SYSTEM_PROMPT = """You classify local mathematical proof source blocks. Return a structural proposal, not proof evidence. Preserve the supplied IDs and never invent a step. Definitions, hypotheses, and cited lemmas use verification_target=none. A deduction uses sympy only for closed local algebra/calculation; use rule for a named bounded rewrite or theorem-specific validator. A theorem citation is a lemma, not a verified deduction. An approximation with an omitted remainder must remain rule and identify the missing error-bound obligation. Do not claim anything verified."""


def _audit_metadata(
    *,
    payload: list[dict[str, Any]],
    locale: str,
    status: str,
    response_text: str = "",
    http_status: int | None = None,
    error_type: str = "",
) -> dict[str, Any]:
    """Return the credential-free audit payload for one semantic parser call."""
    return {
        "call_name": "semantic_proof_structure",
        "system_prompt_name": SEMANTIC_PROOF_SYSTEM_PROMPT_NAME,
        "provider": config.llm_provider_host,
        "model": config.llm_model,
        "request_payload": {"locale": locale, "source_steps": payload},
        "response_text": response_text,
        "status": status,
        "http_status": http_status,
        "error_type": error_type,
    }

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


async def propose_semantic_structure(graph: dict[str, Any], locale: str) -> tuple[dict[str, Any] | None, dict[str, str]]:
    """Ask the configured server-side model for a source-bound structural proposal.

    The second return value is a safe, user-visible availability summary.  It
    never includes provider response bodies or credentials.
    """
    if not config.llm_api_key:
        logger.warning("semantic_parse.unavailable reason=llm_not_configured")
        return None, {"status": "unavailable", "reason": "llm_not_configured", "notice": "Semantic parsing needs a configured server-side LLM provider."}
    payload = _source_payload(graph)
    if not payload:
        logger.info("semantic_parse.unavailable reason=no_source_steps")
        return None, {"status": "unavailable", "reason": "no_source_steps", "notice": "The selected source contains no proof steps to classify."}
    logger.info(
        "semantic_parse.request provider=%s model=%s source_steps=%d locale=%s",
        config.llm_provider_host,
        config.llm_model,
        len(payload),
        locale,
    )
    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(
                config.llm_chat_completions_url,
                headers={"Authorization": f"Bearer {config.llm_api_key}", "Content-Type": "application/json"},
                json={
                    "model": config.llm_model,
                    "temperature": 0,
                    "messages": [
                        {"role": "system", "content": SEMANTIC_PROOF_SYSTEM_PROMPT},
                        {"role": "user", "content": json.dumps({"locale": locale, "source_steps": payload}, ensure_ascii=False)},
                    ],
                    "response_format": {"type": "json_schema", "json_schema": {"name": "semantic_proof_structure", "strict": True, "schema": _SCHEMA}},
                },
            )
            response.raise_for_status()
            raw_content = response.json()["choices"][0]["message"]["content"]
            proposal = validate_semantic_proposal(json.loads(raw_content), graph)
            if proposal is None:
                logger.warning("semantic_parse.unavailable reason=proposal_rejected")
                return None, {
                    "status": "unavailable",
                    "reason": "proposal_rejected",
                    "notice": "The LLM response could not be tied safely to the document source steps.",
                    "_llm_call_log": _audit_metadata(payload=payload, locale=locale, status="rejected", response_text=raw_content),
                }
            logger.info(
                "semantic_parse.proposed fragments=%d steps=%d model=%s",
                len(proposal["fragments"]),
                len(proposal["steps"]),
                config.llm_model,
            )
            return proposal, {
                "status": "proposed",
                "reason": "",
                "notice": "Source-bound LLM structure proposal available.",
                "_llm_call_log": _audit_metadata(payload=payload, locale=locale, status="proposed", response_text=raw_content, http_status=response.status_code),
            }
    except httpx.HTTPStatusError as exc:
        reason = "provider_authentication_failed" if exc.response.status_code in {401, 403} else "provider_request_failed"
        logger.warning(
            "semantic_parse.unavailable reason=%s provider=%s model=%s http_status=%s",
            reason,
            config.llm_provider_host,
            config.llm_model,
            exc.response.status_code,
        )
        return None, {
            "status": "unavailable",
            "reason": reason,
            "notice": "The configured semantic-parser provider did not accept this request. Check the server-side LLM configuration.",
            "_llm_call_log": _audit_metadata(payload=payload, locale=locale, status="provider_error", response_text=exc.response.text[:20000], http_status=exc.response.status_code, error_type=type(exc).__name__),
        }
    except (httpx.HTTPError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        logger.warning(
            "semantic_parse.unavailable reason=provider_request_failed provider=%s model=%s error_type=%s",
            config.llm_provider_host,
            config.llm_model,
            type(exc).__name__,
        )
        return None, {
            "status": "unavailable",
            "reason": "provider_request_failed",
            "notice": "The semantic-parser provider was unavailable; heuristic structure is shown instead.",
            "_llm_call_log": _audit_metadata(payload=payload, locale=locale, status="provider_error", error_type=type(exc).__name__),
        }


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
    existing_edges = {
        (edge.get("from_step_id"), edge.get("to_step_id"), edge.get("kind"))
        for edge in graph.get("dependencies", [])
    }
    semantic_edge_count = 0
    for annotation in proposal["steps"]:
        target_id = annotation["step_id"]
        for source_id in annotation["depends_on"]:
            source = by_id[source_id]
            target = by_id[target_id]
            source_role = source.get("semantic_role", "")
            if source_role == "hypothesis":
                kind, edge_status = "requires_assumption", "declared"
            elif source_role == "definition":
                kind, edge_status = "uses_definition", "declared"
            elif source_role == "lemma":
                kind, edge_status = "justifies", "declared"
            else:
                kind, edge_status = "derives", "not_checked"
            key = (source_id, target_id, kind)
            if key in existing_edges:
                continue
            edge_id = sha256(f"{graph.get('content_hash', '')}:{source_id}:{target_id}:{kind}:semantic".encode("utf-8")).hexdigest()[:16]
            graph.setdefault("dependencies", []).append({
                "id": f"edge_semantic_{edge_id}",
                "from_step_id": source_id,
                "to_step_id": target_id,
                "kind": kind,
                "edge_status": edge_status,
                "reason": f"Source-bound semantic dependency: {annotation['rationale']}",
                "semantic_proposal": True,
            })
            existing_edges.add(key)
            semantic_edge_count += 1
    graph["semantic_proposal"] = {
        "status": "proposed",
        "model": config.llm_model,
        "fragments": proposal["fragments"],
        "edge_count": semantic_edge_count,
        "notice": "LLM structure is a source-bound proposal; only rule validators or execution evidence may establish verification.",
    }
    graph.setdefault("limitations", []).append(
        "Semantic roles are LLM proposals bound to source steps; they do not constitute mathematical verification."
    )
    return graph
