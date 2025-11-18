"""Unit tests for database layer"""
import pytest
import aiosqlite
import tempfile
import os
from pathlib import Path

from backend.db.connection import Database


class TestDatabase:
    """Test database initialization and operations"""

    @pytest.mark.asyncio
    async def test_database_initialization(self):
        """Test database can be initialized"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create temp database
            db = Database()
            db.db_path = Path(tmpdir) / "test.db"

            # Initialize schema
            await db.init_db()

            # Verify database file exists
            assert db.db_path.exists()

    @pytest.mark.asyncio
    async def test_database_schema_tables(self):
        """Test all required tables are created"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db = Database()
            db.db_path = Path(tmpdir) / "test.db"
            await db.init_db()

            # Check tables exist
            async with db.get_connection() as conn:
                cursor = await conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
                tables = [row[0] for row in await cursor.fetchall()]

            required_tables = [
                "workflows",
                "user_checkpoints",
                "agent_executions",
                "agent_sessions",
                "messages"
            ]

            for table in required_tables:
                assert table in tables, f"Table {table} not found"

    @pytest.mark.asyncio
    async def test_workflow_table_structure(self):
        """Test workflows table has correct columns"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db = Database()
            db.db_path = Path(tmpdir) / "test.db"
            await db.init_db()

            async with db.get_connection() as conn:
                cursor = await conn.execute("PRAGMA table_info(workflows)")
                columns = {row[1] for row in await cursor.fetchall()}

            required_columns = {
                "id", "name", "type", "status",
                "created_at", "updated_at", "completed_at",
                "created_by", "metadata", "result"
            }

            assert required_columns.issubset(columns)

    @pytest.mark.asyncio
    async def test_insert_workflow(self):
        """Test inserting a workflow"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db = Database()
            db.db_path = Path(tmpdir) / "test.db"
            await db.init_db()

            async with db.get_connection() as conn:
                await conn.execute(
                    """
                    INSERT INTO workflows (id, name, type, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))
                    """,
                    ("wf-test", "Test Workflow", "plan_review", "running")
                )
                await conn.commit()

                # Verify insertion
                cursor = await conn.execute(
                    "SELECT * FROM workflows WHERE id = ?",
                    ("wf-test",)
                )
                row = await cursor.fetchone()

            assert row is not None
            assert row[0] == "wf-test"
            assert row[1] == "Test Workflow"

    @pytest.mark.asyncio
    async def test_database_indexes(self):
        """Test that indexes are created"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db = Database()
            db.db_path = Path(tmpdir) / "test.db"
            await db.init_db()

            async with db.get_connection() as conn:
                cursor = await conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='index'"
                )
                indexes = [row[0] for row in await cursor.fetchall()]

            # Check for expected indexes
            expected_indexes = [
                "idx_workflows_status",
                "idx_workflows_created_at",
                "idx_checkpoints_workflow",
                "idx_messages_workflow"
            ]

            for idx in expected_indexes:
                assert idx in indexes, f"Index {idx} not found"

    @pytest.mark.asyncio
    async def test_foreign_key_constraint(self):
        """Test foreign key constraints work"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db = Database()
            db.db_path = Path(tmpdir) / "test.db"
            await db.init_db()

            async with db.get_connection() as conn:
                # Enable foreign keys
                await conn.execute("PRAGMA foreign_keys = ON")

                # Insert workflow
                await conn.execute(
                    """
                    INSERT INTO workflows (id, name, type, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))
                    """,
                    ("wf-test", "Test", "plan_review", "running")
                )

                # Insert message referencing workflow
                await conn.execute(
                    """
                    INSERT INTO messages (workflow_id, role, content, created_at)
                    VALUES (?, ?, ?, datetime('now'))
                    """,
                    ("wf-test", "user", "Test message")
                )

                await conn.commit()

                # Delete workflow (should cascade delete message)
                await conn.execute("DELETE FROM workflows WHERE id = ?", ("wf-test",))
                await conn.commit()

                # Verify message was deleted
                cursor = await conn.execute(
                    "SELECT COUNT(*) FROM messages WHERE workflow_id = ?",
                    ("wf-test",)
                )
                count = (await cursor.fetchone())[0]

            assert count == 0, "Foreign key cascade delete failed"
