"""PostgreSQL storage backend — for Railway production deployment."""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime

from app.storage import (
    ClaimEvidenceLink,
    Document,
    ExecutionArtifact,
    LLMCallLog,
    Snapshot,
)

logger = logging.getLogger("exobrain.storage.postgres")

# Lazy import — production only
_pool = None


def _get_pool():
    """Lazy-init psycopg2 connection pool."""
    global _pool
    if _pool is None:
        import psycopg2
        import psycopg2.pool
        db_url = os.getenv("DATABASE_URL", "")
        if not db_url:
            raise RuntimeError("DATABASE_URL must be set for Postgres storage")
        _pool = psycopg2.pool.ThreadedConnectionPool(1, 10, db_url)
    return _pool


class PostgresStorage:
    """Postgres backend — same interface as SQLiteStorage."""

    async def init(self):
        pool = _get_pool()
        conn = pool.getconn()
        try:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS exobrain_documents (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL DEFAULT 'local',
                    title TEXT NOT NULL DEFAULT 'Untitled Paper',
                    markdown TEXT NOT NULL DEFAULT '',
                    messages JSONB NOT NULL DEFAULT '[]',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS exobrain_snapshots (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL REFERENCES exobrain_documents(id) ON DELETE CASCADE,
                    markdown TEXT NOT NULL DEFAULT '',
                    messages JSONB NOT NULL DEFAULT '[]',
                    content_hash TEXT NOT NULL DEFAULT '',
                    verification_results JSONB NOT NULL DEFAULT '[]',
                    verification_scope JSONB NOT NULL DEFAULT '{}',
                    proof_graph JSONB NOT NULL DEFAULT '{}',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                ALTER TABLE exobrain_snapshots ADD COLUMN IF NOT EXISTS content_hash TEXT NOT NULL DEFAULT '';
                ALTER TABLE exobrain_snapshots ADD COLUMN IF NOT EXISTS verification_results JSONB NOT NULL DEFAULT '[]';
                ALTER TABLE exobrain_snapshots ADD COLUMN IF NOT EXISTS verification_scope JSONB NOT NULL DEFAULT '{}';
                ALTER TABLE exobrain_snapshots ADD COLUMN IF NOT EXISTS proof_graph JSONB NOT NULL DEFAULT '{}';
                CREATE INDEX IF NOT EXISTS idx_exo_docs_user ON exobrain_documents(user_id, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_exo_snaps_doc ON exobrain_snapshots(document_id, created_at DESC);
                CREATE TABLE IF NOT EXISTS exobrain_snapshot_shares (
                    token TEXT PRIMARY KEY,
                    snapshot_id TEXT NOT NULL REFERENCES exobrain_snapshots(id) ON DELETE CASCADE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_exo_snapshot_shares_snapshot
                    ON exobrain_snapshot_shares(snapshot_id);
                CREATE TABLE IF NOT EXISTS exobrain_execution_artifacts (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL REFERENCES exobrain_documents(id) ON DELETE CASCADE,
                    code TEXT NOT NULL,
                    code_hash TEXT NOT NULL,
                    stdout TEXT NOT NULL DEFAULT '',
                    stderr TEXT NOT NULL DEFAULT '',
                    exit_code INTEGER NOT NULL,
                    truncated BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS exobrain_claim_evidence_links (
                    id TEXT PRIMARY KEY,
                    snapshot_id TEXT NOT NULL REFERENCES exobrain_snapshots(id) ON DELETE CASCADE,
                    claim_id TEXT NOT NULL,
                    artifact_id TEXT NOT NULL REFERENCES exobrain_execution_artifacts(id) ON DELETE CASCADE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE(snapshot_id, claim_id, artifact_id)
                );
                CREATE INDEX IF NOT EXISTS idx_exo_execution_artifacts_doc
                    ON exobrain_execution_artifacts(document_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_exo_claim_evidence_snapshot
                    ON exobrain_claim_evidence_links(snapshot_id, claim_id);
                CREATE TABLE IF NOT EXISTS exobrain_llm_call_logs (
                    id TEXT PRIMARY KEY,
                    document_id TEXT REFERENCES exobrain_documents(id) ON DELETE SET NULL,
                    source_hash TEXT NOT NULL DEFAULT '',
                    call_name TEXT NOT NULL,
                    system_prompt_name TEXT NOT NULL,
                    provider TEXT NOT NULL DEFAULT '',
                    model TEXT NOT NULL DEFAULT '',
                    request_payload JSONB NOT NULL DEFAULT '{}',
                    response_text TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL,
                    http_status INTEGER,
                    error_type TEXT NOT NULL DEFAULT '',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_exo_llm_call_logs_document
                    ON exobrain_llm_call_logs(document_id, created_at DESC);
            """)
            conn.commit()
            cur.close()
        finally:
            pool.putconn(conn)

    def _row_to_doc(self, row: tuple) -> Document:
        id_, user_id, title, markdown, messages, created_at, updated_at = row
        if isinstance(messages, str):
            messages = json.loads(messages)
        if isinstance(created_at, datetime):
            created_at = created_at.isoformat()
        if isinstance(updated_at, datetime):
            updated_at = updated_at.isoformat()
        return Document(id=id_, project_id=user_id, title=title, markdown=markdown,
                        messages=messages, created_at=created_at, updated_at=updated_at)

    # ── Document CRUD ────────────────────────────────────────────────

    async def create_document(self, project_id: str = "local", title: str = "Untitled Paper") -> Document:
        doc = Document(project_id=project_id, title=title)
        pool = _get_pool()
        conn = pool.getconn()
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO exobrain_documents (id, user_id, title, markdown, messages) VALUES (%s,%s,%s,%s,%s)",
                (doc.id, project_id, title, "", "[]"),
            )
            conn.commit()
            cur.close()
        finally:
            pool.putconn(conn)
        return doc

    async def list_documents(self, project_id: str = "local") -> list[Document]:
        pool = _get_pool()
        conn = pool.getconn()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, user_id, title, markdown, messages, created_at, updated_at FROM exobrain_documents WHERE user_id=%s ORDER BY updated_at DESC",
                (project_id,),
            )
            rows = cur.fetchall()
            cur.close()
        finally:
            pool.putconn(conn)
        return [self._row_to_doc(r) for r in rows]

    async def get_document(self, doc_id: str) -> Document | None:
        pool = _get_pool()
        conn = pool.getconn()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, user_id, title, markdown, messages, created_at, updated_at FROM exobrain_documents WHERE id=%s",
                (doc_id,),
            )
            row = cur.fetchone()
            cur.close()
        finally:
            pool.putconn(conn)
        if row is None:
            return None
        return self._row_to_doc(row)

    async def update_document(self, doc_id: str, markdown: str, messages: list[dict], title: str | None = None) -> Document | None:
        messages_json = json.dumps(messages, ensure_ascii=False)
        pool = _get_pool()
        conn = pool.getconn()
        try:
            cur = conn.cursor()
            if title is not None:
                cur.execute(
                    "UPDATE exobrain_documents SET markdown=%s, messages=%s, title=%s, updated_at=NOW() WHERE id=%s",
                    (markdown, messages_json, title, doc_id),
                )
            else:
                cur.execute(
                    "UPDATE exobrain_documents SET markdown=%s, messages=%s, updated_at=NOW() WHERE id=%s",
                    (markdown, messages_json, doc_id),
                )
            conn.commit()

            cur.execute(
                "SELECT id, user_id, title, markdown, messages, created_at, updated_at FROM exobrain_documents WHERE id=%s",
                (doc_id,),
            )
            row = cur.fetchone()
            cur.close()
        finally:
            pool.putconn(conn)
        if row is None:
            return None
        return self._row_to_doc(row)

    async def delete_document(self, doc_id: str) -> bool:
        pool = _get_pool()
        conn = pool.getconn()
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM exobrain_snapshots WHERE document_id=%s", (doc_id,))
            cur.execute("DELETE FROM exobrain_documents WHERE id=%s", (doc_id,))
            deleted = cur.rowcount > 0
            conn.commit()
            cur.close()
        finally:
            pool.putconn(conn)
        return deleted

    # ── Snapshots ─────────────────────────────────────────────────────

    async def save_snapshot(
        self,
        doc_id: str,
        markdown: str,
        messages: list[dict],
        *,
        content_hash: str = "",
        verification_results: list[dict] | None = None,
        verification_scope: dict | None = None,
        proof_graph: dict | None = None,
    ) -> Snapshot:
        snap = Snapshot(
            document_id=doc_id,
            markdown=markdown,
            messages=messages,
            content_hash=content_hash,
            verification_results=verification_results or [],
            verification_scope=verification_scope or {"kind": "document"},
            proof_graph=proof_graph or {"schema_version": "proof-dependency-graph-v1", "fragments": [], "dependencies": []},
        )
        messages_json = json.dumps(messages, ensure_ascii=False)
        results_json = json.dumps(snap.verification_results, ensure_ascii=False)
        scope_json = json.dumps(snap.verification_scope, ensure_ascii=False)
        proof_graph_json = json.dumps(snap.proof_graph, ensure_ascii=False)
        pool = _get_pool()
        conn = pool.getconn()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO exobrain_snapshots
                    (id, document_id, markdown, messages, content_hash, verification_results, verification_scope, proof_graph)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (snap.id, doc_id, markdown, messages_json, content_hash, results_json, scope_json, proof_graph_json),
            )
            conn.commit()
            cur.close()
        finally:
            pool.putconn(conn)
        return snap

    async def list_snapshots(self, doc_id: str) -> list[Snapshot]:
        pool = _get_pool()
        conn = pool.getconn()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, document_id, markdown, messages, content_hash, verification_results, verification_scope, proof_graph, created_at
                FROM exobrain_snapshots WHERE document_id=%s ORDER BY created_at DESC
                """,
                (doc_id,),
            )
            rows = cur.fetchall()
            cur.close()
        finally:
            pool.putconn(conn)
        results = []
        for row in rows:
            id_, doc_id_, markdown, messages_raw, content_hash, results_raw, scope_raw, graph_raw, created_at = row
            if isinstance(messages_raw, str):
                messages = json.loads(messages_raw)
            else:
                messages = messages_raw
            if isinstance(results_raw, str):
                verification_results = json.loads(results_raw)
            else:
                verification_results = results_raw or []
            if isinstance(scope_raw, str):
                verification_scope = json.loads(scope_raw)
            else:
                verification_scope = scope_raw or {"kind": "document"}
            if isinstance(graph_raw, str):
                proof_graph = json.loads(graph_raw)
            else:
                proof_graph = graph_raw or {"schema_version": "proof-dependency-graph-v1", "fragments": [], "dependencies": []}
            if isinstance(created_at, datetime):
                created_at = created_at.isoformat()
            results.append(
                Snapshot(
                    id=id_,
                    document_id=doc_id_,
                    markdown=markdown,
                    messages=messages,
                    content_hash=content_hash or "",
                    verification_results=verification_results,
                    verification_scope=verification_scope,
                    proof_graph=proof_graph,
                    created_at=created_at,
                )
            )
        return results

    async def restore_snapshot(self, doc_id: str, snapshot_id: str) -> Document | None:
        pool = _get_pool()
        conn = pool.getconn()
        try:
            cur = conn.cursor()

            # Get snapshot
            cur.execute(
                "SELECT markdown, messages FROM exobrain_snapshots WHERE id=%s AND document_id=%s",
                (snapshot_id, doc_id),
            )
            snap_row = cur.fetchone()
            if snap_row is None:
                cur.close()
                return None

            snap_markdown, snap_messages = snap_row

            # Save current state as snapshot first
            cur.execute(
                "SELECT markdown, messages FROM exobrain_documents WHERE id=%s", (doc_id,),
            )
            current = cur.fetchone()
            if current:
                cur.execute(
                    "INSERT INTO exobrain_snapshots (id, document_id, markdown, messages) VALUES (%s,%s,%s,%s)",
                    (str(uuid.uuid4()), doc_id, current[0],
                     json.dumps(current[1]) if isinstance(current[1], (list, dict)) else str(current[1])),
                )

            cur.execute(
                "UPDATE exobrain_documents SET markdown=%s, messages=%s, updated_at=NOW() WHERE id=%s",
                (snap_markdown, json.dumps(snap_messages) if isinstance(snap_messages, (list, dict)) else str(snap_messages), doc_id),
            )
            conn.commit()

            cur.execute(
                "SELECT id, user_id, title, markdown, messages, created_at, updated_at FROM exobrain_documents WHERE id=%s",
                (doc_id,),
            )
            row = cur.fetchone()
            cur.close()
        finally:
            pool.putconn(conn)
        return self._row_to_doc(row)

    # ── Execution evidence ────────────────────────────────────────────

    async def save_execution_artifact(self, artifact: ExecutionArtifact) -> ExecutionArtifact:
        pool = _get_pool()
        conn = pool.getconn()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO exobrain_execution_artifacts
                    (id, document_id, code, code_hash, stdout, stderr, exit_code, truncated, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    artifact.id, artifact.document_id, artifact.code, artifact.code_hash,
                    artifact.stdout, artifact.stderr, artifact.exit_code,
                    artifact.truncated, artifact.created_at,
                ),
            )
            conn.commit()
            cur.close()
        finally:
            pool.putconn(conn)
        return artifact

    async def get_execution_artifact(self, artifact_id: str) -> ExecutionArtifact | None:
        pool = _get_pool()
        conn = pool.getconn()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, document_id, code, code_hash, stdout, stderr, exit_code, truncated, created_at
                FROM exobrain_execution_artifacts WHERE id=%s
                """,
                (artifact_id,),
            )
            row = cur.fetchone()
            cur.close()
        finally:
            pool.putconn(conn)
        if row is None:
            return None
        created_at = row[8].isoformat() if isinstance(row[8], datetime) else row[8]
        return ExecutionArtifact(
            id=row[0], document_id=row[1], code=row[2], code_hash=row[3],
            stdout=row[4], stderr=row[5], exit_code=row[6],
            truncated=bool(row[7]), created_at=created_at,
        )

    async def link_claim_evidence(self, link: ClaimEvidenceLink) -> ClaimEvidenceLink:
        pool = _get_pool()
        conn = pool.getconn()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO exobrain_claim_evidence_links
                    (id, snapshot_id, claim_id, artifact_id, created_at)
                VALUES (%s,%s,%s,%s,%s)
                ON CONFLICT (snapshot_id, claim_id, artifact_id) DO NOTHING
                """,
                (link.id, link.snapshot_id, link.claim_id, link.artifact_id, link.created_at),
            )
            conn.commit()
            cur.close()
        finally:
            pool.putconn(conn)
        return link

    async def list_claim_evidence(self, snapshot_id: str) -> list[ClaimEvidenceLink]:
        pool = _get_pool()
        conn = pool.getconn()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, snapshot_id, claim_id, artifact_id, created_at
                FROM exobrain_claim_evidence_links WHERE snapshot_id=%s ORDER BY created_at
                """,
                (snapshot_id,),
            )
            rows = cur.fetchall()
            cur.close()
        finally:
            pool.putconn(conn)
        return [
            ClaimEvidenceLink(
                id=row[0], snapshot_id=row[1], claim_id=row[2],
                artifact_id=row[3],
                created_at=row[4].isoformat() if isinstance(row[4], datetime) else row[4],
            )
            for row in rows
        ]

    async def save_llm_call_log(self, log: LLMCallLog) -> LLMCallLog:
        pool = _get_pool()
        conn = pool.getconn()
        try:
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO exobrain_llm_call_logs
                    (id, document_id, source_hash, call_name, system_prompt_name, provider, model,
                     request_payload, response_text, status, http_status, error_type, created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s)""",
                (
                    log.id, log.document_id or None, log.source_hash, log.call_name, log.system_prompt_name,
                    log.provider, log.model, json.dumps(log.request_payload, ensure_ascii=False),
                    log.response_text, log.status, log.http_status, log.error_type, log.created_at,
                ),
            )
            conn.commit()
            cur.close()
        finally:
            pool.putconn(conn)
        return log

    async def list_llm_call_logs(self, document_id: str, limit: int = 50) -> list[LLMCallLog]:
        pool = _get_pool()
        conn = pool.getconn()
        try:
            cur = conn.cursor()
            cur.execute(
                """SELECT id, document_id, source_hash, call_name, system_prompt_name, provider, model,
                          request_payload, response_text, status, http_status, error_type, created_at
                   FROM exobrain_llm_call_logs WHERE document_id=%s ORDER BY created_at DESC LIMIT %s""",
                (document_id, min(max(limit, 1), 200)),
            )
            rows = cur.fetchall()
            cur.close()
        finally:
            pool.putconn(conn)
        logs = []
        for row in rows:
            created_at = row[12].isoformat() if isinstance(row[12], datetime) else row[12]
            logs.append(LLMCallLog(
                id=row[0], document_id=row[1] or "", source_hash=row[2], call_name=row[3],
                system_prompt_name=row[4], provider=row[5], model=row[6], request_payload=row[7] or {},
                response_text=row[8], status=row[9], http_status=row[10], error_type=row[11], created_at=created_at,
            ))
        return logs
