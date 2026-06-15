"""Automated update checker for Helicopter Flight Instructor.

Queries the GitHub releases API asynchronously to check for newer plugin versions.
"""

import json
import logging
import ssl
import threading
import urllib.request
import webbrowser

from helicopter_instructor.enums import UpdateStatus

log = logging.getLogger("helicopter_instructor")


class UpdateChecker(object):
    """Manages background checking of update status from GitHub Releases."""

    def __init__(self, current_version):
        """Initializes the UpdateChecker.

        Args:
            current_version (str): The current local version of the plugin.
        """
        self.current_version = current_version
        self.status = UpdateStatus.IDLE
        self.latest_version = None
        self.update_url = None
        self._thread = None
        self._lock = threading.Lock()

    def check_for_updates(self):
        """Kicks off a background thread to check for updates."""
        with self._lock:
            if self.status == UpdateStatus.CHECKING:
                return
            self.status = UpdateStatus.CHECKING
            self.latest_version = None
            self.update_url = None

        self._thread = threading.Thread(target=self._run_check, daemon=True)
        self._thread.start()

    def _run_check(self):
        """Synchronous check logic run within a background thread."""
        try:
            url = (
                "https://api.github.com/repos/leczb/"
                "helicopter-instructor/releases/latest"
            )
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Helicopter-Flight-Instructor-Plugin"},
            )
            context = ssl.create_default_context()

            with urllib.request.urlopen(
                req, context=context, timeout=10
            ) as response:
                if response.status != 200:
                    raise ValueError(f"HTTP Status {response.status}")

                raw_data = response.read().decode("utf-8")
                data = json.loads(raw_data)

                tag_name = data.get("tag_name")
                html_url = data.get("html_url")

                if not tag_name or not html_url:
                    raise ValueError(
                        "Invalid release data received from GitHub."
                    )

                if self._is_newer_version(tag_name):
                    with self._lock:
                        self.status = UpdateStatus.UPDATE_AVAILABLE
                        self.latest_version = tag_name
                        self.update_url = html_url
                    log.info(
                        f"Update available: {tag_name} "
                        f"(Current: {self.current_version})"
                    )
                else:
                    with self._lock:
                        self.status = UpdateStatus.UP_TO_DATE
                        self.latest_version = tag_name
                    log.info(
                        f"Plugin is up to date (Version {self.current_version})."
                    )

        except Exception as e:
            with self._lock:
                self.status = UpdateStatus.ERROR
            log.error(f"Error checking for updates: {e}")

    def _is_newer_version(self, tag_name):
        """Compares a remote tag name with the current version.

        Args:
            tag_name (str): The version tag from GitHub.

        Returns:
            bool: True if the remote version is newer, False otherwise.
        """
        try:
            curr_parsed = self._parse_version(self.current_version)
            latest_parsed = self._parse_version(tag_name)
            return latest_parsed > curr_parsed
        except Exception as e:
            log.warning(
                f"Could not parse/compare versions "
                f"'{self.current_version}' vs '{tag_name}': {e}"
            )
            return False

    @staticmethod
    def _parse_version(version_str):
        """Parses a version string into an integer tuple for comparison.

        Args:
            version_str (str): Semantic version string (e.g. 'v2.1.72').

        Returns:
            tuple: An integer tuple representing the version.
        """
        cleaned = version_str.strip().lower()
        if cleaned.startswith("v"):
            cleaned = cleaned[1:]

        parts = []
        for p in cleaned.split("."):
            digits = []
            for c in p:
                if c.isdigit():
                    digits.append(c)
                else:
                    break
            if digits:
                parts.append(int("".join(digits)))
            else:
                parts.append(0)
        return tuple(parts)

    def open_update_url(self):
        """Opens the update URL in the user's default web browser."""
        if self.update_url:
            try:
                webbrowser.open(self.update_url)
            except Exception as e:
                log.error(
                    f"Failed to open update URL '{self.update_url}': {e}"
                )
