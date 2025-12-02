"""Admin review view for LLM Quiz submissions."""

import logging
from dataclasses import dataclass
from typing import Callable, Coroutine, Any, Optional, TYPE_CHECKING

import discord

from ...database.models import ReviewStatus

if TYPE_CHECKING:
    from ...database.models import LLMQuizAttempt

logger = logging.getLogger(__name__)


@dataclass
class ReviewOption:
    """Represents a review option for the admin dropdown."""

    value: str
    label: str
    description: str
    emoji: str


# Define all review options
REVIEW_OPTIONS = [
    ReviewOption(
        value=ReviewStatus.APPROVED,
        label="Approved",
        description="Accept this question for grading",
        emoji="✅",
    ),
    ReviewOption(
        value=ReviewStatus.APPROVED_WITH_BONUS,
        label="Approved with Bonus",
        description="Accept with bonus points for exceptional question",
        emoji="🌟",
    ),
    ReviewOption(
        value=ReviewStatus.REJECTED_CONTENT_MISMATCH,
        label="Reject (Content Mismatch)",
        description="Question doesn't match the module content",
        emoji="❌",
    ),
    ReviewOption(
        value=ReviewStatus.REJECTED_HEAVY_MATH,
        label="Reject (Heavy Math)",
        description="Question requires heavy mathematical computation",
        emoji="🔢",
    ),
    ReviewOption(
        value=ReviewStatus.REJECTED_DEADLINE_PASSED,
        label="Reject (Deadline Passed)",
        description="Submission deadline has passed",
        emoji="⏰",
    ),
]


class ReviewSelect(discord.ui.Select):
    """Dropdown select for review decisions."""

    def __init__(
        self,
        attempt_id: int,
        on_review_callback: Callable[[int, str, discord.Interaction], Coroutine[Any, Any, None]],
    ):
        self.attempt_id = attempt_id
        self.on_review_callback = on_review_callback

        options = [
            discord.SelectOption(
                value=opt.value,
                label=opt.label,
                description=opt.description,
                emoji=opt.emoji,
            )
            for opt in REVIEW_OPTIONS
        ]

        super().__init__(
            placeholder="Select review decision...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        """Handle selection of a review option."""
        selected_value = self.values[0]
        await self.on_review_callback(self.attempt_id, selected_value, interaction)


class AdminReviewView(discord.ui.View):
    """View containing the admin review dropdown."""

    def __init__(
        self,
        attempt_id: int,
        on_review_callback: Callable[[int, str, discord.Interaction], Coroutine[Any, Any, None]],
        timeout: float = 86400.0,  # 24 hour timeout
    ):
        super().__init__(timeout=timeout)
        self.attempt_id = attempt_id
        self.on_review_callback = on_review_callback

        # Add the select dropdown
        self.add_item(ReviewSelect(attempt_id, on_review_callback))

    async def on_timeout(self):
        """Handle view timeout."""
        # Disable all items on timeout
        for item in self.children:
            item.disabled = True


def build_review_request_embed(
    attempt: "LLMQuizAttempt",
    student_username: str,
    module_name: str,
) -> discord.Embed:
    """Build an embed for the admin review request.

    Args:
        attempt: The LLM quiz attempt to review
        student_username: Display name of the student
        module_name: Name of the module

    Returns:
        Discord embed with review details
    """
    embed = discord.Embed(
        title="LLM Quiz Review Request",
        description=f"A student has submitted a question that needs admin review.",
        color=discord.Color.gold(),
    )

    embed.add_field(
        name="Student",
        value=f"**{student_username}** (<@{attempt.discord_user_id}>)",
        inline=True,
    )

    embed.add_field(
        name="Module",
        value=module_name,
        inline=True,
    )

    embed.add_field(
        name="Attempt ID",
        value=f"`#{attempt.id}`",
        inline=True,
    )

    # Truncate question if too long
    question_display = attempt.question
    if len(question_display) > 500:
        question_display = question_display[:497] + "..."

    embed.add_field(
        name="Question",
        value=question_display,
        inline=False,
    )

    # Truncate answer if too long
    answer_display = attempt.student_answer
    if len(answer_display) > 300:
        answer_display = answer_display[:297] + "..."

    embed.add_field(
        name="Student's Answer",
        value=answer_display,
        inline=False,
    )

    # Show AI's answer summary
    llm_answer_display = attempt.llm_answer
    if len(llm_answer_display) > 300:
        llm_answer_display = llm_answer_display[:297] + "..."

    embed.add_field(
        name="AI's Answer",
        value=llm_answer_display,
        inline=False,
    )

    # Evaluation summary
    if attempt.evaluation_explanation:
        eval_display = attempt.evaluation_explanation
        if len(eval_display) > 300:
            eval_display = eval_display[:297] + "..."
        embed.add_field(
            name="Evaluation Summary",
            value=eval_display,
            inline=False,
        )

    embed.set_footer(text="Select a review decision from the dropdown below")

    return embed


def get_review_status_display(status: str) -> tuple[str, str]:
    """Get display emoji and text for a review status.

    Args:
        status: The review status value

    Returns:
        Tuple of (emoji, display_text)
    """
    status_display = {
        ReviewStatus.PENDING: ("⏳", "Pending Review"),
        ReviewStatus.APPROVED: ("✅", "Approved"),
        ReviewStatus.APPROVED_WITH_BONUS: ("🌟", "Approved with Bonus"),
        ReviewStatus.REJECTED_CONTENT_MISMATCH: ("❌", "Rejected (Content Mismatch)"),
        ReviewStatus.REJECTED_HEAVY_MATH: ("🔢", "Rejected (Heavy Math)"),
        ReviewStatus.REJECTED_DEADLINE_PASSED: ("⏰", "Rejected (Deadline Passed)"),
        ReviewStatus.AUTO_APPROVED: ("✅", "Auto-Approved"),
    }
    return status_display.get(status, ("❓", status))
