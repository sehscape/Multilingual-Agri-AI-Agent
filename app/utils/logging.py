"""Structured logging setup for the entire application."""
import logging
import sys
from app.config import LOG_LEVEL


def enable_utf8_console() -> None:
    """Force stdout/stderr to UTF-8 so non-ASCII output (₹, →, Devanagari, …)
    does not crash on Windows consoles that default to cp1252.

    Safe to call multiple times; a no-op on streams that cannot be reconfigured.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8")
            except (ValueError, OSError):
                pass


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(levelname)-5s | %(name)s | %(message)s",
            datefmt="%H:%M:%S",
        )
    )
    logger.addHandler(handler)
    logger.propagate = False
    return logger
