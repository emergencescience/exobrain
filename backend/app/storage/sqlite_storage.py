"""SQLite storage backend for Exobrain offline / open-source version."""

import json
import logging
import os
import secrets
import sqlite3
import threading
from datetime import datetime, timezone

from app.storage import (
    ClaimEvidenceLink,
    Document,
    ExecutionArtifact,
    LLMCallLog,
    Snapshot,
    SnapshotShare,
)

logger = logging.getLogger("exobrain.storage.sqlite")


class SQLiteStorage:
    """Thread-safe SQLite storage using WAL mode."""

    def __init__(self, db_path: str = "app/data/exobrain.db"):
        self.db_path = db_path
        self._lock = threading.Lock()

    async def init(self):
        """Ensure database and tables exist."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL DEFAULT 'local',
                    title TEXT NOT NULL DEFAULT 'Untitled Paper',
                    markdown TEXT NOT NULL DEFAULT '',
                    messages TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS snapshots (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                    markdown TEXT NOT NULL DEFAULT '',
                    messages TEXT NOT NULL DEFAULT '[]',
                    content_hash TEXT NOT NULL DEFAULT '',
                    verification_results TEXT NOT NULL DEFAULT '[]',
                    verification_scope TEXT NOT NULL DEFAULT '{}',
                    proof_graph TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_docs_user ON documents(user_id, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_snaps_doc ON snapshots(document_id, created_at DESC);
                CREATE TABLE IF NOT EXISTS snapshot_shares (
                    token TEXT PRIMARY KEY,
                    snapshot_id TEXT NOT NULL REFERENCES snapshots(id) ON DELETE CASCADE,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_snapshot_shares_snapshot ON snapshot_shares(snapshot_id);
                CREATE TABLE IF NOT EXISTS execution_artifacts (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                    code TEXT NOT NULL,
                    code_hash TEXT NOT NULL,
                    stdout TEXT NOT NULL DEFAULT '',
                    stderr TEXT NOT NULL DEFAULT '',
                    exit_code INTEGER NOT NULL,
                    truncated INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS claim_evidence_links (
                    id TEXT PRIMARY KEY,
                    snapshot_id TEXT NOT NULL REFERENCES snapshots(id) ON DELETE CASCADE,
                    claim_id TEXT NOT NULL,
                    artifact_id TEXT NOT NULL REFERENCES execution_artifacts(id) ON DELETE CASCADE,
                    created_at TEXT NOT NULL,
                    UNIQUE(snapshot_id, claim_id, artifact_id)
                );
                CREATE INDEX IF NOT EXISTS idx_execution_artifacts_doc
                    ON execution_artifacts(document_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_claim_evidence_snapshot
                    ON claim_evidence_links(snapshot_id, claim_id);
                CREATE TABLE IF NOT EXISTS llm_call_logs (
                    id TEXT PRIMARY KEY,
                    document_id TEXT REFERENCES documents(id) ON DELETE SET NULL,
                    source_hash TEXT NOT NULL DEFAULT '',
                    call_name TEXT NOT NULL,
                    system_prompt_name TEXT NOT NULL,
                    provider TEXT NOT NULL DEFAULT '',
                    model TEXT NOT NULL DEFAULT '',
                    request_payload TEXT NOT NULL DEFAULT '{}',
                    response_text TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL,
                    http_status INTEGER,
                    error_type TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_llm_call_logs_document
                    ON llm_call_logs(document_id, created_at DESC);
            """)
            snapshot_columns = {
                row[1] for row in conn.execute("PRAGMA table_info(snapshots)").fetchall()
            }
            if "content_hash" not in snapshot_columns:
                conn.execute("ALTER TABLE snapshots ADD COLUMN content_hash TEXT NOT NULL DEFAULT ''")
            if "verification_results" not in snapshot_columns:
                conn.execute(
                    "ALTER TABLE snapshots ADD COLUMN verification_results TEXT NOT NULL DEFAULT '[]'"
                )
            if "verification_scope" not in snapshot_columns:
                conn.execute(
                    "ALTER TABLE snapshots ADD COLUMN verification_scope TEXT NOT NULL DEFAULT '{}'"
                )
            if "proof_graph" not in snapshot_columns:
                conn.execute(
                    "ALTER TABLE snapshots ADD COLUMN proof_graph TEXT NOT NULL DEFAULT '{}'"
                )
            conn.commit()
            conn.close()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _row_to_doc(self, row: tuple) -> Document:
        """Convert a row tuple to Document, parsing JSON."""
        id_, user_id, title, markdown, messages_raw, created_at, updated_at = row
        try:
            messages = json.loads(messages_raw)
        except (json.JSONDecodeError, TypeError):
            messages = []
        return Document(
            id=id_, user_id=user_id, title=title, markdown=markdown,
            messages=messages, created_at=created_at, updated_at=updated_at,
        )

    # ── Document CRUD ────────────────────────────────────────────────

    async def create_document(self, user_id: str = "local", title: str = "Untitled Paper") -> Document:
        doc = Document(user_id=user_id, title=title)
        now = self._now()
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                "INSERT INTO documents (id, user_id, title, markdown, messages, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                (doc.id, user_id, title, "", "[]", now, now),
            )
            conn.commit()
            conn.close()
        doc.created_at = now
        doc.updated_at = now
        return doc

    async def list_documents(self, user_id: str = "local") -> list[Document]:
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            rows = conn.execute(
                "SELECT id, user_id, title, markdown, messages, created_at, updated_at FROM documents WHERE user_id=? ORDER BY updated_at DESC",
                (user_id,),
            ).fetchall()
            conn.close()
        return [self._row_to_doc(r) for r in rows]

    async def get_document(self, doc_id: str) -> Document | None:
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            row = conn.execute(
                "SELECT id, user_id, title, markdown, messages, created_at, updated_at FROM documents WHERE id=?",
                (doc_id,),
            ).fetchone()
            conn.close()
        if row is None:
            return None
        return self._row_to_doc(row)

    async def update_document(self, doc_id: str, markdown: str, messages: list[dict], title: str | None = None) -> Document | None:
        now = self._now()
        messages_json = json.dumps(messages, ensure_ascii=False)
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            if title is not None:
                conn.execute(
                    "UPDATE documents SET markdown=?, messages=?, title=?, updated_at=? WHERE id=?",
                    (markdown, messages_json, title, now, doc_id),
                )
            else:
                conn.execute(
                    "UPDATE documents SET markdown=?, messages=?, updated_at=? WHERE id=?",
                    (markdown, messages_json, now, doc_id),
                )
            conn.commit()
            # Fetch updated row
            row = conn.execute(
                "SELECT id, user_id, title, markdown, messages, created_at, updated_at FROM documents WHERE id=?",
                (doc_id,),
            ).fetchone()
            conn.close()
        if row is None:
            return None
        return self._row_to_doc(row)

    async def delete_document(self, doc_id: str) -> bool:
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            conn.execute("DELETE FROM snapshots WHERE document_id=?", (doc_id,))
            cursor = conn.execute("DELETE FROM documents WHERE id=?", (doc_id,))
            conn.commit()
            deleted = cursor.rowcount > 0
            conn.close()
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
        now = self._now()
        messages_json = json.dumps(messages, ensure_ascii=False)
        results_json = json.dumps(snap.verification_results, ensure_ascii=False)
        scope_json = json.dumps(snap.verification_scope, ensure_ascii=False)
        proof_graph_json = json.dumps(snap.proof_graph, ensure_ascii=False)
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                """
                INSERT INTO snapshots
                    (id, document_id, markdown, messages, content_hash, verification_results, verification_scope, proof_graph, created_at)
                VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (snap.id, doc_id, markdown, messages_json, content_hash, results_json, scope_json, proof_graph_json, now),
            )
            conn.commit()
            conn.close()
        snap.created_at = now
        return snap

    async def list_snapshots(self, doc_id: str) -> list[Snapshot]:
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            rows = conn.execute(
                """
                SELECT id, document_id, markdown, messages, content_hash, verification_results, verification_scope, proof_graph, created_at
                FROM snapshots WHERE document_id=? ORDER BY created_at DESC
                """,
                (doc_id,),
            ).fetchall()
            conn.close()
        results = []
        for row in rows:
            id_, doc_id_, markdown, messages_raw, content_hash, results_raw, scope_raw, graph_raw, created_at = row
            try:
                messages = json.loads(messages_raw)
            except (json.JSONDecodeError, TypeError):
                messages = []
            try:
                verification_results = json.loads(results_raw)
            except (json.JSONDecodeError, TypeError):
                verification_results = []
            try:
                verification_scope = json.loads(scope_raw)
            except (json.JSONDecodeError, TypeError):
                verification_scope = {"kind": "document"}
            try:
                proof_graph = json.loads(graph_raw)
            except (json.JSONDecodeError, TypeError):
                proof_graph = {"schema_version": "proof-dependency-graph-v1", "fragments": [], "dependencies": []}
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
        """Restore a document to a snapshot state. Creates a NEW snapshot of current state first."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            # Get snapshot
            snap_row = conn.execute(
                "SELECT markdown, messages FROM snapshots WHERE id=? AND document_id=?",
                (snapshot_id, doc_id),
            ).fetchone()
            if snap_row is None:
                conn.close()
                return None

            snap_markdown, snap_messages_raw = snap_row
            now = self._now()

            # Save current state as snapshot first (so restore is undoable)
            current = conn.execute("SELECT markdown, messages FROM documents WHERE id=?", (doc_id,)).fetchone()
            if current:
                import uuid
                conn.execute(
                    "INSERT INTO snapshots (id, document_id, markdown, messages, created_at) VALUES (?,?,?,?,?)",
                    (str(uuid.uuid4()), doc_id, current[0], current[1], now),
                )

            # Restore
            conn.execute(
                "UPDATE documents SET markdown=?, messages=?, updated_at=? WHERE id=?",
                (snap_markdown, snap_messages_raw, now, doc_id),
            )
            conn.commit()

            # Fetch restored doc
            row = conn.execute(
                "SELECT id, user_id, title, markdown, messages, created_at, updated_at FROM documents WHERE id=?",
                (doc_id,),
            ).fetchone()
            conn.close()

        return self._row_to_doc(row)

    # ── Read-only snapshot sharing ────────────────────────────────────

    async def create_snapshot_share(self, snapshot_id: str) -> SnapshotShare:
        share = SnapshotShare(token=secrets.token_urlsafe(24), snapshot_id=snapshot_id)
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                "INSERT INTO snapshot_shares (token, snapshot_id, created_at) VALUES (?,?,?)",
                (share.token, share.snapshot_id, share.created_at),
            )
            conn.commit()
            conn.close()
        return share

    async def get_shared_snapshot(self, token: str) -> Snapshot | None:
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            row = conn.execute(
                """
                SELECT s.id, s.document_id, s.markdown, s.messages, s.content_hash,
                       s.verification_results, s.verification_scope, s.proof_graph, s.created_at
                FROM snapshot_shares sh
                JOIN snapshots s ON s.id = sh.snapshot_id
                WHERE sh.token=?
                """,
                (token,),
            ).fetchone()
            conn.close()
        if row is None:
            return None
        id_, doc_id, markdown, messages_raw, content_hash, results_raw, scope_raw, graph_raw, created_at = row
        try:
            messages = json.loads(messages_raw)
        except (json.JSONDecodeError, TypeError):
            messages = []
        try:
            results = json.loads(results_raw)
        except (json.JSONDecodeError, TypeError):
            results = []
        return Snapshot(
            id=id_,
            document_id=doc_id,
            markdown=markdown,
            messages=messages,
            content_hash=content_hash or "",
            verification_results=results,
            verification_scope=json.loads(scope_raw) if scope_raw else {"kind": "document"},
            proof_graph=json.loads(graph_raw) if graph_raw else {"schema_version": "proof-dependency-graph-v1", "fragments": [], "dependencies": []},
            created_at=created_at,
        )

    async def revoke_snapshot_share(self, snapshot_id: str, token: str) -> bool:
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute(
                "DELETE FROM snapshot_shares WHERE token=? AND snapshot_id=?",
                (token, snapshot_id),
            )
            conn.commit()
            deleted = cursor.rowcount > 0
            conn.close()
        return deleted

    # ── Execution evidence ────────────────────────────────────────────

    async def save_execution_artifact(self, artifact: ExecutionArtifact) -> ExecutionArtifact:
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                """
                INSERT INTO execution_artifacts
                    (id, document_id, code, code_hash, stdout, stderr, exit_code, truncated, created_at)
                VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (
                    artifact.id,
                    artifact.document_id,
                    artifact.code,
                    artifact.code_hash,
                    artifact.stdout,
                    artifact.stderr,
                    artifact.exit_code,
                    int(artifact.truncated),
                    artifact.created_at,
                ),
            )
            conn.commit()
            conn.close()
        return artifact

    async def get_execution_artifact(self, artifact_id: str) -> ExecutionArtifact | None:
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            row = conn.execute(
                """
                SELECT id, document_id, code, code_hash, stdout, stderr, exit_code, truncated, created_at
                FROM execution_artifacts WHERE id=?
                """,
                (artifact_id,),
            ).fetchone()
            conn.close()
        if row is None:
            return None
        return ExecutionArtifact(
            id=row[0],
            document_id=row[1],
            code=row[2],
            code_hash=row[3],
            stdout=row[4],
            stderr=row[5],
            exit_code=row[6],
            truncated=bool(row[7]),
            created_at=row[8],
        )

    async def link_claim_evidence(self, link: ClaimEvidenceLink) -> ClaimEvidenceLink:
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                """
                INSERT OR IGNORE INTO claim_evidence_links
                    (id, snapshot_id, claim_id, artifact_id, created_at)
                VALUES (?,?,?,?,?)
                """,
                (link.id, link.snapshot_id, link.claim_id, link.artifact_id, link.created_at),
            )
            conn.commit()
            conn.close()
        return link

    async def list_claim_evidence(self, snapshot_id: str) -> list[ClaimEvidenceLink]:
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            rows = conn.execute(
                """
                SELECT id, snapshot_id, claim_id, artifact_id, created_at
                FROM claim_evidence_links WHERE snapshot_id=? ORDER BY created_at
                """,
                (snapshot_id,),
            ).fetchall()
            conn.close()
        return [
            ClaimEvidenceLink(
                id=row[0],
                snapshot_id=row[1],
                claim_id=row[2],
                artifact_id=row[3],
                created_at=row[4],
            )
            for row in rows
        ]

    async def save_llm_call_log(self, log: LLMCallLog) -> LLMCallLog:
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                """
                INSERT INTO llm_call_logs
                    (id, document_id, source_hash, call_name, system_prompt_name, provider, model,
                     request_payload, response_text, status, http_status, error_type, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    log.id, log.document_id or None, log.source_hash, log.call_name, log.system_prompt_name,
                    log.provider, log.model, json.dumps(log.request_payload, ensure_ascii=False),
                    log.response_text, log.status, log.http_status, log.error_type, log.created_at,
                ),
            )
            conn.commit()
            conn.close()
        return log

    async def list_llm_call_logs(self, document_id: str, limit: int = 50) -> list[LLMCallLog]:
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            rows = conn.execute(
                """SELECT id, document_id, source_hash, call_name, system_prompt_name, provider, model,
                          request_payload, response_text, status, http_status, error_type, created_at
                   FROM llm_call_logs WHERE document_id=? ORDER BY created_at DESC LIMIT ?""",
                (document_id, min(max(limit, 1), 200)),
            ).fetchall()
            conn.close()
        return [LLMCallLog(
            id=row[0], document_id=row[1] or "", source_hash=row[2], call_name=row[3],
            system_prompt_name=row[4], provider=row[5], model=row[6],
            request_payload=json.loads(row[7] or "{}"), response_text=row[8], status=row[9],
            http_status=row[10], error_type=row[11], created_at=row[12],
        ) for row in rows]
