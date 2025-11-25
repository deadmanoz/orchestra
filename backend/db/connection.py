import aiosqlite
from pathlib import Path
from backend.settings import settings

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

    def get_connection(self):
        """Get database connection"""
        return aiosqlite.connect(self.db_path)

db = Database()
