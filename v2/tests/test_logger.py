"""Unit tests for the logging utility module."""

import logging
import logging.handlers
import os
import sys
import tempfile
import unittest
from unittest import mock

base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(
    0, os.path.join(base_dir, "..", "plugin", "helicopter_instructor")
)
sys.path.insert(0, os.path.join(base_dir, "..", "plugin"))

# Conditionally mock xp
if "xp" not in sys.modules:
    mock_xp = mock.MagicMock()
    sys.modules["xp"] = mock_xp
else:
    mock_xp = sys.modules["xp"]

from helicopter_instructor import logger


class TestLogger(unittest.TestCase):

    def setUp(self):
        # Reset logging configuration or the package logger handlers
        self.package_logger = logging.getLogger("helicopter_instructor")
        self.original_handlers = list(self.package_logger.handlers)
        for handler in self.original_handlers:
            self.package_logger.removeHandler(handler)

        self.temp_dir = tempfile.TemporaryDirectory()
        mock_xp.reset_mock()
        # Ensure xp.log exists on the mock
        if not hasattr(mock_xp, "log") or not callable(mock_xp.log):
            mock_xp.log = mock.MagicMock()

    def tearDown(self):
        # Restore original handlers
        for handler in list(self.package_logger.handlers):
            self.package_logger.removeHandler(handler)
            handler.close()
        for handler in self.original_handlers:
            self.package_logger.addHandler(handler)
        self.temp_dir.cleanup()

    def test_setup_logging_registers_handlers(self):
        """Verify setup_logging registers correct handlers."""
        logger.setup_logging(self.temp_dir.name)

        handlers = self.package_logger.handlers
        self.assertEqual(len(handlers), 2)

        file_handler = None
        xp_handler = None
        for h in handlers:
            if isinstance(h, logging.handlers.RotatingFileHandler):
                file_handler = h
            elif isinstance(h, logger.XPLogHandler):
                xp_handler = h

        self.assertIsNotNone(file_handler)
        self.assertIsNotNone(xp_handler)

        # Check that file handler writes to the correct path
        expected_log_path = os.path.join(
            self.temp_dir.name, "helicopter_instructor.log"
        )
        self.assertEqual(
            file_handler.baseFilename, os.path.abspath(expected_log_path)
        )

    def test_multiple_calls_clear_old_handlers(self):
        """Verify multiple calls to setup_logging clean up handlers."""
        logger.setup_logging(self.temp_dir.name)
        first_handlers = list(self.package_logger.handlers)

        # Call setup_logging again
        logger.setup_logging(self.temp_dir.name)
        second_handlers = list(self.package_logger.handlers)

        self.assertEqual(len(second_handlers), 2)
        # Ensure old handlers were closed and removed
        for h in first_handlers:
            self.assertNotIn(h, second_handlers)

    def test_xp_log_handler_forwards_to_xp_log(self):
        """Verify XPLogHandler calls mock_xp.log."""
        logger.setup_logging(self.temp_dir.name)
        self.package_logger.info("Test message for XPLogHandler")

        # Verify that mock_xp.log was called
        # The formatter format: "[INFO] Test message for XPLogHandler"
        mock_xp.log.assert_any_call("[INFO] Test message for XPLogHandler")

    def test_fallback_when_xp_log_is_unavailable(self):
        """Verify logging handles missing or failing xp.log silently."""
        # 1. Test when xp.log raises an exception
        with mock.patch("xp.log", side_effect=Exception("X-Plane log failure")):
            logger.setup_logging(self.temp_dir.name)
            # This should log to file and handle failure silently
            self.package_logger.info("Silent failure test")

        # 2. Test when xp has no log attribute (spec=[] ensures no log)
        mock_xp_no_log = mock.MagicMock(spec=[])
        with mock.patch.dict(sys.modules, {"xp": mock_xp_no_log}):
            try:
                logger.setup_logging(self.temp_dir.name)
                # Re-fetch package logger (uses dynamic xp inside emit())
                self.package_logger.info("Missing attribute test")
            except Exception as e:
                self.fail(
                    "setup_logging raised exception with missing xp.log: "
                    f"{e}"
                )


if __name__ == "__main__":
    unittest.main()
