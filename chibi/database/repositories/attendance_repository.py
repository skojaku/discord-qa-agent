"""Repository for attendance database operations."""

import csv
import io
import logging
from datetime import datetime
from typing import Dict, List, Optional

from .base import BaseRepository
from ..mappers import row_to_attendance_record
from ..models import AttendanceRecord

logger = logging.getLogger(__name__)


class AttendanceRepository(BaseRepository):
    """Repository for attendance operations."""

    async def save_attendance_records(
        self, records: List[Dict], session_id: str
    ) -> int:
        """Save attendance records to database using UPSERT.

        Args:
            records: List of dicts with user_id, username, timestamp
            session_id: The session identifier

        Returns:
            Number of records saved
        """
        if not records:
            return 0

        conn = self.connection

        for record in records:
            timestamp = record["timestamp"]
            if isinstance(timestamp, datetime):
                timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
                date_id = timestamp.strftime("%Y-%m-%d")
            else:
                timestamp_str = str(timestamp)
                date_id = timestamp_str[:10]

            await conn.execute(
                """
                INSERT OR REPLACE INTO attendance
                (user_id, username, timestamp, date_id, session_id, status)
                VALUES (?, ?, ?, ?, ?, 'present')
                """,
                (
                    record["user_id"],
                    record["username"],
                    timestamp_str,
                    date_id,
                    session_id,
                ),
            )

        await conn.commit()
        return len(records)

    async def get_session_records(self, session_id: str) -> List[AttendanceRecord]:
        """Get all records for a specific session.

        Args:
            session_id: The session identifier

        Returns:
            List of AttendanceRecord objects
        """
        conn = self.connection
        cursor = await conn.execute(
            "SELECT * FROM attendance WHERE session_id = ? ORDER BY timestamp",
            (session_id,),
        )
        rows = await cursor.fetchall()
        return [row_to_attendance_record(row) for row in rows]

    async def get_record(
        self,
        user_id: int,
        date_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Optional[Dict]:
        """Get a specific attendance record.

        Args:
            user_id: The user's database ID
            date_id: Optional date filter (YYYY-MM-DD)
            session_id: Optional session filter

        Returns:
            Dict with record data if found, None otherwise
        """
        conn = self.connection

        if session_id:
            cursor = await conn.execute(
                "SELECT * FROM attendance WHERE user_id = ? AND session_id = ?",
                (user_id, session_id),
            )
        elif date_id:
            cursor = await conn.execute(
                "SELECT * FROM attendance WHERE user_id = ? AND date_id = ?",
                (user_id, date_id),
            )
        else:
            return None

        row = await cursor.fetchone()
        if row:
            return dict(row)
        return None

    async def add_manual_attendance(
        self,
        user_id: int,
        username: str,
        date_id: str,
        session_id: Optional[str] = None,
        status: str = "present",
    ) -> Dict:
        """Manually add an attendance record.

        Args:
            user_id: The user's database ID
            username: The user's username
            date_id: Date in YYYY-MM-DD format
            session_id: Optional session ID (generated if not provided)
            status: Status ('present' or 'excused')

        Returns:
            Dict with the created record info
        """
        conn = self.connection

        if not session_id:
            session_id = f"manual_{int(datetime.now().timestamp())}"

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        await conn.execute(
            """
            INSERT OR REPLACE INTO attendance
            (user_id, username, timestamp, date_id, session_id, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, username, timestamp, date_id, session_id, status),
        )
        await conn.commit()

        return {
            "user_id": user_id,
            "username": username,
            "date_id": date_id,
            "session_id": session_id,
            "status": status,
        }

    async def update_status(
        self,
        user_id: int,
        status: str,
        date_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> int:
        """Update attendance status (present/excused).

        Args:
            user_id: The user's database ID
            status: New status ('present' or 'excused')
            date_id: Optional date filter
            session_id: Optional session filter

        Returns:
            Number of records updated
        """
        conn = self.connection

        if session_id:
            await conn.execute(
                "UPDATE attendance SET status = ? WHERE user_id = ? AND session_id = ?",
                (status, user_id, session_id),
            )
        elif date_id:
            await conn.execute(
                "UPDATE attendance SET status = ? WHERE user_id = ? AND date_id = ?",
                (status, user_id, date_id),
            )
        else:
            return 0

        await conn.commit()
        return conn.total_changes

    async def remove_attendance(
        self,
        user_id: int,
        date_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> int:
        """Remove attendance record(s).

        Args:
            user_id: The user's database ID
            date_id: Optional date filter
            session_id: Optional session filter

        Returns:
            Number of records deleted
        """
        conn = self.connection

        if session_id:
            await conn.execute(
                "DELETE FROM attendance WHERE user_id = ? AND session_id = ?",
                (user_id, session_id),
            )
        elif date_id:
            await conn.execute(
                "DELETE FROM attendance WHERE user_id = ? AND date_id = ?",
                (user_id, date_id),
            )
        else:
            return 0

        await conn.commit()
        return conn.total_changes

    async def export_to_csv(
        self, session_id: Optional[str] = None
    ) -> tuple[str, int]:
        """Export attendance records to CSV string.

        Args:
            session_id: Optional session filter (None = all records)

        Returns:
            Tuple of (CSV content string, record count)
        """
        conn = self.connection

        # Join with users table to get student_id and student_name
        if session_id:
            cursor = await conn.execute(
                """
                SELECT
                    u.student_id,
                    u.student_name,
                    a.username as discord_username,
                    a.user_id,
                    a.timestamp,
                    a.date_id,
                    a.session_id,
                    a.status
                FROM attendance a
                LEFT JOIN users u ON a.user_id = u.id
                WHERE a.session_id = ?
                ORDER BY a.timestamp
                """,
                (session_id,),
            )
        else:
            cursor = await conn.execute(
                """
                SELECT
                    u.student_id,
                    u.student_name,
                    a.username as discord_username,
                    a.user_id,
                    a.timestamp,
                    a.date_id,
                    a.session_id,
                    a.status
                FROM attendance a
                LEFT JOIN users u ON a.user_id = u.id
                ORDER BY a.date_id, a.timestamp
                """
            )

        rows = await cursor.fetchall()

        if not rows:
            return "", 0

        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow(
            [
                "student_id",
                "student_name",
                "discord_username",
                "user_id",
                "timestamp",
                "date_id",
                "session_id",
                "status",
            ]
        )

        # Write data
        for row in rows:
            writer.writerow(
                [
                    row["student_id"] or "",
                    row["student_name"] or "",
                    row["discord_username"],
                    row["user_id"],
                    row["timestamp"],
                    row["date_id"],
                    row["session_id"],
                    row["status"],
                ]
            )

        return output.getvalue(), len(rows)

    async def search_students(self, query: str, limit: int = 25) -> List[Dict]:
        """Search students for autocomplete.

        Args:
            query: Search query (matches student_id, student_name, or username)
            limit: Maximum results to return

        Returns:
            List of dicts with student info
        """
        conn = self.connection

        cursor = await conn.execute(
            """
            SELECT id as user_id, discord_id, username, student_id, student_name
            FROM users
            WHERE student_id LIKE ? OR student_name LIKE ? OR username LIKE ?
            ORDER BY username
            LIMIT ?
            """,
            (f"%{query}%", f"%{query}%", f"%{query}%", limit),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def find_student(self, identifier: str) -> Optional[Dict]:
        """Find student by student_id, Discord username, or user_id.

        Args:
            identifier: Student ID, username, or user ID

        Returns:
            Dict with student info if found, None otherwise
        """
        conn = self.connection

        # Try student_id first
        cursor = await conn.execute(
            "SELECT id as user_id, discord_id, username, student_id, student_name FROM users WHERE student_id = ?",
            (identifier,),
        )
        row = await cursor.fetchone()
        if row:
            return dict(row)

        # Try username (case-insensitive)
        cursor = await conn.execute(
            "SELECT id as user_id, discord_id, username, student_id, student_name FROM users WHERE LOWER(username) = LOWER(?)",
            (identifier,),
        )
        row = await cursor.fetchone()
        if row:
            return dict(row)

        # Try discord_id
        cursor = await conn.execute(
            "SELECT id as user_id, discord_id, username, student_id, student_name FROM users WHERE discord_id = ?",
            (identifier,),
        )
        row = await cursor.fetchone()
        if row:
            return dict(row)

        # Try user_id (database ID)
        try:
            user_id = int(identifier)
            cursor = await conn.execute(
                "SELECT id as user_id, discord_id, username, student_id, student_name FROM users WHERE id = ?",
                (user_id,),
            )
            row = await cursor.fetchone()
            if row:
                return dict(row)
        except ValueError:
            pass

        return None
