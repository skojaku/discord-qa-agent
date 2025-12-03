"""Shared formatting utilities for Discord embeds."""

from ..constants import MASTERY_EMOJI, PROGRESS_BAR_LENGTH


def create_progress_bar(
    passed: int,
    required: int,
) -> str:
    """Create a visual progress bar showing passed quizzes vs required.

    Args:
        passed: Number of correct quiz answers (will be capped at required)
        required: Total number of correct answers needed

    Returns:
        ASCII progress bar string like "[████████░░░░░░░░░░░░] 8/20"
    """
    if required == 0:
        return "[ No data yet ]"

    # Cap passed at required
    capped_passed = min(passed, required)

    # Calculate filled length
    filled_len = int(capped_passed / required * PROGRESS_BAR_LENGTH)
    empty_len = PROGRESS_BAR_LENGTH - filled_len

    bar = "[" + "█" * filled_len + "░" * empty_len + "]"
    return f"{bar} {capped_passed}/{required}"


def get_mastery_emoji(level: str) -> str:
    """Get emoji for a mastery level.

    Args:
        level: Mastery level string (mastered, proficient, learning, novice)

    Returns:
        Emoji string for the level, or ⬜ for unknown levels
    """
    return MASTERY_EMOJI.get(level, "⬜")


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """Truncate text to a maximum length with suffix.

    Args:
        text: Text to truncate
        max_length: Maximum length including suffix
        suffix: Suffix to append when truncating (default: "...")

    Returns:
        Truncated text with suffix if needed, original text otherwise
    """
    if not text or len(text) <= max_length:
        return text or ""
    return text[: max_length - len(suffix)] + suffix
