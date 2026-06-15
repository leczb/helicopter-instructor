"""Unit tests for the update_checker module."""

import json
import os
import sys
import time
import unittest
from unittest import mock

base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(base_dir, "..", "plugin"))

if "xp" not in sys.modules:
    sys.modules["xp"] = mock.MagicMock()
if "xp_imgui" not in sys.modules:
    sys.modules["xp_imgui"] = mock.MagicMock()
if "imgui" not in sys.modules:
    sys.modules["imgui"] = mock.MagicMock()

from helicopter_instructor import update_checker
from helicopter_instructor.enums import UpdateStatus


class MockResponse(object):
    """Mocks urllib.request.urlopen context manager response."""

    def __init__(self, status, content):
        self.status = status
        self.content = content

    def read(self):
        return self.content

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class TestUpdateChecker(unittest.TestCase):
    """Verifies update checker functionality and background requests."""

    def test_parse_version(self):
        """Verifies semantic version parsing."""
        parse = update_checker.UpdateChecker._parse_version
        self.assertEqual(parse("2.1.72"), (2, 1, 72))
        self.assertEqual(parse("v2.1.73"), (2, 1, 73))
        self.assertEqual(parse("  v3.0.0-beta "), (3, 0, 0))
        self.assertEqual(parse("10"), (10,))
        self.assertEqual(parse("abc"), (0,))

    def test_is_newer_version(self):
        """Verifies version comparisons."""
        checker = update_checker.UpdateChecker("2.1.72")
        self.assertTrue(checker._is_newer_version("2.1.73"))
        self.assertTrue(checker._is_newer_version("v2.2.0"))
        self.assertTrue(checker._is_newer_version("3.0"))
        self.assertFalse(checker._is_newer_version("2.1.72"))
        self.assertFalse(checker._is_newer_version("v2.1.71"))
        self.assertFalse(checker._is_newer_version("invalid_version"))

    @mock.patch("urllib.request.urlopen")
    def test_check_for_updates_available(self, mock_urlopen):
        """Verifies status transitions to update_available when a newer version exists."""
        response_data = {
            "tag_name": "v2.1.74",
            "html_url": "https://github.com/leczb/helicopter-instructor/releases/tag/v2.1.74",
        }
        mock_urlopen.return_value = MockResponse(
            200, json.dumps(response_data).encode("utf-8")
        )

        checker = update_checker.UpdateChecker("2.1.72")
        self.assertEqual(checker.status, UpdateStatus.IDLE)

        checker.check_for_updates()

        # Wait for the background thread to finish
        start_time = time.time()
        while (
            checker.status == UpdateStatus.CHECKING
            and (time.time() - start_time) < 2.0
        ):
            time.sleep(0.01)

        self.assertEqual(checker.status, UpdateStatus.UPDATE_AVAILABLE)
        self.assertEqual(checker.latest_version, "v2.1.74")
        self.assertEqual(
            checker.update_url,
            "https://github.com/leczb/helicopter-instructor/releases/tag/v2.1.74",
        )

    @mock.patch("urllib.request.urlopen")
    def test_check_for_updates_up_to_date(self, mock_urlopen):
        """Verifies status is up_to_date when latest version matches or is older."""
        response_data = {
            "tag_name": "v2.1.72",
            "html_url": "https://github.com/leczb/helicopter-instructor/releases/tag/v2.1.72",
        }
        mock_urlopen.return_value = MockResponse(
            200, json.dumps(response_data).encode("utf-8")
        )

        checker = update_checker.UpdateChecker("2.1.72")
        checker.check_for_updates()

        start_time = time.time()
        while (
            checker.status == UpdateStatus.CHECKING
            and (time.time() - start_time) < 2.0
        ):
            time.sleep(0.01)

        self.assertEqual(checker.status, UpdateStatus.UP_TO_DATE)
        self.assertEqual(checker.latest_version, "v2.1.72")

    @mock.patch("urllib.request.urlopen")
    def test_check_for_updates_error(self, mock_urlopen):
        """Verifies status transitions to error when request fails."""
        mock_urlopen.side_effect = Exception("Connection timed out")

        checker = update_checker.UpdateChecker("2.1.72")
        checker.check_for_updates()

        start_time = time.time()
        while (
            checker.status == UpdateStatus.CHECKING
            and (time.time() - start_time) < 2.0
        ):
            time.sleep(0.01)

        self.assertEqual(checker.status, UpdateStatus.ERROR)

    @mock.patch("webbrowser.open")
    def test_open_update_url(self, mock_webbrowser_open):
        """Verifies open_update_url opens the correct web browser page."""
        checker = update_checker.UpdateChecker("2.1.72")
        checker.update_url = "https://example.com"
        checker.open_update_url()
        mock_webbrowser_open.assert_called_once_with("https://example.com")


if __name__ == "__main__":
    unittest.main()
