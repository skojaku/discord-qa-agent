#!/usr/bin/env python3
"""Main entry point for Chibi Discord bot."""

import asyncio
import logging
import sys

from chibi.bot import create_bot
from chibi.config import load_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger(__name__)


async def main():
    """Main entry point."""
    logger.info("Starting Chibi Discord bot...")

    # Load configuration
    try:
        config = load_config()
    except FileNotFoundError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)

    # Validate Discord token
    if not config.discord_token:
        logger.error("DISCORD_TOKEN environment variable not set")
        logger.info("Please copy .env.example to .env and add your Discord bot token")
        sys.exit(1)

    # Create and run bot
    bot = create_bot()

    try:
        await bot.start(config.discord_token)
    except discord.LoginFailure:
        logger.error("Invalid Discord token")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    finally:
        await bot.close()


if __name__ == "__main__":
    try:
        import discord  # noqa: F401

        asyncio.run(main())
    except ImportError:
        print("Please install dependencies: pip install -r requirements.txt")
        sys.exit(1)
