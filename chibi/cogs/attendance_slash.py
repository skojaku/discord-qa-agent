"""Attendance admin slash commands cog.

Admin attendance commands use slash commands with administrator permission checks.
These commands are only visible to users with administrator permissions.
"""

import asyncio
import io
import logging
from datetime import datetime
from typing import Optional, TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from ..constants import (
    ATTENDANCE_CSV_PREFIX,
    ERROR_ATTENDANCE_SESSION_ACTIVE,
)
from ..utils.code_generator import generate_code
from ..utils.errors import (
    NoActiveSessionError,
    SessionAlreadyActiveError,
)

if TYPE_CHECKING:
    from ..bot import ChibiBot

logger = logging.getLogger(__name__)


class AttendanceSlashCog(commands.Cog):
    """Cog for admin-only attendance slash commands.

    Commands:
        /admin-open-attendance - Start attendance session with rotating codes
        /admin-close-attendance - Close session and save to database
        /admin-export-attendance [session_id] - Export attendance CSV
        /admin-excuse <student> [date] - Mark student excused
        /admin-mark-present <student> [date] [session_id] - Manually mark present
        /admin-remove-attendance <student> [date] [session_id] - Remove attendance record
    """

    def __init__(self, bot: "ChibiBot"):
        self.bot = bot
        # Share the session manager from the main attendance cog
        self.session_manager = bot.attendance_session_manager
        self.rotation_task: Optional[asyncio.Task] = None
        self.auto_close_task: Optional[asyncio.Task] = None

    @app_commands.command(
        name="admin-open-attendance",
        description="[ADMIN] Start attendance session with rotating codes"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def open_attendance(self, interaction: discord.Interaction):
        """Start a new attendance session with rotating codes."""
        try:
            # Generate initial code
            code_length = self.bot.config.attendance.code_length
            initial_code = generate_code(code_length)

            # Get both channels
            admin_channel_id = self.bot.config.discord.admin_channel_id
            attendance_channel_id = self.bot.config.attendance.attendance_channel_id

            admin_channel = self.bot.get_channel(admin_channel_id)
            attendance_channel = self.bot.get_channel(attendance_channel_id)

            if not admin_channel:
                await interaction.response.send_message(
                    "Could not find admin channel. Please check configuration.",
                    ephemeral=True
                )
                return

            if not attendance_channel:
                await interaction.response.send_message(
                    "Could not find attendance channel. Please check ATTENDANCE_CHANNEL_ID.",
                    ephemeral=True
                )
                return

            # Post the code message in ADMIN channel (for projector display)
            code_embed = discord.Embed(
                title="Attendance Code (Admin Only)",
                description="Show this code on the projector for students:",
                color=discord.Color.blue(),
            )
            code_embed.add_field(
                name="Current Code", value=f"# **`{initial_code}`**", inline=False
            )
            code_embed.add_field(
                name="Status", value="0 student(s) submitted", inline=False
            )
            code_embed.set_footer(
                text="Code changes every 15 seconds | Only the latest submission counts"
            )

            admin_message = await admin_channel.send(embed=code_embed)

            # Post a notification in ATTENDANCE channel (no code shown)
            student_embed = discord.Embed(
                title="Attendance is Now Open!",
                description="Look at the projector for the attendance code.",
                color=discord.Color.green(),
            )
            student_embed.add_field(
                name="How to Submit",
                value="Type `/here <code>` in this channel with the code shown on screen",
                inline=False,
            )
            student_embed.set_footer(
                text="Code changes every 15 seconds | Only the latest submission counts"
            )

            attendance_message = await attendance_channel.send(embed=student_embed)

            # Start session
            self.session_manager.start_session(
                initial_code, admin_message.id, admin_channel.id
            )
            self.session_manager.attendance_message_id = attendance_message.id
            self.session_manager.attendance_channel_id = attendance_channel.id

            # Start code rotation task
            self.rotation_task = asyncio.create_task(self._rotate_code_loop())

            # Start auto-close task (10 minutes)
            self.auto_close_task = asyncio.create_task(self._auto_close_loop())

            # Confirm to admin (ephemeral response)
            await interaction.response.send_message(
                f"✅ Attendance session started!\n"
                f"Current code: `{initial_code}`\n"
                f"Code displayed in <#{admin_channel_id}> (show on projector)\n"
                f"Students notified in <#{attendance_channel_id}>\n"
                f"⏰ Session will automatically close in 10 minutes",
                ephemeral=True
            )

        except SessionAlreadyActiveError:
            await interaction.response.send_message(
                ERROR_ATTENDANCE_SESSION_ACTIVE,
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error opening attendance: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ Failed to open attendance: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(
        name="admin-close-attendance",
        description="[ADMIN] Close attendance session and save records"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def close_attendance(self, interaction: discord.Interaction):
        """Close the active attendance session and save records."""
        try:
            # Defer the response
            await interaction.response.defer(ephemeral=True, thinking=True)

            # Cancel rotation task
            if self.rotation_task:
                self.rotation_task.cancel()
                try:
                    await self.rotation_task
                except asyncio.CancelledError:
                    pass

            # Cancel auto-close task if it exists
            if self.auto_close_task:
                self.auto_close_task.cancel()
                try:
                    await self.auto_close_task
                except asyncio.CancelledError:
                    pass

            # Get session data
            records, session_id = self.session_manager.end_session()

            # Save to database
            saved_count = await self.bot.attendance_repo.save_attendance_records(
                records, session_id
            )

            # Update the admin channel message to show it's closed
            try:
                admin_channel = self.bot.get_channel(
                    self.session_manager.channel_id
                    or self.bot.config.discord.admin_channel_id
                )
                if admin_channel and self.session_manager.message_id:
                    admin_message = await admin_channel.fetch_message(
                        self.session_manager.message_id
                    )

                    admin_embed = discord.Embed(
                        title="Attendance Session Closed",
                        description="This attendance session has ended.",
                        color=discord.Color.red(),
                    )
                    admin_embed.add_field(
                        name="Total Submissions",
                        value=f"{saved_count} student(s)",
                        inline=False,
                    )
                    admin_embed.set_footer(text=f"Session ID: {session_id}")

                    await admin_message.edit(embed=admin_embed)
            except Exception as e:
                logger.warning(f"Could not update admin message: {e}")

            # Update the attendance channel message to show it's closed
            try:
                attendance_channel = self.bot.get_channel(
                    self.session_manager.attendance_channel_id
                    or self.bot.config.attendance.attendance_channel_id
                )
                attendance_msg_id = self.session_manager.attendance_message_id
                if attendance_channel and attendance_msg_id:
                    attendance_message = await attendance_channel.fetch_message(
                        attendance_msg_id
                    )

                    student_embed = discord.Embed(
                        title="Attendance is Now Closed",
                        description="This attendance session has ended.",
                        color=discord.Color.red(),
                    )
                    student_embed.add_field(
                        name="Total Submissions",
                        value=f"{saved_count} student(s)",
                        inline=False,
                    )
                    student_embed.set_footer(text=f"Session ID: {session_id}")

                    await attendance_message.edit(embed=student_embed)
            except Exception as e:
                logger.warning(f"Could not update attendance channel message: {e}")

            # Reset session manager
            self.session_manager.reset()

            # Confirm to admin
            await interaction.followup.send(
                f"✅ Attendance session closed!\n"
                f"Total submissions saved: {saved_count}\n"
                f"Session ID: `{session_id}`",
                ephemeral=True
            )

        except NoActiveSessionError:
            await interaction.followup.send(
                "No active attendance session to close.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error closing attendance: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Failed to close attendance: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(
        name="admin-export-attendance",
        description="[ADMIN] Export attendance records to CSV"
    )
    @app_commands.describe(
        session_id="Optional: Export specific session (leave empty for all records)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def export_attendance(
        self,
        interaction: discord.Interaction,
        session_id: Optional[str] = None
    ):
        """Export attendance records to CSV file."""
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            # Export to CSV
            csv_content, record_count = await self.bot.attendance_repo.export_to_csv(
                session_id
            )

            if record_count == 0:
                await interaction.followup.send(
                    "No records found to export.",
                    ephemeral=True
                )
                return

            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if session_id:
                filename = f"{ATTENDANCE_CSV_PREFIX}_{session_id}.csv"
            else:
                filename = f"{ATTENDANCE_CSV_PREFIX}_all_{timestamp}.csv"

            # Send the file
            file = discord.File(
                io.BytesIO(csv_content.encode("utf-8")), filename=filename
            )
            await interaction.followup.send(
                f"✅ Exported {record_count} record(s) to CSV:",
                file=file,
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"Error exporting attendance: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Failed to export attendance: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(
        name="admin-excuse",
        description="[ADMIN] Mark a student as excused for a specific date"
    )
    @app_commands.describe(
        student="Select the student to excuse",
        date="Date in YYYY-MM-DD format (defaults to today)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def excuse(
        self,
        interaction: discord.Interaction,
        student: discord.User,
        date: Optional[str] = None
    ):
        """Mark a student as excused for a date."""
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            # Get user from database
            db_user = await self.bot.user_repo.get_by_discord_id(str(student.id))
            if not db_user:
                await interaction.followup.send(
                    f"❌ User {student.mention} not found in database.\n"
                    f"They need to use `/quiz` or `/register` first.",
                    ephemeral=True
                )
                return

            user_id = db_user.id
            display_name = db_user.username or student.display_name

            # Default to today's date
            if not date:
                date = datetime.now().strftime("%Y-%m-%d")

            # Validate date format
            try:
                datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                await interaction.followup.send(
                    f"❌ Invalid date format: `{date}`\n"
                    f"Please use YYYY-MM-DD format (e.g., 2025-12-01).",
                    ephemeral=True
                )
                return

            # Check if student has an attendance record for this date
            existing = await self.bot.attendance_repo.get_record(user_id, date_id=date)

            if existing:
                # Update existing record to excused
                count = await self.bot.attendance_repo.update_status(
                    user_id, "excused", date_id=date
                )
                if count > 0:
                    await interaction.followup.send(
                        f"✅ Marked **{display_name}** as excused for `{date}`\n"
                        f"(Updated existing attendance record)",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        f"❌ Failed to update attendance record for **{display_name}**.",
                        ephemeral=True
                    )
            else:
                # Create new excused record
                username = db_user.username or student.display_name
                result = await self.bot.attendance_repo.add_manual_attendance(
                    user_id=user_id, username=username, date_id=date, status="excused"
                )
                await interaction.followup.send(
                    f"✅ Marked **{display_name}** as excused for `{date}`\n"
                    f"Session ID: `{result['session_id']}`",
                    ephemeral=True
                )

        except Exception as e:
            logger.error(f"Error marking excused: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Failed to mark student as excused: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(
        name="admin-mark-present",
        description="[ADMIN] Manually mark a student as present"
    )
    @app_commands.describe(
        student="Select the student to mark present",
        date="Date in YYYY-MM-DD format (defaults to today)",
        session_id="Optional: Specific session ID"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def mark_present(
        self,
        interaction: discord.Interaction,
        student: discord.User,
        date: Optional[str] = None,
        session_id: Optional[str] = None,
    ):
        """Manually mark a student as present for a specific date."""
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            # Get user from database
            db_user = await self.bot.user_repo.get_by_discord_id(str(student.id))
            if not db_user:
                await interaction.followup.send(
                    f"❌ User {student.mention} not found in database.\n"
                    f"They need to use `/quiz` or `/register` first.",
                    ephemeral=True
                )
                return

            user_id = db_user.id
            display_name = db_user.username or student.display_name

            # Default to today's date
            if not date:
                date = datetime.now().strftime("%Y-%m-%d")

            # Validate date format
            try:
                datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                await interaction.followup.send(
                    f"❌ Invalid date format: `{date}`\n"
                    f"Please use YYYY-MM-DD format (e.g., 2025-12-01).",
                    ephemeral=True
                )
                return

            # Check if student already has an attendance record
            existing = await self.bot.attendance_repo.get_record(
                user_id,
                date_id=date if not session_id else None,
                session_id=session_id,
            )

            if existing:
                # Update existing record to present
                count = await self.bot.attendance_repo.update_status(
                    user_id,
                    "present",
                    date_id=date if not session_id else None,
                    session_id=session_id,
                )
                if count > 0:
                    await interaction.followup.send(
                        f"✅ Marked **{display_name}** as present for `{date}`\n"
                        f"(Updated existing record - was previously `{existing.get('status', 'unknown')}`)",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        f"❌ Failed to update attendance record for **{display_name}**.",
                        ephemeral=True
                    )
            else:
                # Create new attendance record
                username = db_user.username or student.display_name
                result = await self.bot.attendance_repo.add_manual_attendance(
                    user_id=user_id,
                    username=username,
                    date_id=date,
                    session_id=session_id,
                    status="present",
                )
                await interaction.followup.send(
                    f"✅ Marked **{display_name}** as present for `{date}`\n"
                    f"Session ID: `{result['session_id']}`",
                    ephemeral=True
                )

        except Exception as e:
            logger.error(f"Error marking present: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Failed to mark student as present: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(
        name="admin-remove-attendance",
        description="[ADMIN] Remove a student's attendance record"
    )
    @app_commands.describe(
        student="Select the student",
        date="Date in YYYY-MM-DD format",
        session_id="Optional: Specific session ID"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def remove_attendance(
        self,
        interaction: discord.Interaction,
        student: discord.User,
        date: Optional[str] = None,
        session_id: Optional[str] = None,
    ):
        """Remove a student's attendance record."""
        # Require at least one filter (date or session_id)
        if not date and not session_id:
            await interaction.response.send_message(
                "❌ Please specify either a date or session_id to remove attendance records.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            # Get user from database
            db_user = await self.bot.user_repo.get_by_discord_id(str(student.id))
            if not db_user:
                await interaction.followup.send(
                    f"❌ User {student.mention} not found in database.\n"
                    f"They need to use `/quiz` or `/register` first.",
                    ephemeral=True
                )
                return

            user_id = db_user.id
            display_name = db_user.username or student.display_name

            # Validate date format if provided
            if date:
                try:
                    datetime.strptime(date, "%Y-%m-%d")
                except ValueError:
                    await interaction.followup.send(
                        f"❌ Invalid date format: `{date}`\n"
                        f"Please use YYYY-MM-DD format (e.g., 2025-12-01).",
                        ephemeral=True
                    )
                    return

            # Check if record exists before removing
            existing = await self.bot.attendance_repo.get_record(
                user_id,
                date_id=date if not session_id else None,
                session_id=session_id,
            )

            if not existing:
                msg = f"❌ No attendance record found for **{display_name}**"
                if date:
                    msg += f" on `{date}`"
                if session_id:
                    msg += f" (session: `{session_id}`)"
                await interaction.followup.send(msg, ephemeral=True)
                return

            # Remove the record
            count = await self.bot.attendance_repo.remove_attendance(
                user_id,
                date_id=date if not session_id else None,
                session_id=session_id,
            )

            if count > 0:
                msg = f"✅ Removed {count} attendance record(s) for **{display_name}**"
                if date:
                    msg += f" on `{date}`"
                if session_id:
                    msg += f" (session: `{session_id}`)"
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.followup.send(
                    f"❌ Failed to remove attendance record for **{display_name}**.",
                    ephemeral=True
                )

        except Exception as e:
            logger.error(f"Error removing attendance: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Failed to remove attendance: {str(e)}",
                ephemeral=True
            )

    # Background task for code rotation (shared with prefix commands)
    async def _rotate_code_loop(self):
        """Background task to rotate attendance codes every N seconds."""
        interval = self.bot.config.attendance.code_rotation_interval

        try:
            while self.session_manager.is_active:
                # Wait for the configured interval
                await asyncio.sleep(interval)

                if not self.session_manager.is_active:
                    break

                try:
                    # Generate new code
                    code_length = self.bot.config.attendance.code_length
                    old_code = self.session_manager.current_code
                    new_code = generate_code(code_length, previous_code=old_code)

                    # Update session manager
                    self.session_manager.update_code(new_code)

                    # Update the admin channel message with new code
                    channel_id = self.session_manager.channel_id
                    admin_channel = self.bot.get_channel(channel_id)
                    if admin_channel is None:
                        logger.warning(
                            f"Channel {channel_id} not in cache, fetching from API"
                        )
                        admin_channel = await self.bot.fetch_channel(channel_id)

                    if admin_channel and self.session_manager.message_id:
                        message = await admin_channel.fetch_message(
                            self.session_manager.message_id
                        )

                        code_embed = discord.Embed(
                            title="Attendance Code (Admin Only)",
                            description="Show this code on the projector for students:",
                            color=discord.Color.blue(),
                        )
                        code_embed.add_field(
                            name="Current Code",
                            value=f"# **`{new_code}`**",
                            inline=False,
                        )
                        code_embed.add_field(
                            name="Status",
                            value=f"{self.session_manager.get_submission_count()} student(s) submitted",
                            inline=False,
                        )
                        code_embed.set_footer(
                            text="Code changes every 15 seconds | Only the latest submission counts"
                        )

                        await message.edit(embed=code_embed)
                    else:
                        logger.warning(
                            f"Could not find admin channel ({channel_id}) or message_id is None"
                        )

                except discord.NotFound:
                    logger.warning("Admin message not found, stopping rotation")
                    break
                except Exception as e:
                    logger.error(f"Error in rotation iteration: {e}", exc_info=True)
                    # Continue rotation even if this iteration fails

        except asyncio.CancelledError:
            logger.info("Code rotation task cancelled")
        except Exception as e:
            logger.error(f"Error in code rotation loop: {e}", exc_info=True)

    async def _auto_close_loop(self):
        """Background task to automatically close attendance after 10 minutes."""
        try:
            # Wait for 10 minutes (600 seconds)
            await asyncio.sleep(600)

            # Check if session is still active
            if not self.session_manager.is_active:
                logger.info("Session already closed, skipping auto-close")
                return

            logger.info("Auto-closing attendance session after 10 minutes")

            # Cancel rotation task
            if self.rotation_task:
                self.rotation_task.cancel()
                try:
                    await self.rotation_task
                except asyncio.CancelledError:
                    pass

            # Get session data
            records, session_id = self.session_manager.end_session()

            # Save to database
            saved_count = await self.bot.attendance_repo.save_attendance_records(
                records, session_id
            )

            # Update the admin channel message to show it's closed
            try:
                admin_channel = self.bot.get_channel(
                    self.session_manager.channel_id
                    or self.bot.config.discord.admin_channel_id
                )
                if admin_channel and self.session_manager.message_id:
                    admin_message = await admin_channel.fetch_message(
                        self.session_manager.message_id
                    )

                    admin_embed = discord.Embed(
                        title="Attendance Session Auto-Closed",
                        description="This attendance session has automatically ended after 10 minutes.",
                        color=discord.Color.orange(),
                    )
                    admin_embed.add_field(
                        name="Total Submissions",
                        value=f"{saved_count} student(s)",
                        inline=False,
                    )
                    admin_embed.set_footer(text=f"Session ID: {session_id}")

                    await admin_message.edit(embed=admin_embed)
            except Exception as e:
                logger.warning(f"Could not update admin message: {e}")

            # Update the attendance channel message to show it's closed
            try:
                attendance_channel = self.bot.get_channel(
                    self.session_manager.attendance_channel_id
                    or self.bot.config.attendance.attendance_channel_id
                )
                attendance_msg_id = self.session_manager.attendance_message_id
                if attendance_channel and attendance_msg_id:
                    attendance_message = await attendance_channel.fetch_message(
                        attendance_msg_id
                    )

                    student_embed = discord.Embed(
                        title="Attendance is Now Closed",
                        description="This attendance session has automatically ended after 10 minutes.",
                        color=discord.Color.orange(),
                    )
                    student_embed.add_field(
                        name="Total Submissions",
                        value=f"{saved_count} student(s)",
                        inline=False,
                    )
                    student_embed.set_footer(text=f"Session ID: {session_id}")

                    await attendance_message.edit(embed=student_embed)
            except Exception as e:
                logger.warning(f"Could not update attendance channel message: {e}")

            # Reset session manager
            self.session_manager.reset()

            logger.info(
                f"Attendance auto-closed successfully. "
                f"Saved {saved_count} records, session_id: {session_id}"
            )

        except asyncio.CancelledError:
            logger.info("Auto-close task cancelled (manual close)")
        except Exception as e:
            logger.error(f"Error in auto-close loop: {e}", exc_info=True)

    # Error handlers for permission errors
    @open_attendance.error
    @close_attendance.error
    @export_attendance.error
    @excuse.error
    @mark_present.error
    @remove_attendance.error
    async def attendance_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        """Handle errors for attendance commands."""
        if isinstance(error, app_commands.errors.MissingPermissions):
            try:
                await interaction.response.send_message(
                    "❌ You need administrator permissions to use admin attendance commands.",
                    ephemeral=True,
                )
            except discord.InteractionResponded:
                await interaction.followup.send(
                    "❌ You need administrator permissions to use admin attendance commands.",
                    ephemeral=True,
                )
        else:
            logger.error(f"Attendance command error: {error}", exc_info=True)
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
    """Set up the Attendance Slash cog."""
    await bot.add_cog(AttendanceSlashCog(bot))
