# Copyright (c) 2026 Symbol Science. All rights reserved.
"""Schema-constrained LLM proposals for local proof-fragment structure.

This module never marks a mathematical relationship verified.  It only proposes
semantic roles, groupings, and which bounded deterministic rule could be tried.
All proposals are validated against existing source-step IDs and source spans.
"""
from __future__ import annotations

import json
import logging
import re
from hashlib import sha256
from typing import Any

import httpx

from app.config import config
from app.prompt_loader import SEMANTIC_PROOF_SYSTEM_PROMPT_FILE, load_system_prompt

logger = logging.getLogger("exobrain.semantic_proof")

SEMANTIC_PROOF_SYSTEM_PROMPT_NAME = SEMANTIC_PROOF_SYSTEM_PROMPT_FILE
SEMANTIC_PROOF_SYSTEM_PROMPT = load_system_prompt(SEMANTIC_PROOF_SYSTEM_PROMPT_NAME)

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


def _response_audit_excerpt(response: httpx.Response | None, error: Exception) -> tuple[str, int | None]:
    """Return a bounded diagnostic for a failed semantic-parser response.

    A JSON decoding failure can happen after a successful HTTP status. Persisting
    only the provider body formerly made an empty body indistinguishable from an
    unrecorded response, so record body text when present and safe transport
    metadata otherwise. Request credentials and headers are never persisted.
    """
    if response is None:
        return (
            f"[no HTTP response; parser_error={type(error).__name__}: {error}]"[:20000],
            None,
        )
    try:
        response_text = response.text
    except Exception as response_text_error:  # pragma: no cover - defensive guard
        response_text = f"[response body unreadable: {type(response_text_error).__name__}: {response_text_error}]"
    if response_text:
        return response_text[:20000], response.status_code
    content_type = response.headers.get("content-type", "<missing>")
    return (
        f"[empty provider response body; http_status={response.status_code}; "
        f"content_type={content_type}; parser_error={type(error).__name__}: {error}]"[:20000],
        response.status_code,
    )

