"""Backup cog for admin-only backup and restore operations."""

import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

if TYPE_CHECKING:
    from ..bot import ChibiBot

logger = logging.getLogger(__name__)

# Error messages
ERROR_BACKUP_EXPORT = "Failed to export progress to Google Sheets. Please check logs."
ERROR_BACKUP_IMPORT = "Failed to import progress from Google Sheets. Please check logs."
ERROR_BACKUP_LIST = "Failed to list recent exports. Please check logs."


class ImportConfirmView(discord.ui.View):
    """Confirmation view for import operations."""

    def __init__(self, cog: "BackupCog", spreadsheet_url: str, mode: str):
        super().__init__(timeout=300)  # 5 minute timeout
        self.cog = cog
        self.spreadsheet_url = spreadsheet_url
        self.mode = mode
        self.confirmed = False

    @discord.ui.button(label="Confirm Import", style=discord.ButtonStyle.danger)
    async def confirm_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Handle confirmation button click."""
        await interaction.response.defer()
        self.confirmed = True
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Handle cancel button click."""
        await interaction.response.send_message("Import cancelled.", ephemeral=True)
        self.confirmed = False
        self.stop()


class BackupCog(commands.Cog):
    """Cog for admin-only backup commands.

    Commands:
        /export-progress - Export student progress to Google Sheets
        /import-progress - Import student progress from Google Sheets
        /list-exports - List recent exports
    """

    def __init__(self, bot: "ChibiBot"):
        self.bot = bot

    @app_commands.command(
        name="export-progress",
        description="[ADMIN] Export student progress to Google Sheets"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def export_progress(self, interaction: discord.Interaction):
        """Export all student progress data to a new Google Sheets spreadsheet.

        Creates a new spreadsheet with all student data including:
        - User profiles
        - Quiz attempts and responses
        - Concept mastery tracking
        - LLM quiz challenge attempts
        - Attendance records

        The spreadsheet URL will be returned for easy access.
        """
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            # Call the backup service
            result = await self.bot.backup_service.export_progress()

            # Build success embed
            embed = discord.Embed(
                title="✅ Export Successful",
                description="Student progress has been exported to Google Sheets.",
                color=discord.Color.green(),
            )

            # Add spreadsheet link
            embed.add_field(
                name="Spreadsheet",
                value=f"[Open in Google Sheets]({result['spreadsheet_url']})",
                inline=False,
            )

            # Add summary stats
            summary = result.get('summary', {})
            stats_lines = []
            if 'users' in summary:
                stats_lines.append(f"**Users:** {summary['users']}")
            if 'quiz_attempts' in summary:
                stats_lines.append(f"**Quiz Attempts:** {summary['quiz_attempts']}")
            if 'concept_mastery' in summary:
                stats_lines.append(f"**Concept Mastery:** {summary['concept_mastery']}")
            if 'llm_quiz_attempts' in summary:
                stats_lines.append(f"**LLM Quiz Attempts:** {summary['llm_quiz_attempts']}")
            if 'attendance' in summary:
                stats_lines.append(f"**Attendance:** {summary['attendance']}")

            if stats_lines:
                embed.add_field(
                    name="Records Exported",
                    value="\n".join(stats_lines),
                    inline=False,
                )

            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(f"Admin {interaction.user.display_name} exported progress to Sheets")

        except Exception as e:
            logger.error(f"Error exporting progress: {e}", exc_info=True)
            embed = discord.Embed(
                title="❌ Export Failed",
                description=ERROR_BACKUP_EXPORT,
                color=discord.Color.red(),
            )
            embed.add_field(
                name="Error",
                value=str(e)[:1024],  # Truncate long errors
                inline=False,
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(
        name="import-progress",
        description="[ADMIN] Import student progress from Google Sheets"
    )
    @app_commands.describe(
        spreadsheet_url="The Google Sheets URL or spreadsheet ID",
        mode="Import mode: 'replace' (delete all) or 'merge' (update existing)",
    )
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="Replace (delete all data first)", value="replace"),
            app_commands.Choice(name="Merge (update existing records)", value="merge"),
        ]
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def import_progress(
        self,
        interaction: discord.Interaction,
        spreadsheet_url: str,
        mode: app_commands.Choice[str] = None,
    ):
        """Import student progress from a Google Sheets backup.

        Args:
            spreadsheet_url: The URL or ID of the Google Sheets backup
            mode: Import mode - 'replace' deletes all existing data first,
                  'merge' updates existing records and adds new ones.
                  Default is 'replace'.

        Warning: 'replace' mode will DELETE all existing student data
        before importing. Use with caution!
        """
        # Extract mode value (default to replace)
        mode_value = mode.value if mode else "replace"

        # For replace mode, show confirmation dialog
        if mode_value == "replace":
            # Send confirmation prompt
            embed = discord.Embed(
                title="⚠️ Confirm Import",
                description=(
                    "**WARNING:** Replace mode will **DELETE ALL** existing student data "
                    "before importing from the spreadsheet.\n\n"
                    "Are you sure you want to proceed?"
                ),
                color=discord.Color.orange(),
            )
            embed.add_field(
                name="Spreadsheet",
                value=spreadsheet_url,
                inline=False,
            )
            embed.add_field(
                name="Mode",
                value="Replace (delete all existing data)",
                inline=False,
            )

            view = ImportConfirmView(self, spreadsheet_url, mode_value)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

            # Wait for user response
            await view.wait()

            if not view.confirmed:
                return  # User cancelled

            # Defer for the actual import
            await interaction.followup.defer(ephemeral=True)
        else:
            # Merge mode - defer immediately
            await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            # Call the backup service
            result = await self.bot.backup_service.import_progress(
                spreadsheet_url, mode=mode_value
            )

            # Build success embed
            embed = discord.Embed(
                title="✅ Import Successful",
                description=f"Student progress has been imported from Google Sheets using **{mode_value}** mode.",
                color=discord.Color.green(),
            )

            # Add summary stats
            summary = result.get('summary', {})
            stats_lines = []
            if 'users_imported' in result:
                stats_lines.append(f"**Users:** {result['users_imported']}")
            if 'quiz_attempts_imported' in result:
                stats_lines.append(f"**Quiz Attempts:** {result['quiz_attempts_imported']}")
            if 'concept_mastery_imported' in result:
                stats_lines.append(f"**Concept Mastery:** {result['concept_mastery_imported']}")
            if 'llm_quiz_attempts_imported' in result:
                stats_lines.append(f"**LLM Quiz Attempts:** {result['llm_quiz_attempts_imported']}")
            if 'attendance_imported' in result:
                stats_lines.append(f"**Attendance:** {result['attendance_imported']}")

            if stats_lines:
                embed.add_field(
                    name="Records Imported",
                    value="\n".join(stats_lines),
                    inline=False,
                )

            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(
                f"Admin {interaction.user.display_name} imported progress from Sheets "
                f"(mode: {mode_value})"
            )

        except Exception as e:
            logger.error(f"Error importing progress: {e}", exc_info=True)
            embed = discord.Embed(
                title="❌ Import Failed",
                description=ERROR_BACKUP_IMPORT,
                color=discord.Color.red(),
            )
            embed.add_field(
                name="Error",
                value=str(e)[:1024],  # Truncate long errors
                inline=False,
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(
        name="list-exports",
        description="[ADMIN] List recent Google Sheets exports"
    )
    @app_commands.describe(
        limit="Maximum number of exports to show (default: 10)",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def list_exports(
        self,
        interaction: discord.Interaction,
        limit: int = 10,
    ):
        """List recent backup exports from Google Sheets.

        Shows the most recent exports with links for easy access.

        Args:
            limit: Maximum number of exports to show (default: 10, max: 25)
        """
        await interaction.response.defer(ephemeral=True, thinking=True)

        # Validate limit
        limit = max(1, min(limit, 25))

        try:
            # Call the backup service
            exports = await self.bot.backup_service.list_recent_exports(limit=limit)

            if not exports:
                embed = discord.Embed(
                    title="📋 Recent Exports",
                    description="No exports found. Use `/export-progress` to create one.",
                    color=discord.Color.blue(),
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Build embed with exports
            embed = discord.Embed(
                title=f"📋 Recent Exports ({len(exports)})",
                description="Click on a spreadsheet to open it in Google Sheets.",
                color=discord.Color.blue(),
            )

            for i, export in enumerate(exports, 1):
                name = export.get('name', 'Untitled')
                url = export.get('url', '')
                created = export.get('createdTime', 'Unknown')

                # Format created time (if available as ISO string)
                if created and created != 'Unknown':
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                        created = dt.strftime('%Y-%m-%d %H:%M UTC')
                    except Exception:
                        pass  # Keep original format if parsing fails

                embed.add_field(
                    name=f"{i}. {name}",
                    value=f"[Open Spreadsheet]({url})\nCreated: {created}",
                    inline=False,
                )

            embed.set_footer(text="Use /export-progress to create a new backup")
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(f"Admin {interaction.user.display_name} listed recent exports")

        except Exception as e:
            logger.error(f"Error listing exports: {e}", exc_info=True)
            embed = discord.Embed(
                title="❌ Failed to List Exports",
                description=ERROR_BACKUP_LIST,
                color=discord.Color.red(),
            )
            embed.add_field(
                name="Error",
                value=str(e)[:1024],  # Truncate long errors
                inline=False,
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @export_progress.error
    @import_progress.error
    @list_exports.error
    async def backup_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        """Handle errors for backup commands."""
        if isinstance(error, app_commands.errors.MissingPermissions):
            await interaction.response.send_message(
                "❌ You need administrator permissions to use backup commands.",
                ephemeral=True,
            )
        else:
            logger.error(f"Backup command error: {error}", exc_info=True)
            try:
                await interaction.response.send_message(
                    "❌ An error occurred. Please try again or check the logs.",
                    ephemeral=True,
                )
            except discord.InteractionResponded:
                await interaction.followup.send(
                    "❌ An error occurred. Please try again or check the logs.",
                    ephemeral=True,
                )


async def setup(bot: "ChibiBot"):
    """Set up the Backup cog."""
    await bot.add_cog(BackupCog(bot))
