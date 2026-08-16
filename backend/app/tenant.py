"""Tenant isolation for Exobrain.

Exobrain does not know users. The orchestrator (or OSS docker) supplies a
project id. Missing header → single-tenant "local" for the open-source shell.
"""

from __future__ import annotations

from fastapi import Header


def get_project_id(
    x_project_id: str | None = Header(default=None, alias="X-Project-Id"),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> str:
    """Resolve the acting project.

    Prefer X-Project-Id. X-User-Id is accepted only as a transition alias so
    existing tests and older proxies keep working; new callers must send
    X-Project-Id.
    """
    value = (x_project_id or x_user_id or "local").strip()
    return value or "local"
