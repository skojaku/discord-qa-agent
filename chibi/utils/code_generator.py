"""Generate random attendance codes."""

import secrets
from typing import Optional

# Exclude ambiguous characters (I, O, 1, 0)
CHAR_SET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_code(length: int = 4, previous_code: Optional[str] = None) -> str:
    """Generate a random alphanumeric code for attendance.

    Uses cryptographically secure random generation via the secrets module.
    Avoids ambiguous characters like I/O/1/0 that could be confused.

    Args:
        length: Length of the code (default: 4)
        previous_code: Previous code to avoid duplicates

    Returns:
        A random code string (e.g., "A1B2")
    """
    while True:
        code = "".join(secrets.choice(CHAR_SET) for _ in range(length))
        if code != previous_code:
            return code
