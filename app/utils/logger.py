"""Structured logging setup using loguru."""
import sys
from pathlib import Path
from loguru import logger

from app.config.settings import settings


def setup_logger() -> None:
    """Configure structured logging for stdout and file storage."""
    Path("logs").mkdir(exist_ok=True)
    logger.remove()

    # Console stdout logger
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=settings.log_level,
        colorize=True,
    )

    # File logger with rotation and compression
    logger.add(
        settings.log_file,
        rotation="10 MB",
        retention="30 days",
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
        level="DEBUG",
    )


__all__ = ["logger", "setup_logger"]
