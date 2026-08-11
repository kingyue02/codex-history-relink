import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from codex_history_relink.backup import rotate_backups
from codex_history_relink.environment import (
    discover_database,
    resolve_paths,
)
from codex_history_relink.process_lock import single_instance
from codex_history_relink.relink import inspect, relink

THREAD_ID = "11111111-1111-1111-1111-111111111111"


def make_db(path: Path, provider: str = "old-provider"):
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)

    try:
        conn.execute(
            """
            CREATE TABLE threads (
                id TEXT PRIMARY KEY,
                model_provider TEXT,
                model TEXT,
                title TEXT,
                updated_at INTEGER,
                archived INTEGER
            )
            """
        )

        conn.execute(
            "INSERT INTO threads VALUES (?, ?, ?, ?, ?, ?)",
            (
                THREAD_ID,
                provider,
                "gpt-old",
                "Example",
                100,
                0,
            ),
        )

        conn.commit()

    finally:
        conn.close()


class CoreTests(unittest.TestCase):
    def make_home(
        self,
        provider_line: str | None,
        db_in_sqlite: bool = False,
    ):
        tmp = tempfile.TemporaryDirectory()
        home = Path(tmp.name)

        config_text = 'service_tier = "default"\n'
        if provider_line:
            config_text = provider_line + "\n" + config_text

        (home / "config.toml").write_text(
            config_text,
            encoding="utf-8",
        )

        (home / "sessions").mkdir()

        db = (
            home / "sqlite" / "state_5.sqlite"
            if db_in_sqlite
            else home / "state_5.sqlite"
        )

        make_db(db)

        session = (
            home
            / "sessions"
            / f"rollout-test-{THREAD_ID}.jsonl"
        )

        session.write_text(
            json.dumps(
                {
                    "type": "session_meta",
                    "payload": {
                        "id": THREAD_ID,
                        "model_provider": "old-provider",
                        "model": "gpt-old",
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )

        return tmp, home

    def test_explicit_provider_relink_preserves_model(self):
        tmp, home = self.make_home(
            'model_provider = "new-provider"'
        )

        try:
            with mock.patch.dict(
                os.environ,
                {"CODEX_HOME": str(home)},
                clear=False,
            ):
                paths = resolve_paths()
                before = inspect(paths)

                self.assertEqual(
                    before["current_provider"],
                    "new-provider",
                )
                self.assertEqual(
                    before["mismatched_threads"],
                    1,
                )

                result = relink(paths)

                self.assertTrue(result["changed"])
                self.assertTrue(result["verified"])

                conn = sqlite3.connect(paths.database)

                try:
                    provider, model = conn.execute(
                        """
                        SELECT model_provider, model
                        FROM threads
                        WHERE id = ?
                        """,
                        (THREAD_ID,),
                    ).fetchone()

                finally:
                    conn.close()

                self.assertEqual(
                    provider,
                    "new-provider",
                )
                self.assertEqual(
                    model,
                    "gpt-old",
                )

        finally:
            tmp.cleanup()

    def test_missing_provider_uses_openai(self):
        tmp, home = self.make_home(None)

        try:
            with mock.patch.dict(
                os.environ,
                {"CODEX_HOME": str(home)},
                clear=False,
            ):
                paths = resolve_paths()
                before = inspect(paths)

                self.assertEqual(
                    before["current_provider"],
                    "openai",
                )
                self.assertFalse(
                    before["provider_explicit"],
                )

        finally:
            tmp.cleanup()

    def test_no_mismatch_creates_no_backup(self):
        tmp, home = self.make_home(
            'model_provider = "old-provider"'
        )

        try:
            with mock.patch.dict(
                os.environ,
                {"CODEX_HOME": str(home)},
                clear=False,
            ):
                paths = resolve_paths()
                result = relink(paths)

                self.assertFalse(result["changed"])
                self.assertFalse(paths.backups_dir.exists())

        finally:
            tmp.cleanup()

    def test_discovers_sqlite_subdirectory_database(self):
        tmp, home = self.make_home(
            'model_provider = "new-provider"',
            db_in_sqlite=True,
        )

        try:
            selected = discover_database(home)
            self.assertEqual(
                selected,
                home / "sqlite" / "state_5.sqlite",
            )

        finally:
            tmp.cleanup()

    def test_wal_activity_selects_active_database(self):
        with tempfile.TemporaryDirectory() as tmp_name:
            home = Path(tmp_name)
            root_db = home / "state_5.sqlite"
            nested_db = home / "sqlite" / "state_5.sqlite"

            make_db(root_db)
            make_db(nested_db)

            os.utime(
                root_db,
                (10, 10),
            )
            os.utime(
                nested_db,
                (20, 20),
            )

            wal = Path(f"{root_db}-wal")
            wal.write_bytes(b"fake-wal-activity")
            os.utime(
                wal,
                (30, 30),
            )

            selected = discover_database(home)

            self.assertEqual(
                selected,
                root_db,
            )

    def test_rotation_keeps_five_across_state_versions(self):
        tmp, home = self.make_home(
            'model_provider = "new-provider"'
        )

        try:
            with mock.patch.dict(
                os.environ,
                {"CODEX_HOME": str(home)},
                clear=False,
            ):
                paths = resolve_paths()
                paths.backups_dir.mkdir(parents=True)

                for i in range(7):
                    db_name = (
                        "state_4.sqlite"
                        if i % 2 == 0
                        else "state_5.sqlite"
                    )

                    primary = paths.backups_dir / (
                        f"{db_name}.pre-relink.20260811-00000{i}.bak"
                    )

                    primary.write_bytes(b"x")
                    os.utime(
                        primary,
                        (i + 1, i + 1),
                    )

                summary = rotate_backups(
                    paths,
                    keep=5,
                )

                remaining = list(
                    paths.backups_dir.glob(
                        "state_*.sqlite.pre-relink.*.bak"
                    )
                )

                self.assertEqual(
                    len(remaining),
                    5,
                )
                self.assertEqual(
                    summary["remaining_backup_sets"],
                    5,
                )

        finally:
            tmp.cleanup()

    def test_process_lock_blocks_second_instance(self):
        with tempfile.TemporaryDirectory() as tmp_name:
            lock_path = Path(tmp_name) / ".lock"

            with single_instance(lock_path):
                with self.assertRaises(RuntimeError):
                    with single_instance(lock_path):
                        pass

    def test_repair_failure_rolls_database_back(self):
        tmp, home = self.make_home(
            'model_provider = "new-provider"'
        )

        try:
            with mock.patch.dict(
                os.environ,
                {"CODEX_HOME": str(home)},
                clear=False,
            ):
                paths = resolve_paths()

                with mock.patch(
                    "codex_history_relink.relink.rewrite_provider",
                    side_effect=RuntimeError("simulated session write failure"),
                ):
                    with self.assertRaises(RuntimeError):
                        relink(paths)

                conn = sqlite3.connect(paths.database)

                try:
                    provider, model = conn.execute(
                        """
                        SELECT model_provider, model
                        FROM threads
                        WHERE id = ?
                        """,
                        (THREAD_ID,),
                    ).fetchone()

                finally:
                    conn.close()

                self.assertEqual(
                    provider,
                    "old-provider",
                )
                self.assertEqual(
                    model,
                    "gpt-old",
                )

        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
