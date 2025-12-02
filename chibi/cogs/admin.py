"""Admin commands cog for instructor/admin functionality."""

import csv
import io
import logging
from datetime import datetime
from typing import Optional, TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from ..constants import (
    CSV_FILENAME_PREFIX,
    ERROR_ADMIN_CHANNEL_ONLY,
    ERROR_ADMIN_ONLY,
    ERROR_MODULE_NOT_FOUND,
    ERROR_SHOW_GRADE,
    MASTERY_MASTERED,
    MASTERY_PROFICIENT,
)
from .utils import defer_interaction, module_autocomplete_choices, send_error_response

if TYPE_CHECKING:
    from ..bot import ChibiBot

logger = logging.getLogger(__name__)


def is_admin_channel(bot: "ChibiBot", channel: discord.abc.GuildChannel) -> bool:
    """Check if the channel is the admin channel.

    Args:
        bot: The bot instance
        channel: The channel to check

    Returns:
        True if the channel is the admin channel
    """
    admin_channel_name = bot.config.discord.admin_channel_name
    return channel.name.lower() == admin_channel_name.lower()


class AdminCog(commands.Cog):
    """Cog for admin-only commands."""

    def __init__(self, bot: "ChibiBot"):
        self.bot = bot

    async def _check_admin_permissions(
        self, interaction: discord.Interaction
    ) -> Optional[str]:
        """Check if user has admin permissions and is in admin channel.

        Args:
            interaction: The Discord interaction

        Returns:
            Error message if check fails, None if all checks pass
        """
        # Check if user is an administrator
        if not interaction.user.guild_permissions.administrator:
            return ERROR_ADMIN_ONLY

        # Check if command is used in admin channel
        if not is_admin_channel(self.bot, interaction.channel):
            admin_channel = self.bot.config.discord.admin_channel_name
            return f"{ERROR_ADMIN_CHANNEL_ONLY} Please use #{admin_channel}."

        return None

    @app_commands.command(
        name="show_grade",
        description="Generate a CSV report of student grades (Admin only)"
    )
    @app_commands.describe(
        module="Filter by specific module (optional)"
    )
    @defer_interaction(thinking=True)
    async def show_grade(
        self,
        interaction: discord.Interaction,
        module: Optional[str] = None,
    ):
        """Generate and send a CSV file with student grades.

        The CSV includes:
        - Student ID (Discord ID)
        - Username
        - Completed concepts
        - Percentage of completion per module
        """
        try:
            # Check admin permissions
            error = await self._check_admin_permissions(interaction)
            if error:
                await interaction.followup.send(error, ephemeral=True)
                return

            # Validate module if specified
            target_module = None
            if module:
                target_module = self.bot.course.get_module(module)
                if not target_module:
                    await interaction.followup.send(ERROR_MODULE_NOT_FOUND, ephemeral=True)
                    return

            # Generate CSV data
            csv_content = await self._generate_grade_csv(target_module)

            # Create file object
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            module_suffix = f"_{module}" if module else ""
            filename = f"{CSV_FILENAME_PREFIX}{module_suffix}_{timestamp}.csv"

            file = discord.File(
                io.BytesIO(csv_content.encode("utf-8")),
                filename=filename
            )

            # Send the file
            module_info = f" for module **{target_module.name}**" if target_module else ""
            await interaction.followup.send(
                f"Grade report{module_info} generated successfully.",
                file=file
            )

        except Exception as e:
            await send_error_response(
                interaction, ERROR_SHOW_GRADE, logger, e, "/show_grade command"
            )

    async def _generate_grade_csv(
        self,
        target_module=None,
    ) -> str:
        """Generate CSV content with student grades.

        Args:
            target_module: If specified, only include data for this module

        Returns:
            CSV content as a string
        """
        # Get all users
        users = await self.bot.repository.get_all_users()

        # Get course modules info
        if target_module:
            modules = [target_module]
        else:
            modules = self.bot.course.modules

        # Build CSV headers
        headers = ["discord_id", "username"]

        # Add columns for each module: completed concepts and completion percentage
        for mod in modules:
            headers.append(f"{mod.id}_completed_concepts")
            headers.append(f"{mod.id}_completion_pct")

        # Add overall columns if showing all modules
        if not target_module:
            headers.append("total_completed_concepts")
            headers.append("overall_completion_pct")

        # Create CSV writer
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(headers)

        # Process each user
        for user in users:
            row = [user.discord_id, user.username]

            # Get user's mastery records
            mastery_records = await self.bot.repository.get_user_mastery_all(user.id)
            mastery_by_concept = {m.concept_id: m for m in mastery_records}

            total_completed = 0
            total_concepts = 0

            for mod in modules:
                module_concepts = mod.concepts
                total_concepts += len(module_concepts)

                # Count completed concepts (proficient or mastered)
                completed_concepts = []
                for concept in module_concepts:
                    mastery = mastery_by_concept.get(concept.id)
                    if mastery and mastery.mastery_level in (MASTERY_PROFICIENT, MASTERY_MASTERED):
                        completed_concepts.append(concept.id)

                completed_count = len(completed_concepts)
                total_completed += completed_count

                # Calculate completion percentage for this module
                completion_pct = (
                    (completed_count / len(module_concepts) * 100)
                    if module_concepts else 0
                )

                # Add module data to row
                row.append(";".join(completed_concepts) if completed_concepts else "")
                row.append(f"{completion_pct:.1f}")

            # Add overall totals if showing all modules
            if not target_module:
                all_completed = []
                for mod in modules:
                    for concept in mod.concepts:
                        mastery = mastery_by_concept.get(concept.id)
                        if mastery and mastery.mastery_level in (MASTERY_PROFICIENT, MASTERY_MASTERED):
                            all_completed.append(concept.id)

                overall_pct = (
                    (len(all_completed) / total_concepts * 100)
                    if total_concepts > 0 else 0
                )

                row.append(";".join(all_completed) if all_completed else "")
                row.append(f"{overall_pct:.1f}")

            writer.writerow(row)

        return output.getvalue()

    @show_grade.autocomplete("module")
    async def module_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """Provide autocomplete choices for module selection."""
        return await module_autocomplete_choices(self.bot.course, current)


async def setup(bot: "ChibiBot"):
    """Set up the Admin cog."""
    await bot.add_cog(AdminCog(bot))
