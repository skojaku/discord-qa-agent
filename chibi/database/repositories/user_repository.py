"""User repository for user-related database operations."""

import logging
from datetime import datetime
from typing import List, Optional

from ..mappers import row_to_user
from ..models import User
from .base import BaseRepository

logger = logging.getLogger(__name__)


class UserRepository(BaseRepository):
    """Repository for user operations."""

    async def get_or_create(self, discord_id: str, username: str) -> User:
        """Get existing user or create new one."""
        conn = self.connection

        # Try to get existing user
        cursor = await conn.execute(
            "SELECT * FROM users WHERE discord_id = ?", (discord_id,)
        )
        row = await cursor.fetchone()

        if row:
            # Update last_active and username
            await conn.execute(
                "UPDATE users SET last_active = CURRENT_TIMESTAMP, username = ? WHERE discord_id = ?",
                (username, discord_id),
            )
            await conn.commit()
            return User(
                id=row["id"],
                discord_id=row["discord_id"],
                username=username,
                created_at=row["created_at"],
                last_active=datetime.now(),
            )

        # Create new user
        cursor = await conn.execute(
            "INSERT INTO users (discord_id, username) VALUES (?, ?)",
            (discord_id, username),
        )
        await conn.commit()

        return User(
            id=cursor.lastrowid,
            discord_id=discord_id,
            username=username,
            created_at=datetime.now(),
            last_active=datetime.now(),
        )

    async def get_by_discord_id(self, discord_id: str) -> Optional[User]:
        """Get user by Discord ID."""
        conn = self.connection
        cursor = await conn.execute(
            "SELECT * FROM users WHERE discord_id = ?", (discord_id,)
        )
        row = await cursor.fetchone()

        if not row:
            return None

        return row_to_user(row)

    async def get_all(self) -> List[User]:
        """Get all users in the database."""
        conn = self.connection
        cursor = await conn.execute("SELECT * FROM users ORDER BY username")
        rows = await cursor.fetchall()

        return [row_to_user(row) for row in rows]

    async def search_by_identifier(self, identifier: str) -> Optional[User]:
        """Search for a user by Discord ID, username, or partial match.

        Args:
            identifier: Discord ID, username, or partial name to search for

        Returns:
            User if found, None otherwise
        """
        conn = self.connection
        logger.info(f"Searching for user with identifier: '{identifier}'")

        # First try exact match on discord_id
        cursor = await conn.execute(
            "SELECT * FROM users WHERE discord_id = ?", (identifier,)
        )
        row = await cursor.fetchone()
        if row:
            logger.info(f"Found user by discord_id: {row['username']} ({row['discord_id']})")
            return row_to_user(row)

        # Then try exact match on username (case-insensitive)
        cursor = await conn.execute(
            "SELECT * FROM users WHERE LOWER(username) = LOWER(?)", (identifier,)
        )
        row = await cursor.fetchone()
        if row:
            logger.info(f"Found user by username: {row['username']} ({row['discord_id']})")
            return row_to_user(row)

        # Finally try partial match on username (case-insensitive)
        cursor = await conn.execute(
            "SELECT * FROM users WHERE LOWER(username) LIKE LOWER(?)",
            (f"%{identifier}%",),
        )
        row = await cursor.fetchone()
        if row:
            logger.info(f"Found user by partial match: {row['username']} ({row['discord_id']})")
            return row_to_user(row)

        # List all users for debugging
        cursor = await conn.execute("SELECT discord_id, username FROM users LIMIT 10")
        all_rows = await cursor.fetchall()
        logger.info(f"No user found. Available users: {[(r['discord_id'], r['username']) for r in all_rows]}")

        return None
