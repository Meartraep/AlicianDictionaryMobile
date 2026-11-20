# -*- coding: utf-8 -*-
"""Unit tests for release tag vs. APK/Gradle versionName guards."""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[4]
SCRIPTS = REPO / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import verify_release_apk  # noqa: E402


class VerifyReleaseApkVersionTests(unittest.TestCase):
    def test_normalize_release_version(self) -> None:
        self.assertEqual(verify_release_apk.normalize_release_version("v1.12.2"), "1.12.2")
        self.assertEqual(verify_release_apk.normalize_release_version("V1.12.2"), "1.12.2")
        self.assertEqual(verify_release_apk.normalize_release_version("1.12.2"), "1.12.2")
        self.assertEqual(verify_release_apk.normalize_release_version(" v1.12.2-rc1 "), "1.12.2-rc1")

    def test_check_gradle_version_matches_current_build_file(self) -> None:
        gradle_file = REPO / "app" / "build.gradle.kts"
        version_name, version_code = verify_release_apk.parse_gradle_version(
            gradle_file.read_text(encoding="utf-8")
        )
        self.assertEqual(version_name, "1.12.2")
        self.assertEqual(version_code, 17)
        self.assertEqual(
            verify_release_apk.check_gradle_version(gradle_file, "v1.12.2"),
            [],
        )

    def test_check_gradle_version_rejects_tag_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            gradle_file = Path(tmp) / "build.gradle.kts"
            gradle_file.write_text(
                'android {\n    defaultConfig {\n        versionCode = 16\n        versionName = "1.12.0"\n    }\n}\n',
                encoding="utf-8",
            )
            problems = verify_release_apk.check_gradle_version(gradle_file, "v1.12.1")
            self.assertEqual(len(problems), 1)
            self.assertIn("1.12.0", problems[0])
            self.assertIn("1.12.1", problems[0])

    def test_parse_and_check_aapt2_badging_version(self) -> None:
        sample_badging = (
            "package: name='com.meartraep.alician.mobile' versionCode='17' "
            "versionName='1.12.2' platformBuildVersionName='16'\n"
            "sdkVersion:'24'\n"
        )
        self.assertEqual(
            verify_release_apk.parse_aapt2_badging_version(sample_badging),
            ("1.12.2", 17),
        )

        with tempfile.TemporaryDirectory() as tmp:
            fake_apk = Path(tmp) / "app.apk"
            fake_apk.write_bytes(b"")
            fake_aapt2 = Path(tmp) / "aapt2"
            fake_aapt2.write_bytes(b"")

            completed = subprocess.CompletedProcess(
                args=[str(fake_aapt2), "dump", "badging", str(fake_apk)],
                returncode=0,
                stdout=sample_badging,
                stderr="",
            )
            with mock.patch("verify_release_apk.subprocess.run", return_value=completed):
                self.assertEqual(
                    verify_release_apk.check_apk_version(fake_apk, "v1.12.2", aapt2=fake_aapt2),
                    [],
                )
                mismatch = verify_release_apk.check_apk_version(
                    fake_apk, "v1.12.3", aapt2=fake_aapt2
                )
                self.assertEqual(len(mismatch), 1)
                self.assertIn("1.12.2", mismatch[0])
                self.assertIn("1.12.3", mismatch[0])


if __name__ == "__main__":
    unittest.main()
