"""Base repository with common database operations."""

from ..connection import Database


class BaseRepository:
    """Base class for all repositories."""

    def __init__(self, database: Database):
        self.db = database

    @property
    def connection(self):
        """Get the database connection."""
        return self.db.connection
