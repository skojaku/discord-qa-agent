"""Attendance tracking cog with admin prefix commands and student slash commands.

Admin commands use prefix commands (!command) to keep them hidden from students.
Student commands use slash commands for discoverability.
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
    ERROR_ADMIN_CHANNEL_NOT_CONFIGURED,
    ERROR_ADMIN_CHANNEL_ONLY,
    ERROR_ATTENDANCE_CHANNEL_NOT_CONFIGURED,
    ERROR_ATTENDANCE_CHANNEL_ONLY,
    ERROR_ATTENDANCE_EXPORT,
    ERROR_ATTENDANCE_SESSION_ACTIVE,
    ERROR_INVALID_CODE,
    ERROR_NO_ACTIVE_SESSION,
    ERROR_STUDENT_NOT_FOUND,
    ERROR_STUDENT_REGISTRATION_FAILED,
)
from ..services.attendance_session import AttendanceSessionManager
from ..utils.code_generator import generate_code
from ..utils.errors import (
    InvalidCodeError,
    NoActiveSessionError,
    SessionAlreadyActiveError,
)
from .utils import (
    defer_interaction,
    get_or_create_user_from_interaction,
    handle_prefix_command_errors,
    handle_slash_command_errors,
)

if TYPE_CHECKING:
    from ..bot import ChibiBot

logger = logging.getLogger(__name__)


def admin_channel_only():
    """Check that ensures command is only used in the admin channel."""

    async def predicate(ctx: commands.Context) -> bool:
        bot: "ChibiBot" = ctx.bot
        admin_channel_id = bot.config.discord.admin_channel_id

        if admin_channel_id is None:
            await ctx.send(ERROR_ADMIN_CHANNEL_NOT_CONFIGURED)
            return False

        if ctx.channel.id != admin_channel_id:
            await ctx.send(f"{ERROR_ADMIN_CHANNEL_ONLY} Please use <#{admin_channel_id}>.")
            return False

        return True

    return commands.check(predicate)


def attendance_channel_only():
    """Check that ensures slash command is only used in the attendance channel."""

    async def predicate(interaction: discord.Interaction) -> bool:
        bot: "ChibiBot" = interaction.client
        attendance_channel_id = bot.config.attendance.attendance_channel_id

        if attendance_channel_id is None:
            await interaction.response.send_message(
                ERROR_ATTENDANCE_CHANNEL_NOT_CONFIGURED, ephemeral=True
            )
            return False

        if interaction.channel_id != attendance_channel_id:
            await interaction.response.send_message(
                f"{ERROR_ATTENDANCE_CHANNEL_ONLY} Please use <#{attendance_channel_id}>.",
                ephemeral=True,
            )
            return False

        return True

    return app_commands.check(predicate)


class AttendanceCog(commands.Cog):
    """Cog for managing attendance tracking.

    Student Commands (slash):
        /register [student_id] [student_name] - Link Discord to student ID
        /here [code] - Submit attendance (attendance channel only)

    Admin Commands (prefix, admin channel only):
        !open_attendance - Start session with rotating codes
        !close_attendance - End session, save to database
        !export_attendance [session_id] - Export CSV
        !excuse [student] [date] - Mark student excused
        !mark_present [student] [date] [session_id] - Manual marking
        !remove_attendance [student] [date] [session_id] - Remove record
    """

    def __init__(self, bot: "ChibiBot"):
        self.bot = bot
        self.session_manager = AttendanceSessionManager()
        self.rotation_task: Optional[asyncio.Task] = None

    # ==================== Student Slash Commands ====================

    @app_commands.command(
        name="register", description="Register your student ID for attendance"
    )
    @app_commands.describe(
        student_id="Your student ID",
        student_name="Your full name (optional)",
    )
    @defer_interaction(thinking=True)
    @handle_slash_command_errors(
        error_message=ERROR_STUDENT_REGISTRATION_FAILED, context="/register"
    )
    async def register(
        self,
        interaction: discord.Interaction,
        student_id: str,
        student_name: Optional[str] = None,
    ):
        """Register student ID and name for gradebook integration."""
        # Get or create user first
        user = await get_or_create_user_from_interaction(
            self.bot.user_repo, interaction
        )

        # Check if already registered
        existing = await self.bot.user_repo.get_student_info(str(interaction.user.id))

        # Register the student
        await self.bot.user_repo.register_student(
            discord_id=str(interaction.user.id),
            student_id=student_id,
            student_name=student_name,
        )

        if existing:
            await interaction.followup.send(
                f"Registration updated!\n"
                f"Student ID: `{student_id}`\n"
                f"Name: {student_name if student_name else '(not provided)'}\n"
                f"Discord: {interaction.user.mention}",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                f"Registration successful!\n"
                f"Student ID: `{student_id}`\n"
                f"Name: {student_name if student_name else '(not provided)'}\n"
                f"Discord: {interaction.user.mention}\n\n"
                f"Your attendance records will now include your student information.",
                ephemeral=True,
            )

    @app_commands.command(
        name="here", description="Submit your attendance with the current code"
    )
    @app_commands.describe(code="The current attendance code shown on screen")
    @attendance_channel_only()
    async def here(self, interaction: discord.Interaction, code: str):
        """Submit attendance with the current code."""
        try:
            # Normalize code
            code_upper = code.upper().strip()

            # Get or create user first (to ensure user exists in DB)
            user = await get_or_create_user_from_interaction(
                self.bot.user_repo, interaction
            )

            # Submit attendance with database user_id
            await self.session_manager.submit_attendance(
                user.id,  # Use database user_id, not Discord ID
                interaction.user.display_name,
                code_upper,
            )

            # Confirm to student (ephemeral)
            await interaction.response.send_message(
                f"Attendance recorded for {interaction.user.mention}!\n"
                f"Code: `{code_upper}`\n"
                f"Time: {datetime.now().strftime('%H:%M:%S')}",
                ephemeral=True,
            )

        except NoActiveSessionError:
            await interaction.response.send_message(
                ERROR_NO_ACTIVE_SESSION, ephemeral=True
            )
        except InvalidCodeError:
            await interaction.response.send_message(
                f"Code `{code.upper()}` is {ERROR_INVALID_CODE}", ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error in /here command: {e}", exc_info=True)
            await interaction.response.send_message(
                f"Error submitting attendance: {str(e)}", ephemeral=True
            )

    # ==================== Admin Prefix Commands ====================

    @commands.command(name="open_attendance")
    @commands.has_permissions(administrator=True)
    @admin_channel_only()
    @handle_prefix_command_errors(
        error_message="Failed to open attendance.", context="!open_attendance"
    )
    async def open_attendance(self, ctx: commands.Context):
        """Start a new attendance session with rotating codes.

        Usage: !open_attendance
        """
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
                await ctx.send("Could not find admin channel. Please check configuration.")
                return

            if not attendance_channel:
                await ctx.send(
                    "Could not find attendance channel. Please check ATTENDANCE_CHANNEL_ID."
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

            # Confirm to admin
            await ctx.send(
                f"Attendance session started!\n"
                f"Current code: `{initial_code}`\n"
                f"Code displayed in this channel (show on projector)\n"
                f"Students notified in <#{attendance_channel_id}>"
            )

        except SessionAlreadyActiveError:
            await ctx.send(ERROR_ATTENDANCE_SESSION_ACTIVE)

    @commands.command(name="close_attendance")
    @commands.has_permissions(administrator=True)
    @admin_channel_only()
    @handle_prefix_command_errors(
        error_message="Failed to close attendance.", context="!close_attendance"
    )
    async def close_attendance(self, ctx: commands.Context):
        """Close the active attendance session and save records.

        Usage: !close_attendance
        """
        try:
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
            await ctx.send(
                f"Attendance session closed!\n"
                f"Total submissions saved: {saved_count}\n"
                f"Session ID: `{session_id}`"
            )

        except NoActiveSessionError:
            await ctx.send("No active attendance session to close.")

    @commands.command(name="export_attendance")
    @commands.has_permissions(administrator=True)
    @admin_channel_only()
    @handle_prefix_command_errors(
        error_message=ERROR_ATTENDANCE_EXPORT, context="!export_attendance"
    )
    async def export_attendance(
        self, ctx: commands.Context, session_id: Optional[str] = None
    ):
        """Export attendance records to CSV file.

        Usage: !export_attendance [session_id]
        """
        async with ctx.typing():
            # Export to CSV
            csv_content, record_count = await self.bot.attendance_repo.export_to_csv(
                session_id
            )

            if record_count == 0:
                await ctx.send("No records found to export.")
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
            await ctx.send(f"Exported {record_count} record(s) to CSV:", file=file)

    @commands.command(name="excuse")
    @commands.has_permissions(administrator=True)
    @admin_channel_only()
    @handle_prefix_command_errors(
        error_message="Failed to mark student as excused.", context="!excuse"
    )
    async def excuse(
        self, ctx: commands.Context, student: str, date: Optional[str] = None
    ):
        """Mark a student as excused for a date.

        Usage: !excuse <student> [date]
        Args:
            student: Student ID, Discord username, or Discord user ID
            date: Date in YYYY-MM-DD format (defaults to today)
        """
        async with ctx.typing():
            # Resolve student
            student_info = await self.bot.attendance_repo.find_student(student)
            if not student_info:
                await ctx.send(
                    f"Student not found: `{student}`\n"
                    f"Try using their student ID, Discord username, or Discord user ID."
                )
                return

            user_id = student_info["user_id"]
            display_name = (
                student_info.get("student_name")
                or student_info.get("username")
                or student_info.get("student_id")
                or str(user_id)
            )

            # Default to today's date
            if not date:
                date = datetime.now().strftime("%Y-%m-%d")

            # Validate date format
            try:
                datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                await ctx.send(
                    f"Invalid date format: `{date}`\n"
                    f"Please use YYYY-MM-DD format (e.g., 2025-12-01)."
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
                    await ctx.send(
                        f"Marked **{display_name}** as excused for `{date}`\n"
                        f"(Updated existing attendance record)"
                    )
                else:
                    await ctx.send(
                        f"Failed to update attendance record for **{display_name}**."
                    )
            else:
                # Create new excused record
                username = (
                    student_info.get("username")
                    or student_info.get("student_name")
                    or student
                )
                result = await self.bot.attendance_repo.add_manual_attendance(
                    user_id=user_id, username=username, date_id=date, status="excused"
                )
                await ctx.send(
                    f"Marked **{display_name}** as excused for `{date}`\n"
                    f"Session ID: `{result['session_id']}`"
                )

    @commands.command(name="mark_present")
    @commands.has_permissions(administrator=True)
    @admin_channel_only()
    @handle_prefix_command_errors(
        error_message="Failed to mark student as present.", context="!mark_present"
    )
    async def mark_present(
        self,
        ctx: commands.Context,
        student: str,
        date: Optional[str] = None,
        session_id: Optional[str] = None,
    ):
        """Manually mark a student as present for a specific date.

        Usage: !mark_present <student> [date] [session_id]
        Args:
            student: Student ID, Discord username, or Discord user ID
            date: Date in YYYY-MM-DD format (defaults to today)
            session_id: Optional specific session ID
        """
        async with ctx.typing():
            # Resolve student
            student_info = await self.bot.attendance_repo.find_student(student)
            if not student_info:
                await ctx.send(
                    f"Student not found: `{student}`\n"
                    f"Try using their student ID, Discord username, or Discord user ID."
                )
                return

            user_id = student_info["user_id"]
            display_name = (
                student_info.get("student_name")
                or student_info.get("username")
                or student_info.get("student_id")
                or str(user_id)
            )

            # Default to today's date
            if not date:
                date = datetime.now().strftime("%Y-%m-%d")

            # Validate date format
            try:
                datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                await ctx.send(
                    f"Invalid date format: `{date}`\n"
                    f"Please use YYYY-MM-DD format (e.g., 2025-12-01)."
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
                    await ctx.send(
                        f"Marked **{display_name}** as present for `{date}`\n"
                        f"(Updated existing record - was previously `{existing.get('status', 'unknown')}`)"
                    )
                else:
                    await ctx.send(
                        f"Failed to update attendance record for **{display_name}**."
                    )
            else:
                # Create new attendance record
                username = (
                    student_info.get("username")
                    or student_info.get("student_name")
                    or student
                )
                result = await self.bot.attendance_repo.add_manual_attendance(
                    user_id=user_id,
                    username=username,
                    date_id=date,
                    session_id=session_id,
                    status="present",
                )
                await ctx.send(
                    f"Marked **{display_name}** as present for `{date}`\n"
                    f"Session ID: `{result['session_id']}`"
                )

    @commands.command(name="remove_attendance")
    @commands.has_permissions(administrator=True)
    @admin_channel_only()
    @handle_prefix_command_errors(
        error_message="Failed to remove attendance.", context="!remove_attendance"
    )
    async def remove_attendance(
        self,
        ctx: commands.Context,
        student: str,
        date: Optional[str] = None,
        session_id: Optional[str] = None,
    ):
        """Remove a student's attendance record.

        Usage: !remove_attendance <student> [date] [session_id]
        Args:
            student: Student ID, Discord username, or Discord user ID
            date: Date in YYYY-MM-DD format
            session_id: Optional specific session ID
        """
        # Require at least one filter (date or session_id)
        if not date and not session_id:
            await ctx.send(
                "Please specify either a date or session_id to remove attendance records."
            )
            return

        async with ctx.typing():
            # Resolve student
            student_info = await self.bot.attendance_repo.find_student(student)
            if not student_info:
                await ctx.send(
                    f"Student not found: `{student}`\n"
                    f"Try using their student ID, Discord username, or Discord user ID."
                )
                return

            user_id = student_info["user_id"]
            display_name = (
                student_info.get("student_name")
                or student_info.get("username")
                or student_info.get("student_id")
                or str(user_id)
            )

            # Validate date format if provided
            if date:
                try:
                    datetime.strptime(date, "%Y-%m-%d")
                except ValueError:
                    await ctx.send(
                        f"Invalid date format: `{date}`\n"
                        f"Please use YYYY-MM-DD format (e.g., 2025-12-01)."
                    )
                    return

            # Check if record exists before removing
            existing = await self.bot.attendance_repo.get_record(
                user_id,
                date_id=date if not session_id else None,
                session_id=session_id,
            )

            if not existing:
                msg = f"No attendance record found for **{display_name}**"
                if date:
                    msg += f" on `{date}`"
                if session_id:
                    msg += f" (session: `{session_id}`)"
                await ctx.send(msg)
                return

            # Remove the record
            count = await self.bot.attendance_repo.remove_attendance(
                user_id,
                date_id=date if not session_id else None,
                session_id=session_id,
            )

            if count > 0:
                msg = f"Removed {count} attendance record(s) for **{display_name}**"
                if date:
                    msg += f" on `{date}`"
                if session_id:
                    msg += f" (session: `{session_id}`)"
                await ctx.send(msg)
            else:
                await ctx.send(
                    f"Failed to remove attendance record for **{display_name}**."
                )

    # ==================== Background Tasks ====================

    async def _rotate_code_loop(self):
        """Background task to rotate attendance codes every N seconds."""
        interval = self.bot.config.attendance.code_rotation_interval

        try:
            while self.session_manager.is_active:
                # Wait for the configured interval
                await asyncio.sleep(interval)

                if not self.session_manager.is_active:
                    break

                # Generate new code
                code_length = self.bot.config.attendance.code_length
                old_code = self.session_manager.current_code
                new_code = generate_code(code_length, previous_code=old_code)

                # Update session manager
                self.session_manager.update_code(new_code)

                # Update the admin channel message with new code
                try:
                    admin_channel = self.bot.get_channel(self.session_manager.channel_id)
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

                except discord.NotFound:
                    logger.warning("Admin message not found, stopping rotation")
                    break
                except Exception as e:
                    logger.error(f"Error updating admin message: {e}")
                    # Continue rotation even if message update fails

        except asyncio.CancelledError:
            logger.info("Code rotation task cancelled")
        except Exception as e:
            logger.error(f"Error in code rotation loop: {e}", exc_info=True)


async def setup(bot: "ChibiBot"):
    """Set up the Attendance cog."""
    await bot.add_cog(AttendanceCog(bot))
