"""Unit tests for immutable verification snapshot metadata."""

from __future__ import annotations

import asyncio

from app.storage.sqlite_storage import SQLiteStorage
from app.verify import extract_equations


def run(coro):
    """Run a storage coroutine without requiring pytest-asyncio."""
    return asyncio.run(coro)


def test_extract_equations_reports_source_lines_for_block_and_inline_math():
    markdown = """# Example

Inline claim: $a = b$.

$$
c = d
$$
"""

    equations = extract_equations(markdown)

    assert equations == [
        (3, "a = b", "inline"),
        (5, "c = d", "block"),
    ]


def test_sqlite_snapshot_retains_immutable_verification_provenance(tmp_path):
    async def scenario():
        storage = SQLiteStorage(str(tmp_path / "exobrain.db"))
        await storage.init()
        document = await storage.create_document("researcher-1", "Proof")

        snapshot = await storage.save_snapshot(
            document.id,
            "$$x=x$$",
            [{"role": "user", "content": "Check this claim"}],
            content_hash="content-sha256",
            verification_results=[
                {
                    "claim_id": "claim-123",
                    "line": 1,
                    "end_line": 1,
                    "status": "verified",
                }
            ],
        )

        stored = await storage.list_snapshots(document.id)
        assert len(stored) == 1
        assert stored[0].id == snapshot.id
        assert stored[0].markdown == "$$x=x$$"
        assert stored[0].content_hash == "content-sha256"
        assert stored[0].verification_results == [
            {
                "claim_id": "claim-123",
                "line": 1,
                "end_line": 1,
                "status": "verified",
            }
        ]

    run(scenario())
