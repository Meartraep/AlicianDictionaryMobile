# -*- coding: utf-8 -*-
"""P0 acceptance tests for recovery points + atomic database replacement.

Contract: ``.luna-review/p0-interface.md`` ("恢复点", ``validate_database_file``,
``atomic_replace_file``) and acceptance list items 10-11.

Every test copies the *shipped* database ``app/src/main/assets/translated.db``
into a fresh ``tempfile.mkdtemp()`` and works on ``DataCore(<copy>,
backups_dir=<tmp>/backups)`` or plain files inside that temp directory.  The
shipped asset is never opened for writing.

Run::

    cd app/src/test/python
    $env:PYTHONPATH = '<repo>/app/src/main/python'
    python -m unittest test_backup_restore -v
"""

from __future__ import annotations

import hashlib
import json
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

from webui_backend.data_core import (  # noqa: E402
    DataCore,
    DataError,
    atomic_replace_file,
    validate_database_file,
)


ASSET_SHA256 = hashlib.sha256(ASSET_DB.read_bytes()).hexdigest()


def sha1_file(path) -> str:
    return hashlib.sha1(Path(path).read_bytes()).hexdigest()


def sha256_file(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sql_on(path, statement: str, args=()):
    connection = sqlite3.connect(str(path))
    try:
        return [tuple(row) for row in connection.execute(statement, args).fetchall()]
    finally:
        connection.close()


class RealDatabaseTestCase(unittest.TestCase):
    """One private copy of the shipped database + one connected ``DataCore`` per test."""

    def setUp(self) -> None:
        self.tmpdir = Path(tempfile.mkdtemp(prefix="p0-backup-"))
        self.addCleanup(self._cleanup_tmpdir)
        self.db_path = str(self.tmpdir / "translated.db")
        self.backups_dir = str(self.tmpdir / "backups")
        self._assert_copy()
        self.core = DataCore(self.db_path, backups_dir=self.backups_dir)
        self.assertTrue(self.core.connect(), "DataCore.connect() failed on a real DB copy")

    def _cleanup_tmpdir(self) -> None:
        import shutil

        try:
            self.core.close()
        except Exception:  # pragma: no cover
            pass
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _assert_copy(self) -> None:
        import shutil

        shutil.copyfile(ASSET_DB, self.db_path)
        self.assertEqual(
            sha256_file(self.db_path),
            ASSET_SHA256,
            "the database under test must be a byte-for-byte copy of the shipped asset",
        )

    def copy_asset(self, name: str) -> Path:
        import shutil

        target = self.tmpdir / name
        shutil.copyfile(ASSET_DB, target)
        return target

    def assert_asset_unmodified(self) -> None:
        self.assertEqual(
            hashlib.sha256(ASSET_DB.read_bytes()).hexdigest(),
            ASSET_SHA256,
            "the shipped database asset must never be modified by the tests",
        )

    def temp_files(self, pattern: str = "*.tmp-*") -> list:
        return [path for path in self.tmpdir.iterdir() if path.match(pattern)]


# ---------------------------------------------------------------------------
# Contract "恢复点": backup_create / backup_list / backup_prune
# ---------------------------------------------------------------------------
class BackupCreateTests(RealDatabaseTestCase):
    def test_backup_create_returns_sidecar_identity(self):
        backup = self.core.backup_create("p0test")
        self.assertTrue(backup["ok"])
        self.assertEqual(backup["reason"], "p0test")
        self.assertEqual(backup["source"], "installed")
        self.assertEqual(backup["db_version"], 2)

        path = Path(backup["path"])
        self.assertTrue(path.is_file(), "backup file must exist")
        self.assertRegex(path.name, r"^translated_\d{8}_\d{6}_p0test\.db$")
        self.assertEqual(backup["size"], path.stat().st_size)
        self.assertEqual(backup["sha1"], sha1_file(path))
        self.assertEqual(len(backup["sha1"]), 40)

        sidecar_path = Path(str(path) + ".json")
        self.assertTrue(sidecar_path.is_file(), "backup sidecar .json must exist next to the .db")
        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
        for key in ("db_version", "sha1", "size", "created_at", "reason", "source"):
            self.assertIn(key, backup, "backup_create result must carry %r" % key)
            self.assertIn(key, sidecar, "sidecar must carry %r" % key)
        self.assertEqual(sidecar["sha1"], backup["sha1"])
        self.assertEqual(sidecar["size"], backup["size"])
        self.assertEqual(sidecar["db_version"], 2)
        self.assertEqual(sidecar["reason"], "p0test")
        self.assertEqual(sidecar["source"], "installed")
        datetime.fromisoformat(sidecar["created_at"])  # must be an ISO timestamp

    def test_backup_is_a_complete_valid_snapshot(self):
        backup = self.core.backup_create("p0snapshot")
        validated = validate_database_file(backup["path"])
        self.assertTrue(validated["ok"])
        self.assertEqual(validated["db_version"], 2)
        self.assertEqual(validated["sha1"], backup["sha1"])
        self.assertEqual(
            sql_on(backup["path"], "SELECT COUNT(*) FROM dictionary")[0][0], 1515
        )
        self.assertEqual(
            sql_on(backup["path"], "SELECT COUNT(*) FROM dictionary_headwords")[0][0], 1339
        )
        self.assertEqual(sql_on(backup["path"], "SELECT COUNT(*) FROM songs")[0][0], 53)
        self.assertEqual(
            sql_on(backup["path"], "SELECT COUNT(*) FROM sentence_alignments")[0][0], 1286
        )

    def test_backup_captures_committed_edits(self):
        created = self.core.create(
            "phrase", {"PHRASE": "P0 backup phrase", "explanation": "in the snapshot"}
        )
        self.assertTrue(created["ok"])
        self.core.update("phrase", 1, {"explanation": "P0 edited explanation"})
        backup = self.core.backup_create("p0edits")

        self.assertEqual(
            sql_on(backup["path"], "SELECT explanation FROM phrase WHERE id = 1")[0][0],
            "P0 edited explanation",
        )
        self.assertEqual(
            sql_on(backup["path"], "SELECT COUNT(*) FROM phrase WHERE PHRASE = ?",
                   ("P0 backup phrase",))[0][0],
            1,
        )

    def test_default_backups_dir_is_next_to_the_database(self):
        other_dir = self.tmpdir / "other"
        other_dir.mkdir()
        other_db = other_dir / "translated.db"
        other_db.write_bytes(ASSET_DB.read_bytes())
        other_core = DataCore(str(other_db))  # no explicit backups_dir
        self.addCleanup(other_core.close)
        self.assertTrue(other_core.connect())
        backup = other_core.backup_create("p0default")
        self.assertEqual(Path(backup["path"]).parent.resolve(), (other_dir / "backups").resolve())


class BackupListTests(RealDatabaseTestCase):
    def test_backup_list_returns_newest_first(self):
        reasons = ["p0list_a", "p0list_b", "p0list_c"]
        for reason in reasons:
            self.core.backup_create(reason)
        entries = self.core.backup_list()
        self.assertEqual(len(entries), len(reasons))
        self.assertEqual({entry["reason"] for entry in entries}, set(reasons))
        for entry in entries:
            self.assertIn("path", entry)
            self.assertIn("sha1", entry)
            self.assertIn("created_at", entry)
            self.assertEqual(entry["sha1"], sha1_file(entry["path"]))
            self.assertTrue(int(entry["db_version"]) >= 1)
            datetime.fromisoformat(entry["created_at"])
        created = [entry["created_at"] for entry in entries]
        self.assertEqual(created, sorted(created, reverse=True), "newest backup must come first")

    def test_corrupt_or_sidecarless_files_are_skipped(self):
        valid = self.core.backup_create("p0valid")
        directory = Path(self.backups_dir)

        # 1) .db without a sidecar
        (directory / "translated_19990101_000000_orphan.db").write_bytes(b"not a database")
        # 2) sidecar that is not valid JSON
        bad_json = directory / "translated_19990101_000000_badjson.db"
        bad_json.write_bytes(b"not a database")
        Path(str(bad_json) + ".json").write_text("{not json", encoding="utf-8")
        # 3) sidecar whose sha1 does not match the file
        bad_sha = directory / "translated_19990101_000000_badsha.db"
        bad_sha.write_bytes(b"different bytes")
        Path(str(bad_sha) + ".json").write_text(
            json.dumps(
                {
                    "db_version": 1,
                    "sha1": "0" * 40,
                    "size": bad_sha.stat().st_size,
                    "created_at": "1999-01-01T00:00:00+00:00",
                    "reason": "badsha",
                    "source": "installed",
                }
            ),
            encoding="utf-8",
        )

        entries = self.core.backup_list()
        self.assertEqual(len(entries), 1, "corrupt/foreign files must be skipped")
        self.assertEqual(Path(entries[0]["path"]).resolve(), Path(valid["path"]).resolve())


class BackupPruneTests(RealDatabaseTestCase):
    def test_prune_keeps_the_requested_number_and_removes_sidecars(self):
        backups = [self.core.backup_create("p0prune_%d" % index) for index in range(4)]
        entries = self.core.backup_list()
        self.assertEqual(len(entries), 4)

        removed = self.core.backup_prune(keep=2)
        self.assertEqual(removed, 2)

        remaining = self.core.backup_list()
        self.assertEqual(len(remaining), 2)
        kept_paths = {Path(entry["path"]).resolve() for entry in remaining}
        for entry in entries[:2]:
            self.assertIn(Path(entry["path"]).resolve(), kept_paths)
        for entry in entries[2:]:
            self.assertFalse(Path(entry["path"]).exists(), "pruned backup must be deleted")
            self.assertFalse(
                Path(str(entry["path"]) + ".json").exists(), "pruned sidecar must be deleted"
            )
        self.assertEqual(len([path for path in Path(self.backups_dir).glob("translated_*.db")]), 2)

    def test_prune_with_fewer_backups_deletes_nothing(self):
        self.core.backup_create("p0few")
        self.assertEqual(self.core.backup_prune(keep=10), 0)
        self.assertEqual(len(self.core.backup_list()), 1)


# ---------------------------------------------------------------------------
# Contract "validate_database_file"
# ---------------------------------------------------------------------------
class ValidateDatabaseFileTests(RealDatabaseTestCase):
    def test_accepts_the_shipped_database(self):
        copy = self.copy_asset("valid.db")
        result = validate_database_file(copy)
        self.assertTrue(result["ok"])
        self.assertEqual(result["db_version"], 2)
        self.assertEqual(result["size"], copy.stat().st_size)
        self.assertEqual(result["sha1"], sha1_file(copy))

    def test_rejects_missing_file(self):
        with self.assertRaises(DataError) as caught:
            validate_database_file(self.tmpdir / "missing.db")
        self.assertTrue(str(caught.exception).strip())

    def test_rejects_non_sqlite_file(self):
        text = self.tmpdir / "not-a-db.txt"
        text.write_text("this is not a database", encoding="utf-8")
        with self.assertRaises(DataError):
            validate_database_file(text)

    def test_rejects_empty_file(self):
        empty = self.tmpdir / "empty.db"
        empty.write_bytes(b"")
        with self.assertRaises(DataError):
            validate_database_file(empty)

    def test_rejects_sqlite_database_without_required_tables(self):
        database = self.tmpdir / "no-schema.db"
        connection = sqlite3.connect(str(database))
        try:
            connection.execute("CREATE TABLE unrelated (value TEXT)")
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(DataError):
            validate_database_file(database)

    def test_rejects_truncated_database(self):
        data = ASSET_DB.read_bytes()
        truncated = self.tmpdir / "truncated.db"
        truncated.write_bytes(data[: len(data) // 3])
        with self.assertRaises(DataError):
            validate_database_file(truncated)

    def test_rejects_corrupted_header(self):
        corrupted = self.tmpdir / "corrupted.db"
        corrupted.write_bytes(b"SQLite format 3\x00" + b"\x00" * 2048)
        with self.assertRaises(DataError):
            validate_database_file(corrupted)


# ---------------------------------------------------------------------------
# Contract "atomic_replace_file"
# ---------------------------------------------------------------------------
class AtomicReplaceTests(RealDatabaseTestCase):
    def test_replaces_target_atomically(self):
        source = self.copy_asset("source.db")
        target = self.copy_asset("target.db")
        connection = sqlite3.connect(str(target))
        try:
            connection.execute("UPDATE phrase SET explanation = 'changed before replace' WHERE id = 1")
            connection.commit()
        finally:
            connection.close()
        self.assertNotEqual(sha1_file(source), sha1_file(target))

        atomic_replace_file(source, target)

        self.assertEqual(sha1_file(target), sha1_file(source))
        self.assertEqual(
            sql_on(target, "SELECT explanation FROM phrase WHERE id = 1")[0][0], "最终"
        )
        leftovers = [path.name for path in self.temp_files()]
        self.assertEqual(leftovers, [], "atomic replace must not leave temp files behind")

    def test_missing_source_raises_and_leaves_target_untouched(self):
        target = self.copy_asset("untouched.db")
        before = sha1_file(target)
        with self.assertRaises(DataError) as caught:
            atomic_replace_file(self.tmpdir / "missing-source.db", target)
        self.assertTrue(str(caught.exception).strip())
        self.assertEqual(sha1_file(target), before)
        self.assertEqual(self.temp_files(), [])

    def test_source_directory_is_rejected(self):
        target = self.copy_asset("dir-target.db")
        before = sha1_file(target)
        with self.assertRaises(DataError):
            atomic_replace_file(self.tmpdir, target)
        self.assertEqual(sha1_file(target), before)
        self.assertEqual(self.temp_files(), [])

    def test_failure_midway_cleans_the_temp_file(self):
        source = self.copy_asset("midway-source.db")
        target_directory = self.tmpdir / "target-is-a-directory"
        target_directory.mkdir()
        with self.assertRaises(DataError):
            atomic_replace_file(source, target_directory)
        leftovers = [
            path.name
            for path in self.tmpdir.iterdir()
            if path.name.startswith("target-is-a-directory.tmp-")
        ]
        self.assertEqual(leftovers, [], "a failed replace must remove its temp file")


# ---------------------------------------------------------------------------
# Acceptance 10 — create → modify → validate → atomic replace → reconnect
# ---------------------------------------------------------------------------
class RestoreFlowTests(RealDatabaseTestCase):
    def test_recovery_point_restore_roundtrip(self):
        original_row = self.core.row("phrase", 1)
        self.assertIsNotNone(original_row)
        original_explanation = original_row["explanation"]

        backup = self.core.backup_create("p0restore")
        backup_sha = backup["sha1"]
        self.assertEqual(backup_sha, sha1_file(backup["path"]))
        self.assertEqual(len(self.core.backup_list()), 1)

        # Modify the live database after the snapshot was taken.
        self.core.update("phrase", 1, {"explanation": "P0 restored-away edit"})
        created = self.core.create(
            "phrase", {"PHRASE": "P0RESTORE_SENTINEL", "explanation": "created after snapshot"}
        )
        self.assertTrue(created["ok"])
        self.assertNotEqual(sha1_file(self.db_path), backup_sha)
        self.core.close()

        # Restore = validate the recovery point, then atomically replace the live file.
        validated = validate_database_file(backup["path"])
        self.assertTrue(validated["ok"])
        self.assertEqual(validated["sha1"], backup_sha)
        atomic_replace_file(backup["path"], self.db_path)
        self.assertEqual(
            sha1_file(self.db_path), backup_sha, "restored file must be the recovery point"
        )
        validate_database_file(self.db_path)  # restored file is installable again

        self.assertTrue(self.core.connect(), "DataCore must reconnect after the restore")
        restored_row = self.core.row("phrase", 1)
        self.assertIsNotNone(restored_row)
        self.assertEqual(restored_row["explanation"], original_explanation)
        self.assertEqual(
            self.core.page("phrase", keyword="P0RESTORE_SENTINEL")["total"],
            0,
            "content created after the snapshot must be gone",
        )

    def test_restore_refuses_invalid_backup_file(self):
        corrupt = self.tmpdir / "corrupt-backup.db"
        corrupt.write_bytes(b"this is not a database")
        before = sha1_file(self.db_path)
        with self.assertRaises(DataError):
            validate_database_file(corrupt)  # the restore path validates before replacing
        self.assertEqual(sha1_file(self.db_path), before)


# ---------------------------------------------------------------------------
# Acceptance 11 — the shipped asset is never written
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
