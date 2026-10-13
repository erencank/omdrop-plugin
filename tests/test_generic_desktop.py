"""Tests for generic desktop fallbacks (notify-send, xdg-open).

When Omarchy-specific commands (omarchy-notification-send, omarchy-launch-browser)
are absent on a generic Linux system, omdrop falls back cleanly to freedesktop
standards without errors.
"""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OMDROP = ROOT / "bin" / "omdrop"


class GenericDesktopTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.log = self.root / "log"

        # Safe isolated PATH containing only system utilities and our mocks
        self.env = os.environ.copy()
        self.env.update(
            PATH=f"{self.bin}:/usr/bin:/bin",
            LOG=str(self.log),
            XDG_CONFIG_HOME=str(self.root / "config"),
            XDG_DATA_HOME=str(self.root / "data"),
        )
        self.mock_cmd("wl-copy")

    def mock_cmd(self, name):
        path = self.bin / name
        path.write_text(f'#!/bin/sh\nprintf "{name}|%s\\n" "$*" >> "$LOG"\n')
        path.chmod(0o755)

    def run_omdrop(self, *args):
        return subprocess.run([OMDROP, *args], env=self.env, capture_output=True, text=True)

    def logged(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def test_notify_send_called_when_omarchy_notification_missing(self):
        self.mock_cmd("notify-send")
        test_file = self.root / "photo.jpg"
        test_file.write_bytes(b"image data")

        res = self.run_omdrop("handle", str(test_file))
        self.assertEqual(res.returncode, 0, res.stderr)

        logs = self.logged()
        self.assertTrue(any("notify-send|" in l and "photo.jpg" in l for l in logs), logs)
        self.assertTrue(any("-a AirDrop" in l for l in logs), logs)
        self.assertTrue(any(f"-i {test_file}" in l for l in logs), logs)

    def test_xdg_open_called_when_omarchy_browser_missing(self):
        self.mock_cmd("xdg-open")
        link = self.root / "test.url"
        link.write_bytes(b"[InternetShortcut]\r\nURL=https://example.com/test\r\n")

        res = self.run_omdrop("open-link", str(link))
        self.assertEqual(res.returncode, 0, res.stderr)

        logs = self.logged()
        self.assertTrue(any("xdg-open|https://example.com/test" in l for l in logs), logs)

    def test_omarchy_tools_still_preferred_if_installed(self):
        self.mock_cmd("omarchy-notification-send")
        self.mock_cmd("notify-send")
        test_file = self.root / "document.pdf"
        test_file.write_bytes(b"pdf data")

        res = self.run_omdrop("handle", str(test_file))
        self.assertEqual(res.returncode, 0, res.stderr)

        logs = self.logged()
        self.assertTrue(any("omarchy-notification-send|" in l for l in logs), logs)
        self.assertFalse(any("notify-send|" in l for l in logs), logs)


if __name__ == "__main__":
    unittest.main()
