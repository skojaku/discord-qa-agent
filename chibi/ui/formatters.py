"""Shared formatting utilities for Discord embeds."""

from ..constants import MASTERY_EMOJI, PROGRESS_BAR_LENGTH


def create_progress_bar(
    mastered: int,
    proficient: int,
    learning: int,
    novice: int,
) -> str:
    """Create a visual progress bar showing mastery distribution.

    Args:
        mastered: Count of mastered concepts
        proficient: Count of proficient concepts
        learning: Count of learning concepts
        novice: Count of novice concepts

    Returns:
        ASCII progress bar string like "[████▓▓▒▒░░░░░░░░░░░░]"
    """
    total = mastered + proficient + learning + novice
    if total == 0:
        return "[ No data yet ]"

    m_len = int(mastered / total * PROGRESS_BAR_LENGTH)
    p_len = int(proficient / total * PROGRESS_BAR_LENGTH)
    l_len = int(learning / total * PROGRESS_BAR_LENGTH)
    n_len = PROGRESS_BAR_LENGTH - m_len - p_len - l_len

    return (
        "["
        + "█" * m_len
        + "▓" * p_len
        + "▒" * l_len
        + "░" * n_len
        + "]"
    )


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
