# Copyright (c) 2026 Symbol Science. All rights reserved.
"""Build a bounded, auditable proof dependency graph from Markdown source.

This module intentionally creates *candidate* proof structure.  It never marks a
logical dependency verified solely because adjacent formulae are symbolically
valid; proof-edge status remains explicit until a rule-specific validator exists.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import re
from typing import Any

from app.proof_rules import apply_rule_specific_validators


_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_ASSUMPTION = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)?(?:assumption|assume|given|hypothesis|假设|前提|已知)\b", re.IGNORECASE)
_DEFINITION = re.compile(r"^\s*(?:let|define|set|put|令|定义|设)\b", re.IGNORECASE)
_THEOREM = re.compile(r"\b(?:tonelli|fubini|stokes|green'?s|change of variables|polar coordinates?|substitution theorem)\b|(?:tonelli|fubini|极坐标|变量替换|换元)", re.IGNORECASE)
_CONCLUSION = re.compile(r"^\s*(?:thus|therefore|hence|consequently|so|taking|于是|因此|故|从而)\b", re.IGNORECASE)


@dataclass(frozen=True)
class SourceBlock:
    text: str
    start_line: int
    end_line: int
    section: str
    section_start_line: int


def _stable_id(prefix: str, content_hash: str, start_line: int, text: str) -> str:
    digest = sha256(f"{content_hash}:{prefix}:{start_line}:{text}".encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def _section_kind(title: str) -> str:
    lowered = title.lower()
    if "assumption" in lowered or "hypoth" in lowered or "假设" in title or "前提" in title:
        return "assumptions"
    if "claim" in lowered or "theorem" in lowered or "statement" in lowered or "结论" in title or "命题" in title:
        return "claim"
    if "derivation" in lowered or "proof" in lowered or "argument" in lowered or "推导" in title or "证明" in title:
        return "derivation"
    return "context"


def _classify(block: SourceBlock) -> str:
    text = block.text.strip()
    section_kind = _section_kind(block.section)
    if section_kind == "assumptions" or _ASSUMPTION.search(text):
        return "assumption"
    if _THEOREM.search(text):
        return "theorem_application"
    if _DEFINITION.search(text):
        return "definition"
    if _CONCLUSION.search(text):
        return "conclusion"
    if section_kind == "claim":
        return "statement"
    return "derivation_step"


def _blocks(markdown: str) -> list[SourceBlock]:
    """Split Markdown into bounded semantic source blocks while retaining ranges."""
    lines = markdown.splitlines()
    blocks: list[SourceBlock] = []
    section = "Document"
    section_start = 1
    index = 0
    while index < len(lines):
        line = lines[index]
        heading = _HEADING.match(line)
        if heading:
            section = heading.group(2).strip()
            section_start = index + 1
            index += 1
            continue
        if not line.strip():
            index += 1
            continue
        start = index
        if line.strip().startswith("$$"):
            index += 1
            while index < len(lines):
                if lines[index].strip().startswith("$$"):
                    index += 1
                    break
                index += 1
        else:
            index += 1
            while index < len(lines):
                candidate = lines[index]
                if not candidate.strip() or _HEADING.match(candidate) or candidate.strip().startswith("$$"):
                    break
                index += 1
        text = "\n".join(lines[start:index]).strip()
        if text:
            blocks.append(SourceBlock(text=text, start_line=start + 1, end_line=index, section=section, section_start_line=section_start))
    return blocks


def _result_status(block: SourceBlock, verification_results: list[dict[str, Any]]) -> str:
    overlapping = [
        result for result in verification_results
        if result.get("line", 0) <= block.end_line and result.get("end_line", result.get("line", 0)) >= block.start_line
    ]
    if not overlapping:
        return "not_checked"
    statuses = {str(result.get("status", "inconclusive")) for result in overlapping}
    if "error" in statuses or "failed" in statuses:
        return "failed"
    if statuses == {"verified"}:
        return "locally_verified"
    if "verified" in statuses:
        return "partially_checked"
    return "inconclusive"


def _nearest_assumption(step: dict[str, Any], assumptions: list[dict[str, Any]]) -> dict[str, Any] | None:
    keywords = set(re.findall(r"[a-zA-Z]+|[\u4e00-\u9fff]+", step["text"].lower()))
    prior = [item for item in assumptions if item["source"]["end_line"] <= step["source"]["start_line"]]
    scored: list[tuple[int, dict[str, Any]]] = []
    for item in prior:
        assumption_words = set(re.findall(r"[a-zA-Z]+|[\u4e00-\u9fff]+", item["text"].lower()))
        scored.append((len(keywords & assumption_words), item))
    if not scored:
        return None
    best_score, best = max(scored, key=lambda pair: (pair[0], pair[1]["source"]["start_line"]))
    return best if best_score > 0 or step["kind"] == "theorem_application" else None


def build_proof_graph(markdown: str, verification_results: list[dict[str, Any]]) -> dict[str, Any]:
    """Return local proof fragments and candidate proof dependencies.

    The result is suitable for review and user correction, not a claim of full
    formalization.  `edge_status` is intentionally never `verified` in v1.
    """
    content_hash = sha256(markdown.encode("utf-8")).hexdigest()
    fragments_by_section: dict[tuple[str, int], dict[str, Any]] = {}
    ordered_steps: list[dict[str, Any]] = []
    for block in _blocks(markdown):
        key = (block.section, block.section_start_line)
        fragment = fragments_by_section.get(key)
        if fragment is None:
            fragment = {
                "id": _stable_id("fragment", content_hash, block.section_start_line, block.section),
                "title": block.section,
                "kind": _section_kind(block.section),
                "source": {"start_line": block.section_start_line, "end_line": block.end_line},
                "steps": [],
            }
            fragments_by_section[key] = fragment
        else:
            fragment["source"]["end_line"] = block.end_line
        step = {
            "id": _stable_id("step", content_hash, block.start_line, block.text),
            "kind": _classify(block),
            "text": block.text,
            "source": {"start_line": block.start_line, "end_line": block.end_line},
            "local_status": _result_status(block, verification_results),
            "fragment_id": fragment["id"],
        }
        fragment["steps"].append(step)
        ordered_steps.append(step)

    dependencies: list[dict[str, Any]] = []
    assumptions = [step for step in ordered_steps if step["kind"] == "assumption"]
    prior_step: dict[str, Any] | None = None
    for step in ordered_steps:
        if step["kind"] == "assumption":
            continue
        if prior_step is not None and prior_step["fragment_id"] == step["fragment_id"]:
            dependencies.append({
                "id": _stable_id("edge", content_hash, step["source"]["start_line"], f"{prior_step['id']}->{step['id']}"),
                "from_step_id": prior_step["id"],
                "to_step_id": step["id"],
                "kind": "derives",
                "edge_status": "not_checked",
                "reason": "Candidate local dependency inferred from source order; reviewer confirmation or a rule-specific validator is required.",
            })
        assumption = _nearest_assumption(step, assumptions)
        if assumption is not None:
            dependencies.append({
                "id": _stable_id("edge", content_hash, step["source"]["start_line"], f"{assumption['id']}->{step['id']}:assumption"),
                "from_step_id": assumption["id"],
                "to_step_id": step["id"],
                "kind": "requires_assumption",
                "edge_status": "declared",
                "reason": "An explicit hypothesis is available as a prerequisite; its sufficiency has not been machine-proved.",
            })
        prior_step = step

    graph = {
        "schema_version": "proof-dependency-graph-v1",
        "content_hash": content_hash,
        "fragments": list(fragments_by_section.values()),
        "dependencies": dependencies,
        "limitations": [
            "This is a local candidate proof dependency graph, not a full formal proof AST.",
            "A locally verified expression does not automatically verify its incoming proof dependency.",
        ],
    }
    return apply_rule_specific_validators(graph)
