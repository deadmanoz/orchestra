import aiosqlite
import logging
from pathlib import Path
from backend.settings import settings

logger = logging.getLogger(__name__)


class Database:
    def __init__(self):
        self.db_path = Path("./data/orchestra.db")
        self.db_path.parent.mkdir(exist_ok=True)

    async def init_db(self):
        """Initialize database schema"""
        async with aiosqlite.connect(self.db_path) as db:
            # Read and execute schema
            schema_path = Path(__file__).parent / "schema.sql"
            schema_sql = schema_path.read_text()

            await db.executescript(schema_sql)
            await db.commit()

            # Run migrations for existing databases
            await self._run_migrations(db)

    async def _run_migrations(self, db: aiosqlite.Connection):
        """Run database migrations for schema changes"""
        # Migration: Add approval_status column to agent_executions if not exists
        cursor = await db.execute("PRAGMA table_info(agent_executions)")
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]

        if "approval_status" not in column_names:
            logger.info("[Migration] Adding approval_status column to agent_executions")
            await db.execute(
                "ALTER TABLE agent_executions ADD COLUMN approval_status TEXT "
                "CHECK(approval_status IN ('approved', 'has_feedback', 'unclear'))"
            )
            await db.commit()

    def get_connection(self):
        """Get database connection"""
        return aiosqlite.connect(self.db_path)

db = Database()
