"""Logging utility module for Helicopter Flight Instructor."""

import logging
import logging.handlers
import os

# Create standard package-level logger
logger = logging.getLogger("helicopter_instructor")


class XPLogHandler(logging.Handler):
    """Custom logging Handler that mirrors records to X-Plane's xp.log."""

    def emit(self, record):
        """Emits a log record to X-Plane's log.

        Args:
            record: The logging.LogRecord instance to emit.
        """
        try:
            msg = self.format(record)
            # Safely import xp at runtime so tests run without XPLM
            import xp
            if hasattr(xp, "log") and callable(xp.log):
                xp.log(msg)
        except Exception:
            pass


def setup_logging(plugin_dir, level=logging.INFO):
    """Configures the logger, ensuring handlers are not duplicated on reloads.

    Args:
        plugin_dir: Absolute path to the plugin package directory.
        level: The logging level threshold.
    """
    logger.setLevel(level)

    # Remove existing handlers to avoid duplicates on plugin reload
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    # Formatter for the dedicated log file (with timestamps, lines, etc.)
    file_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] [%(filename)s:%(lineno)d]: %(message)s"
    )

    # Formatter for X-Plane's log (no timestamp since X-Plane handles it)
    xp_formatter = logging.Formatter(
        "[%(levelname)s] %(message)s"
    )

    # 1. Setup RotatingFileHandler (in plugin package directory)
    log_file = os.path.join(plugin_dir, "helicopter_instructor.log")
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=5 * 1024 * 1024, backupCount=1, encoding="utf-8"
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        # If writing to the file fails, at least attempt to report it
        try:
            import xp
            if hasattr(xp, "log") and callable(xp.log):
                xp.log(
                    "Helicopter Instructor: Failed to create log file "
                    f"at {log_file}: {e}"
                )
        except Exception:
            pass

    # 2. Setup XPLogHandler
    xp_handler = XPLogHandler()
    xp_handler.setFormatter(xp_formatter)
    logger.addHandler(xp_handler)

    logger.info("====================================================")
    logger.info("Helicopter Instructor logging system initialized.")
    logger.info("====================================================")
