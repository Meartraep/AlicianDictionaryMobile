# -*- coding: utf-8 -*-
"""P4 acceptance tests — database governance identity, recovery points, restore,
and the Windows connection-leak regression.

Spec: ``.luna-review/p4-spec.md`` (section 测试, 6 checks), bridge layer.

Coverage:

1. ``gov_identity`` initial state (version 1, published_at/format/notes, sha256 64 hex
   equal to the on-disk file, real counts, ``local_edits == 0`` /
   ``local_modified == False``, ``backup_count == 0`` / ``latest_backup is None``);
2. after editing one word: ``local_edits >= 1`` and ``local_modified is True``;
3. ``gov_backup_create``: ``backup_count + 1``, ``latest_backup`` with the full sidecar
   shape, and the snapshot does not rewrite the live database;
4. ``gov_backup_restore`` round trip: ok, safety backup added, version not lowered,
   services usable, ``local_edits`` back to the snapshot value, and the edited content
   reverted;
5. **connection-leak regression (commit 335e62a)**: ``gov_identity`` ×20 followed by
   ``gov_backup_restore`` must succeed.  Before the fix, ``with sqlite3.connect(...)``
   committed but never closed, and the leaked handles/locks made the atomic file replace
   fail on Windows ("替换数据库文件失败。"/WinError 5);
6. the shipped asset SHA-256 never changes.

Every test copies ``app/src/main/assets/translated.db`` into its own
``tempfile.mkdtemp()`` and drives the bridge with
``mobile_bridge.initialize(<copy>, <tmp>/data)``; the temp data dir / cwd / env are
restored in cleanup.

Run::

    cd app/src/test/python
    $env:PYTHONPATH = '<repo>/app/src/main/python'
    python -m unittest test_governance -v
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
MAIN_PYTHON = REPO / "app" / "src" / "main" / "python"
ASSET_DB = REPO / "app" / "src" / "main" / "assets" / "translated.db"

if str(MAIN_PYTHON) not in sys.path:
    sys.path.insert(0, str(MAIN_PYTHON))

try:  # Windows console is GBK; Chinese assertion messages must not crash.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:  # pragma: no cover
    pass

from webui_backend.dictionary_core import DictionaryConfig  # noqa: E402

import mobile_bridge  # noqa: E402


ASSET_SHA256 = hashlib.sha256(ASSET_DB.read_bytes()).hexdigest()

#: Real shipped-data facts re-checked in the tests.
EXPECTED_DB_VERSION = 2
EXPECTED_WORDS = 1339
EXPECTED_SONGS = 53
EXPECTED_BUSINESS_TABLES = 13
REAL_EDIT_WORD = "Finz"


def sha256_file(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_sql(path, statement: str, args=()):
    connection = sqlite3.connect(str(path))
    try:
        return [tuple(row) for row in connection.execute(statement, args).fetchall()]
    finally:
        connection.close()


class BridgeGovernanceTests(unittest.TestCase):
    """Bridge-level governance tests on one real-database copy per test."""

    def setUp(self) -> None:
        self.tmpdir = Path(tempfile.mkdtemp(prefix="p4-governance-"))
        self.data_dir = self.tmpdir / "data"
        self.data_dir.mkdir()
        self.db_path = str(self.data_dir / "translated.db")
        shutil.copyfile(ASSET_DB, self.db_path)
        self.assertEqual(
            sha256_file(self.db_path),
            ASSET_SHA256,
            "the database under test must be a byte-for-byte copy of the shipped asset",
        )

        self._saved_cwd = os.getcwd()
        self._saved_env = {
            name: os.environ.get(name) for name in ("ALICIAN_DB_PATH", "ALICIAN_LITE_BUILD")
        }
        self._saved_config = (DictionaryConfig.DB_NAME, DictionaryConfig.CURRENT_DB)
        self.addCleanup(self._cleanup)

        init = json.loads(mobile_bridge.initialize(self.db_path, str(self.data_dir)))
        self.assertTrue(init.get("ok"), init.get("message"))
        self.core = mobile_bridge._data_core
        self.assertIsNotNone(self.core)

    def _cleanup(self) -> None:
        try:
            mobile_bridge._close_services()
        except Exception:  # pragma: no cover
            pass
        try:
            os.chdir(self._saved_cwd)
        except Exception:  # pragma: no cover
            pass
        for name, value in self._saved_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        DictionaryConfig.DB_NAME, DictionaryConfig.CURRENT_DB = self._saved_config
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    # ------------------------------------------------------------ helpers

    def call(self, method: str, **payload):
        return json.loads(
            mobile_bridge.invoke(method, json.dumps(payload, ensure_ascii=False))
        )

    def backup_count(self) -> int:
        directory = self.data_dir / "backups"
        return len(list(directory.glob("*.db"))) if directory.is_dir() else 0

    def real_word_entry(self, word: str = REAL_EDIT_WORD):
        search = self.call("dictionary_search", query=word, exact=True, position="any")
        self.assertTrue(search.get("ok"), search.get("message"))
        entries = [
            entry
            for section in search.get("sections") or []
            for entry in section.get("entries") or []
            if entry.get("kind") == "alice" and entry.get("word") == word
        ]
        self.assertEqual(len(entries), 1, "real data changed: %r is not one alice entry" % word)
        return entries[0]

    def edit_word(self, entry, new_explanation: str):
        senses = [
            {
                "id": sense["id"],
                "explanation": sense["explanation"],
                "english": sense["english_gloss"],
                "japanese": sense["japanese_gloss"],
            }
            for sense in entry["senses"]
        ]
        result = self.call(
            "dictionary_update_word",
            headword_id=entry["headword_id"],
            original_word=entry["word"],
            word=entry["word"],
            display_explanation=new_explanation,
            senses=senses,
        )
        self.assertTrue(result.get("ok"), result.get("message"))
        return result

    def assert_asset_unmodified(self) -> None:
        self.assertEqual(
            hashlib.sha256(ASSET_DB.read_bytes()).hexdigest(),
            ASSET_SHA256,
            "the shipped database asset must never be modified by the tests",
        )

    # --------------------------------------------------- check 1
    def test_gov_identity_initial_state(self):
        identity = self.call("gov_identity")
        self.assertTrue(identity["ok"], identity.get("message"))

        self.assertEqual(identity["db_version"], EXPECTED_DB_VERSION)
        self.assertTrue(str(identity["published_at"]).strip(), "published_at must be present")
        self.assertGreaterEqual(len(str(identity["published_at"])), 10)
        self.assertTrue(str(identity["notes"]).strip())
        self.assertEqual(identity["format"], "alician-lite")

        sha = str(identity["sha256"])
        self.assertEqual(len(sha), 64, "sha256 must be a hex digest")
        int(sha, 16)  # raises if it is not hex
        self.assertEqual(sha, sha256_file(self.db_path), "identity sha256 must describe the live file")
        self.assertEqual(sha, ASSET_SHA256, "a fresh identity read must not modify the database")
        self.assertGreater(int(identity["size"]), 0)
        self.assertTrue(str(identity["modified"]).strip())

        self.assertEqual(int(identity["word_count"]), EXPECTED_WORDS)
        self.assertEqual(int(identity["song_count"]), EXPECTED_SONGS)
        self.assertEqual(int(identity["table_count"]), EXPECTED_BUSINESS_TABLES)

        self.assertEqual(int(identity["local_edits"]), 0)
        self.assertIs(identity["local_modified"], False)
        self.assertEqual(int(identity["backup_count"]), 0)
        self.assertIsNone(identity["latest_backup"])

        listing = self.call("gov_backups")
        self.assertTrue(listing["ok"], listing.get("message"))
        self.assertEqual(int(listing["count"]), 0)
        self.assertEqual(listing["backups"], [])
        self.assert_asset_unmodified()

    # --------------------------------------------------- check 2
    def test_local_edit_reflected_in_identity(self):
        before = self.call("gov_identity")
        self.assertEqual(int(before["local_edits"]), 0)

        entry = self.real_word_entry()
        original_explanation = entry["explanation"]
        edited_explanation = original_explanation + "（P4 治理测试）"
        self.edit_word(entry, edited_explanation)

        identity = self.call("gov_identity")
        self.assertTrue(identity["ok"], identity.get("message"))
        self.assertGreaterEqual(
            int(identity["local_edits"]), 1, "a curated edit must append a local-edit row"
        )
        self.assertIs(identity["local_modified"], True)
        self.assertNotEqual(
            str(identity["sha256"]), ASSET_SHA256, "the edited database must have a new sha256"
        )
        self.assertEqual(str(identity["sha256"]), sha256_file(self.db_path))

        updated_entry = self.real_word_entry()
        self.assertEqual(updated_entry["explanation"], edited_explanation)
        self.assert_asset_unmodified()

    # --------------------------------------------------- check 3
    def test_backup_create_updates_identity(self):
        before = self.call("gov_identity")
        backups_before = int(before["backup_count"])
        sha_before = str(before["sha256"])

        created = self.call("gov_backup_create", reason="p4test")
        self.assertTrue(created["ok"], created.get("message"))
        backup_path = Path(str(created["path"]))
        self.assertTrue(backup_path.is_file(), str(backup_path))
        self.assertTrue(Path(str(backup_path) + ".json").is_file(), "sidecar .json must exist")

        identity = self.call("gov_identity")
        self.assertEqual(int(identity["backup_count"]), backups_before + 1)
        self.assertEqual(self.backup_count(), backups_before + 1)

        latest = identity["latest_backup"]
        self.assertIsInstance(latest, dict)
        for key in (
            "path",
            "name",
            "created_at",
            "reason",
            "db_version",
            "sha1",
            "size",
        ):
            self.assertIn(key, latest, "latest_backup must expose %r" % key)
        self.assertEqual(Path(str(latest["path"])).resolve(), backup_path.resolve())
        self.assertEqual(latest["reason"], "p4test")
        self.assertEqual(int(latest["db_version"]), EXPECTED_DB_VERSION)
        self.assertEqual(len(str(latest["sha1"])), 40)
        self.assertEqual(
            str(latest["sha1"]), _sha1_file(latest["path"]), "sidecar sha1 must describe the file"
        )
        self.assertGreater(int(latest["size"]), 0)
        datetime.fromisoformat(str(latest["created_at"]))

        listing = self.call("gov_backups")
        self.assertTrue(listing["ok"], listing.get("message"))
        self.assertEqual(int(listing["count"]), backups_before + 1)
        self.assertEqual(len(listing["backups"]), backups_before + 1)
        self.assertEqual(
            Path(str(listing["backups"][0]["path"])).resolve(), backup_path.resolve(),
            "the newest backup must sort first",
        )

        # Snapshotting is read-only for the live database.
        self.assertEqual(str(identity["sha256"]), sha_before)
        self.assert_asset_unmodified()

    # --------------------------------------------------- check 4
    def test_backup_restore_roundtrip(self):
        entry = self.real_word_entry()
        original_explanation = entry["explanation"]

        created = self.call("gov_backup_create", reason="p4restore_base")
        self.assertTrue(created["ok"], created.get("message"))
        backup_path = Path(str(created["path"]))

        edited_explanation = original_explanation + "（P4 回退测试）"
        self.edit_word(entry, edited_explanation)
        identity_edited = self.call("gov_identity")
        self.assertGreaterEqual(int(identity_edited["local_edits"]), 1)
        self.assertIs(identity_edited["local_modified"], True)
        self.assertNotEqual(str(identity_edited["sha256"]), ASSET_SHA256)

        restored = self.call("gov_backup_restore", path=str(backup_path))
        self.assertTrue(restored["ok"], restored.get("message"))
        self.assertTrue(str(restored.get("message")).strip())
        self.assertIn("恢复", str(restored.get("message")))
        self.assertIsInstance(restored.get("restored"), dict)
        self.assertIn("sha1", restored["restored"])

        safety_path = str(restored.get("safety_backup") or "")
        self.assertTrue(safety_path, "restore must create a safety backup of the current database")
        self.assertTrue(Path(safety_path).is_file(), safety_path)
        self.assertNotEqual(Path(safety_path).resolve(), backup_path.resolve())

        identity = self.call("gov_identity")
        self.assertTrue(identity["ok"], identity.get("message"))
        self.assertEqual(int(identity["db_version"]), EXPECTED_DB_VERSION, "version must not be lowered")
        self.assertGreaterEqual(
            int(identity["backup_count"]), 2, "base + safety recovery points must be listed"
        )
        listed_paths = {
            Path(str(item["path"])).resolve()
            for item in self.call("gov_backups")["backups"]
        }
        self.assertIn(Path(safety_path).resolve(), listed_paths)
        self.assertEqual(
            int(identity["local_edits"]), 0, "local_edits must go back to the snapshot value"
        )
        self.assertIs(identity["local_modified"], False)

        reverted = self.real_word_entry()
        self.assertEqual(reverted["explanation"], original_explanation, "restore must revert the edit")

        # The services must be usable after the atomic replace + reconnect.
        self.assertTrue(self.call("dictionary_search", query="world", exact=False)["ok"])
        self.assertTrue(self.call("data_form", table="phrase")["ok"])
        self.assertEqual(
            self.call("data_page", table="dictionary_headwords", limit=5)["total"], EXPECTED_WORDS
        )
        self.assert_asset_unmodified()

    # --------------------------------------------------- check 5 (leak regression)
    def test_identity_reads_do_not_block_restore(self):
        """Pin commit 335e62a: reading gov_identity must not leak DB handles/locks.

        Before that fix the bridge used ``with sqlite3.connect(...)`` (commits but never
        closes).  After enough identity reads the leaked lock made the restore's atomic
        file replace fail on Windows ("替换数据库文件失败。", WinError 5).
        """
        entry = self.real_word_entry()
        original_explanation = entry["explanation"]

        created = self.call("gov_backup_create", reason="p4leak")
        self.assertTrue(created["ok"], created.get("message"))
        backup_path = Path(str(created["path"]))

        self.edit_word(entry, original_explanation + "（P4 泄漏回归）")
        for index in range(20):
            identity = self.call("gov_identity")
            self.assertTrue(
                identity.get("ok"), "gov_identity call #%d failed: %r" % (index + 1, identity)
            )
            self.assertEqual(len(str(identity.get("sha256") or "")), 64)

        restored = self.call("gov_backup_restore", path=str(backup_path))
        self.assertTrue(
            restored.get("ok"),
            "restore after 20 gov_identity reads must succeed — leaked sqlite handles/"
            "locks from identity reads are the 335e62a regression: %r" % (restored,),
        )
        safety_path = str(restored.get("safety_backup") or "")
        self.assertTrue(Path(safety_path).is_file(), safety_path)

        identity_after = self.call("gov_identity")
        self.assertTrue(identity_after["ok"], identity_after.get("message"))
        self.assertEqual(int(identity_after["db_version"]), EXPECTED_DB_VERSION)

        reverted = self.real_word_entry()
        self.assertEqual(reverted["explanation"], original_explanation)
        self.assertTrue(self.call("dictionary_search", query="Finz", exact=False)["ok"])
        self.assert_asset_unmodified()


def _sha1_file(path) -> str:
    return hashlib.sha1(Path(path).read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Check 6 — shipped asset guard
# ---------------------------------------------------------------------------
class ShippedAssetTests(unittest.TestCase):
    def test_shipped_database_asset_is_unmodified(self):
        self.assertEqual(
            hashlib.sha256(ASSET_DB.read_bytes()).hexdigest(),
            ASSET_SHA256,
            "tests must never open the shipped database for writing",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
