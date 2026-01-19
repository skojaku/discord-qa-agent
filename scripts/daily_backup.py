#!/usr/bin/env python3
"""
Daily Backup Script - Automated Google Sheets export with Discord notification.

This script runs independently of the Discord bot to perform scheduled backups.
It exports student progress data to Google Sheets and posts a notification to
a configured Discord channel.

Usage:
    python scripts/daily_backup.py

Environment Variables Required:
    DISCORD_TOKEN: Bot token for posting notifications
    BACKUP_NOTIFICATION_CHANNEL_ID: Channel ID where notifications will be posted

Configuration:
    Reads from config.yaml in project root for backup settings.
"""

import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from chibi.backup import BackupService
from chibi.config import load_config
from chibi.database.connection import Database
import aiohttp


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(project_root / "logs" / "daily_backup.log"),
    ],
)
logger = logging.getLogger(__name__)


async def post_to_discord(channel_id: str, token: str, content: str, embed: Optional[Dict] = None) -> bool:
    """Post a message to Discord channel using the bot token.

    Args:
        channel_id: Discord channel ID to post to
        token: Discord bot token
        content: Message content
        embed: Optional embed data

    Returns:
        True if successful, False otherwise
    """
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
    headers = {
        "Authorization": f"Bot {token}",
        "Content-Type": "application/json"
    }

    payload = {"content": content}
    if embed:
        payload["embeds"] = [embed]

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as response:
                if response.status in (200, 201):
                    logger.info("Successfully posted notification to Discord")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to post to Discord: {response.status} - {error_text}")
                    return False
    except Exception as e:
        logger.error(f"Error posting to Discord: {e}", exc_info=True)
        return False


def format_export_embed(result: Dict[str, Any]) -> Dict:
    """Format export result as a Discord embed.

    Args:
        result: Export result from BackupService

    Returns:
        Discord embed dictionary
    """
    summary = result.get('summary', {})

    # Build description with summary counts
    description_lines = [
        f"**Export Date:** {result.get('export_date', 'Unknown')}",
        f"**Schema Version:** {result.get('schema_version', 'Unknown')}",
        "",
        "**Records Exported:**",
        f"• Users: {summary.get('users', 0)}",
        f"• Quiz Attempts: {summary.get('quiz_attempts', 0)}",
        f"• Concept Mastery: {summary.get('concept_mastery', 0)}",
        f"• LLM Quiz Attempts: {summary.get('llm_quiz_attempts', 0)}",
        f"• Attendance: {summary.get('attendance', 0)}",
    ]

    embed = {
        "title": "Daily Backup Completed",
        "description": "\n".join(description_lines),
        "color": 0x00ff00,  # Green
        "url": result.get('spreadsheet_url', ''),
        "fields": [
            {
                "name": "Spreadsheet",
                "value": f"[Open in Google Sheets]({result.get('spreadsheet_url', '')})",
                "inline": False
            }
        ],
        "timestamp": datetime.utcnow().isoformat(),
        "footer": {
            "text": "Chibi Backup Service"
        }
    }

    return embed


async def perform_backup() -> Dict[str, Any]:
    """Perform the backup export operation.

    Returns:
        Export result dictionary

    Raises:
        Exception: If backup fails
    """
    logger.info("Starting daily backup process")

    # Load configuration
    config_path = project_root / "config.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    config = load_config(str(config_path))
    logger.info("Configuration loaded")

    # Initialize database
    database = Database(config.database.path)
    await database.connect()
    logger.info(f"Database connected: {config.database.path}")

    try:
        # Initialize backup service
        # Build config dict in expected format (nested structure)
        backup_config_dict = {
            'backup': {
                'google_sheets': {
                    'credentials_file': config.backup.credentials_file,
                    'token_file': config.backup.token_file,
                    'scopes': config.backup.scopes,
                    'folder_name': config.backup.folder_name,
                }
            }
        }

        backup_service = BackupService(
            database=database,
            config=backup_config_dict
        )
        logger.info("Backup service initialized")

        # Perform export
        result = await backup_service.export_progress()
        logger.info(f"Export completed: {result.get('spreadsheet_url', 'Unknown URL')}")

        return result

    finally:
        # Clean up database connection
        await database.close()
        logger.info("Database connection closed")


async def main():
    """Main entry point for daily backup script."""
    start_time = datetime.now()
    logger.info("="*60)
    logger.info(f"Daily Backup Script Started - {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("="*60)

    try:
        # Check required environment variables
        discord_token = os.getenv("DISCORD_TOKEN")
        channel_id = os.getenv("BACKUP_NOTIFICATION_CHANNEL_ID")

        if not discord_token:
            raise ValueError("DISCORD_TOKEN environment variable not set")

        if not channel_id:
            logger.warning(
                "BACKUP_NOTIFICATION_CHANNEL_ID not set - backup will run but no notification will be sent"
            )

        # Perform backup
        result = await perform_backup()

        # Post notification to Discord (if channel configured)
        if channel_id:
            embed = format_export_embed(result)
            success = await post_to_discord(
                channel_id=channel_id,
                token=discord_token,
                content="Daily student progress backup completed!",
                embed=embed
            )

            if not success:
                logger.error("Failed to post Discord notification, but backup succeeded")

        # Log success
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info("="*60)
        logger.info(f"Daily Backup Completed Successfully - Duration: {duration:.2f}s")
        logger.info(f"Spreadsheet URL: {result.get('spreadsheet_url', 'Unknown')}")
        logger.info("="*60)

        return 0

    except Exception as e:
        logger.error("="*60)
        logger.error(f"Daily Backup Failed: {e}", exc_info=True)
        logger.error("="*60)

        # Try to post error notification to Discord (if configured)
        channel_id = os.getenv("BACKUP_NOTIFICATION_CHANNEL_ID")
        discord_token = os.getenv("DISCORD_TOKEN")

        if channel_id and discord_token:
            error_embed = {
                "title": "Daily Backup Failed",
                "description": f"**Error:** {str(e)}",
                "color": 0xff0000,  # Red
                "timestamp": datetime.utcnow().isoformat(),
                "footer": {"text": "Chibi Backup Service"}
            }

            await post_to_discord(
                channel_id=channel_id,
                token=discord_token,
                content="Daily student progress backup failed!",
                embed=error_embed
            )

        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
