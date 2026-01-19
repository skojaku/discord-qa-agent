"""Main entry point for the Chibi Discord bot."""

import asyncio
import logging
import os
import sys
from pathlib import Path

from chibi.bot import create_bot
from chibi.config import load_config


def setup_logging():
    """Configure logging for the bot."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("chibi.log"),
        ],
    )


def main():
    """Run the Chibi Discord bot."""
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)

    try:
        # Load configuration
        config_path = "config.yaml"
        if not Path(config_path).exists():
            logger.error(f"Configuration file not found: {config_path}")
            logger.error("Please create config.yaml from config.yaml.example")
            sys.exit(1)

        config = load_config(config_path)

        # Get Discord token
        token = os.getenv("DISCORD_TOKEN") or config.discord.token
        if not token:
            logger.error("Discord token not found!")
            logger.error("Set DISCORD_TOKEN in .env or config.yaml")
            sys.exit(1)

        # Create and run the bot
        logger.info("Starting Chibi Discord bot...")
        bot = create_bot(config_path)
        bot.run(token)

    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