_ROLES = {"context", "definition", "hypothesis", "lemma", "calculation", "deduction", "conclusion"}
_TARGETS = {"none", "semantic", "sympy", "rule"}
_ROLE_ALIASES = {
    "assumption": "hypothesis",
    "claim": "deduction",
    "statement": "deduction",
    "theorem": "lemma",
    "theorem_application": "lemma",
    "derivation": "calculation",
    "proof": "calculation",
}
_TARGET_ALIASES = {
    "": "none",
    "llm": "semantic",
    "llm_review": "semantic",
    "semantic_review": "semantic",
    "structural": "semantic",
    "deterministic": "sympy",
    "verify": "semantic",
}
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
    """Normalize a provider proposal while keeping every accepted reference source-bound.

    Strict JSON Schema remains the preferred transport. The JSON-only fallback for
    compatible providers is deliberately tolerant of role aliases and drops an
    invalid item rather than losing an otherwise source-bound proposal. It never
    invents or rewrites source IDs, and it never turns an LLM decision into proof
    evidence.
    """
    known = {step["id"] for step in _source_payload(graph)}
    raw_steps = raw.get("steps")
    raw_fragments = raw.get("fragments")
    # DeepSeek JSON Object mode may return a compact fragment-only proposal even
    # when instructed to include `steps`. Expand it only when every referenced
    # source ID is already present in this document; fragment IDs never escape
    # this normalization boundary.
    if not isinstance(raw_steps, list) and isinstance(raw_fragments, list):
        fragment_sources: dict[str, list[str]] = {}
        for index, item in enumerate(raw_fragments):
            if not isinstance(item, dict):
                continue
            source_ids = item.get("source_ids", item.get("step_ids", []))
            if isinstance(source_ids, str):
                source_ids = [source_ids]
            valid_ids = [source_id for source_id in source_ids if isinstance(source_id, str) and source_id in known]
            fragment_sources[str(item.get("id", f"fragment_{index}"))] = valid_ids
        expanded_steps: list[dict[str, Any]] = []
        expanded_fragments: list[dict[str, Any]] = []
        for index, item in enumerate(raw_fragments):
            if not isinstance(item, dict):
                continue
            fragment_id = str(item.get("id", f"fragment_{index}"))
            source_ids = fragment_sources.get(fragment_id, [])
            if not source_ids:
                continue
            raw_dependencies = item.get("depends_on", [])
            if isinstance(raw_dependencies, str):
                raw_dependencies = [raw_dependencies]
            if not isinstance(raw_dependencies, list):
                raw_dependencies = []
            dependencies: list[str] = []
            for dependency in raw_dependencies:
                if isinstance(dependency, str) and dependency in known:
                    dependencies.append(dependency)
                elif isinstance(dependency, str) and fragment_sources.get(dependency):
                    dependencies.append(fragment_sources[dependency][-1])
            role = item.get("role", item.get("kind", "context"))
            target = item.get("verification_target", item.get("target", "none"))
            expanded_fragments.append({
                "title": item.get("title", item.get("name", fragment_id)),
                "role": role,
                "step_ids": source_ids,
            })
            for source_id in source_ids:
                expanded_steps.append({
                    "step_id": source_id,
                    "role": role,
                    "verification_target": target,
                    "rule_id": item.get("rule_id", item.get("rule", "")),
                    "depends_on": dependencies if source_id == source_ids[-1] else [],
                    "rationale": item.get("rationale", item.get("reason", "")),
                })
        raw_steps = expanded_steps
        raw_fragments = expanded_fragments
    if not isinstance(raw_steps, list):
        return None
    normalized_steps: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw_steps:
        if not isinstance(item, dict):
            continue
        step_id = item.get("step_id", item.get("id"))
        if not isinstance(step_id, str) or step_id not in known or step_id in seen:
            continue
        raw_role = str(item.get("role", item.get("kind", "context"))).strip().lower()
        role = _ROLE_ALIASES.get(raw_role, raw_role)
        if role not in _ROLES:
            role = "context"
        raw_target = str(item.get("verification_target", item.get("target", "none"))).strip().lower()
        target = _TARGET_ALIASES.get(raw_target, raw_target)
        if target not in _TARGETS:
            target = "none" if role in {"context", "definition", "hypothesis", "lemma"} else "semantic"
        dependencies = item.get("depends_on", item.get("dependencies", []))
        if isinstance(dependencies, str):
            dependencies = [dependencies]
        if not isinstance(dependencies, list):
            dependencies = []
        source_dependencies = [dep for dep in dependencies if isinstance(dep, str) and dep in known and dep != step_id]
        seen.add(step_id)
        normalized_steps.append({
            "step_id": step_id,
            "role": role,
            "verification_target": target,
            "rule_id": str(item.get("rule_id", item.get("rule", "")))[:120],
            "depends_on": source_dependencies,
            "rationale": str(item.get("rationale", item.get("reason", "")))[:500],
        })
    if not normalized_steps:
        return None
    normalized_fragments: list[dict[str, Any]] = []
    if isinstance(raw_fragments, list):
        for item in raw_fragments:
            if not isinstance(item, dict):
                continue
            raw_role = str(item.get("role", item.get("kind", "context"))).strip().lower()
            role = _ROLE_ALIASES.get(raw_role, raw_role)
            if role not in _ROLES:
                role = "context"
            step_ids = item.get("step_ids", item.get("steps", []))
            if isinstance(step_ids, str):
                step_ids = [step_ids]
            if not isinstance(step_ids, list):
                continue
            source_ids = [step_id for step_id in step_ids if isinstance(step_id, str) and step_id in known]
            if not source_ids:
                continue
            normalized_fragments.append({
                "title": str(item.get("title", item.get("name", "Untitled semantic fragment")))[:160],
                "role": role,
                "step_ids": source_ids,
            })
    if not normalized_fragments:
        normalized_fragments = [{
            "title": "Source-bound semantic units",
            "role": "context",
            "step_ids": [item["step_id"] for item in normalized_steps],
        }]
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
    response: httpx.Response | None = None
    try:
        # Semantic parsing augments deterministic verification; it must never make
        # a researcher wait on an unbounded reasoning completion. DeepSeek's
        # OpenAI-compatible endpoint rejects JSON Schema and can otherwise spend
        # minutes producing a tiny JSON proposal after sending response headers.
        provider_without_json_schema = config.llm_provider_host.endswith("deepseek.com")
        timeout = httpx.Timeout(connect=5.0, read=15.0, write=10.0, pool=5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            request_payload = {
                "model": config.llm_model,
                "temperature": 0,
                "max_tokens": 1200,
                "messages": [
                    {"role": "system", "content": SEMANTIC_PROOF_SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps({"locale": locale, "source_steps": payload}, ensure_ascii=False)},
                ],
            }
            if provider_without_json_schema:
                # DeepSeek documents JSON Object (not JSON Schema) and enables
                # high-effort thinking by default. Structural classification is
                # deliberately a short, non-reasoning operation; the deterministic
                # verifier remains the authority for mathematical evidence.
                request_payload["thinking"] = {"type": "disabled"}
                request_payload["response_format"] = {"type": "json_object"}
                structured_transport = "json_object"
            else:
                request_payload["response_format"] = {"type": "json_schema", "json_schema": {"name": "semantic_proof_structure", "strict": True, "schema": _SCHEMA}}
                structured_transport = "json_schema"
            logger.info(
                "semantic_parse.transport provider=%s structured_transport=%s max_tokens=%d read_timeout_seconds=%d",
                config.llm_provider_host,
                structured_transport,
                request_payload["max_tokens"],
                15,
            )
            response = await client.post(
                config.llm_chat_completions_url,
                headers={"Authorization": f"Bearer {config.llm_api_key}", "Content-Type": "application/json"},
                json=request_payload,
            )
            # DeepSeek and some OpenAI-compatible gateways reject JSON Schema.
            # Retry once without the transport feature; validate the returned JSON
            # locally against the same source-bound contract instead.
            if "response_format" in request_payload and response.status_code == 400 and "response_format type is unavailable" in response.text.lower():
                logger.info(
                    "semantic_parse.response_format_fallback provider=%s model=%s",
                    config.llm_provider_host,
                    config.llm_model,
                )
                fallback_payload = {
                    key: value for key, value in request_payload.items()
                    if key != "response_format"
                }
                response = await client.post(
                    config.llm_chat_completions_url,
                    headers={"Authorization": f"Bearer {config.llm_api_key}", "Content-Type": "application/json"},
                    json=fallback_payload,
                )
            response.raise_for_status()
            raw_content = response.json()["choices"][0]["message"]["content"]
            logger.info(
                "semantic_parse.response_received provider=%s model=%s content_chars=%d",
                config.llm_provider_host,
                config.llm_model,
                len(raw_content) if isinstance(raw_content, str) else 0,
            )
            if not isinstance(raw_content, str):
                raise ValueError("provider response did not contain text content")
            parsed_content = json.loads(raw_content.removeprefix("```json").removeprefix("```").removesuffix("```").strip())
            logger.info("semantic_parse.response_json_valid provider=%s model=%s", config.llm_provider_host, config.llm_model)
            proposal = validate_semantic_proposal(parsed_content, graph)
            logger.info(
                "semantic_parse.response_validated provider=%s model=%s proposal_available=%s",
                config.llm_provider_host,
                config.llm_model,
                proposal is not None,
            )
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
        response_text, http_status = _response_audit_excerpt(exc.response, exc)
        logger.warning(
            "semantic_parse.unavailable reason=%s provider=%s model=%s http_status=%s",
            reason,
            config.llm_provider_host,
            config.llm_model,
            http_status,
        )
        return None, {
            "status": "unavailable",
            "reason": reason,
            "notice": "The configured semantic-parser provider did not accept this request. Check the server-side LLM configuration.",
            "_llm_call_log": _audit_metadata(payload=payload, locale=locale, status="provider_error", response_text=response_text, http_status=http_status, error_type=type(exc).__name__),
        }
    except (httpx.HTTPError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        response_text, http_status = _response_audit_excerpt(response, exc)
        logger.warning(
            "semantic_parse.unavailable reason=provider_request_failed provider=%s model=%s error_type=%s http_status=%s",
            config.llm_provider_host,
            config.llm_model,
            type(exc).__name__,
            http_status,
        )
        return None, {
            "status": "unavailable",
            "reason": "provider_request_failed",
            "notice": "The semantic-parser provider was unavailable; heuristic structure is shown instead.",
            "_llm_call_log": _audit_metadata(payload=payload, locale=locale, status="provider_error", response_text=response_text, http_status=http_status, error_type=type(exc).__name__),
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
        if annotation["role"] in {"context", "definition", "hypothesis", "lemma"} and annotation["verification_target"] == "none":
            step["local_status"] = "not_required"
        elif annotation["role"] == "calculation" and annotation["verification_target"] == "semantic":
            # A model-approved structural calculation is useful review context,
            # but deliberately distinct from deterministic mathematical proof.
            step["local_status"] = "semantically_reviewed"
    existing_edges = {
        (edge.get("from_step_id"), edge.get("to_step_id"), edge.get("kind")): edge
        for edge in graph.get("dependencies", [])
    }
    semantic_edge_count = 0
    for annotation in proposal["steps"]:
        target_id = annotation["step_id"]
        for source_id in annotation["depends_on"]:
            source = by_id[source_id]
            target = by_id[target_id]
            source_role = source.get("semantic_role", "")
            source_text = source.get("text", "")
            missing_function_declaration = (
                (r"\mathrm{d}x" in source_text or " dx" in source_text)
                and bool(re.search(r"(?:令|let)\s*\$?x\s*=", source_text, re.IGNORECASE))
                and not bool(re.search(r"x\s*\(", source_text))
            )
            if missing_function_declaration:
                kind, edge_status = "requires_assumption", "declared"
                reason = "The substitution uses differential notation but does not explicitly declare the substituted variable as a function of the parameter (for example, x(t)=…)."
            elif annotation["verification_target"] == "semantic":
                kind = {
                    "hypothesis": "requires_assumption",
                    "definition": "uses_definition",
                    "lemma": "justifies",
                }.get(source_role, "derives")
                edge_status = "semantically_reviewed"
                reason = f"Source-bound structural review: {annotation['rationale']}"
            elif source_role == "hypothesis":
                kind, edge_status = "requires_assumption", "declared"
                reason = f"Source-bound semantic dependency: {annotation['rationale']}"
            elif source_role == "definition":
                kind, edge_status = "uses_definition", "declared"
                reason = f"Source-bound semantic dependency: {annotation['rationale']}"
            elif source_role == "lemma":
                kind, edge_status = "justifies", "declared"
                reason = f"Source-bound semantic dependency: {annotation['rationale']}"
            else:
                kind, edge_status = "derives", "not_checked"
                reason = f"Source-bound semantic dependency: {annotation['rationale']}"
            key = (source_id, target_id, kind)
            existing = existing_edges.get(key)
            if existing is None:
                # A source-order heuristic may have the same endpoints but a
                # generic `derives` kind. Upgrade that edge in place rather than
                # duplicating one reader-visible card for the same relation.
                existing = next((
                    edge for edge in graph.get("dependencies", [])
                    if edge.get("from_step_id") == source_id and edge.get("to_step_id") == target_id
                ), None)
            if existing is not None:
                # Replace a sequence-only edge with the model's explicit,
                # source-bound relation instead of silently discarding it.
                existing.update({
                    "kind": kind,
                    "edge_status": edge_status,
                    "reason": reason,
                    "semantic_proposal": True,
                    "review_visible": True,
                })
                existing_edges[key] = existing
                semantic_edge_count += 1
                continue
            edge_id = sha256(f"{graph.get('content_hash', '')}:{source_id}:{target_id}:{kind}:semantic".encode("utf-8")).hexdigest()[:16]
            edge = {
                "id": f"edge_semantic_{edge_id}",
                "from_step_id": source_id,
                "to_step_id": target_id,
                "kind": kind,
                "edge_status": edge_status,
                "reason": reason,
                "semantic_proposal": True,
                "review_visible": True,
            }
            graph.setdefault("dependencies", []).append(edge)
            existing_edges[key] = edge
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
