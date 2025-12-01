"""SQLite database connection manager for Chibi bot."""

import aiosqlite
from pathlib import Path
from typing import Optional


class Database:
    """Async SQLite database connection manager."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None

    async def connect(self) -> None:
        """Establish database connection and initialize schema."""
        # Ensure data directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self._connection = await aiosqlite.connect(self.db_path)
        self._connection.row_factory = aiosqlite.Row
        await self._init_schema()

    async def close(self) -> None:
        """Close database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None

    @property
    def connection(self) -> aiosqlite.Connection:
        """Get the database connection."""
        if not self._connection:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._connection

    async def _init_schema(self) -> None:
        """Initialize database schema."""
        schema = """
        -- Users table
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            discord_id TEXT UNIQUE NOT NULL,
            username TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Interactions log (Q&A history)
        CREATE TABLE IF NOT EXISTS interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            module_id TEXT NOT NULL,
            question TEXT NOT NULL,
            response TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        -- Quiz attempts
        CREATE TABLE IF NOT EXISTS quiz_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            module_id TEXT NOT NULL,
            concept_id TEXT NOT NULL,
            quiz_format TEXT NOT NULL,
            question TEXT NOT NULL,
            user_answer TEXT NOT NULL,
            correct_answer TEXT,
            is_correct BOOLEAN NOT NULL,
            llm_feedback TEXT,
            llm_quality_score INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        -- Concept mastery
        CREATE TABLE IF NOT EXISTS concept_mastery (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            concept_id TEXT NOT NULL,
            total_attempts INTEGER DEFAULT 0,
            correct_attempts INTEGER DEFAULT 0,
            avg_quality_score REAL DEFAULT 0.0,
            mastery_level TEXT DEFAULT 'novice',
            last_attempt_at TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, concept_id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        -- Indexes for performance
        CREATE INDEX IF NOT EXISTS idx_interactions_user ON interactions(user_id);
        CREATE INDEX IF NOT EXISTS idx_interactions_module ON interactions(module_id);
        CREATE INDEX IF NOT EXISTS idx_quiz_attempts_user ON quiz_attempts(user_id);
        CREATE INDEX IF NOT EXISTS idx_quiz_attempts_concept ON quiz_attempts(concept_id);
        CREATE INDEX IF NOT EXISTS idx_concept_mastery_user ON concept_mastery(user_id);
        """

        await self._connection.executescript(schema)
        await self._connection.commit()
