import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import codex_history_relink as relink


def compact(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


class RelinkTests(unittest.TestCase):
    def make_home(self):
        temp = tempfile.TemporaryDirectory()
        home = Path(temp.name) / ".codex"
        home.mkdir(parents=True)
        (home / "sessions").mkdir()
        return temp, home

    def make_db(self, path: Path):
        conn = sqlite3.connect(path)
        conn.execute(
            """
            CREATE TABLE threads (
                id TEXT PRIMARY KEY,
                model_provider TEXT,
                model TEXT
            )
            """
        )
        conn.executemany(
            "INSERT INTO threads(id, model_provider, model) VALUES (?, ?, ?)",
            [
                ("1", "openai", "gpt-old"),
                ("2", "custom", "gpt-old"),
                ("3", "OpenAI", "gpt-current"),
            ],
        )
        conn.commit()
        conn.close()

    def test_read_current_provider_preserves_case(self):
        temp, home = self.make_home()
        try:
            config = home / "config.toml"
            config.write_text(
                'model_provider = "OpenAI"\n'
                'model = "gpt-5.5"\n\n'
                '[model_providers.OpenAI]\n'
                'name = "OpenAI"\n',
                encoding="utf-8",
            )
            self.assertEqual(relink.read_current_provider(config), "OpenAI")
        finally:
            temp.cleanup()

    def test_database_only_changes_provider(self):
        temp, home = self.make_home()
        try:
            db = home / "state_5.sqlite"
            self.make_db(db)

            updated = relink.sync_database_provider(db, "OpenAI")
            self.assertEqual(updated, 2)

            conn = sqlite3.connect(db)
            rows = conn.execute(
                "SELECT model_provider, model FROM threads ORDER BY id"
            ).fetchall()
            conn.close()

            self.assertEqual(
                rows,
                [
                    ("OpenAI", "gpt-old"),
                    ("OpenAI", "gpt-old"),
                    ("OpenAI", "gpt-current"),
                ],
            )
        finally:
            temp.cleanup()

    def test_session_sync_changes_exact_two_verified_paths(self):
        temp, home = self.make_home()
        try:
            session = home / "sessions" / "rollout-test.jsonl"

            lines = [
                {
                    "type": "session_meta",
                    "payload": {
                        "id": "thread-1",
                        "model_provider": "openai",
                        "model": "gpt-old",
                    },
                },
                {
                    "type": "event_msg",
                    "payload": {
                        "type": "thread_settings_applied",
                        "thread_settings": {
                            "model_provider_id": "custom",
                            "model": "gpt-old",
                        },
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "model_provider": "do-not-touch",
                        "text": "openai custom OpenAI",
                    },
                },
            ]

            session.write_text(
                "\n".join(compact(x) for x in lines) + "\n",
                encoding="utf-8",
            )

            meta_changed, settings_changed = relink.sync_session_file(
                session, "OpenAI"
            )

            self.assertEqual(meta_changed, 1)
            self.assertEqual(settings_changed, 1)

            output = [
                json.loads(line)
                for line in session.read_text(encoding="utf-8").splitlines()
            ]

            self.assertEqual(output[0]["payload"]["model_provider"], "OpenAI")
            self.assertEqual(
                output[1]["payload"]["thread_settings"]["model_provider_id"],
                "OpenAI",
            )
            self.assertEqual(
                output[2]["payload"]["model_provider"],
                "do-not-touch",
            )
            self.assertEqual(output[0]["payload"]["model"], "gpt-old")
        finally:
            temp.cleanup()

    def test_scan_detects_real_thread_settings_structure(self):
        temp, home = self.make_home()
        try:
            session = home / "sessions" / "rollout-test.jsonl"

            session.write_text(
                compact(
                    {
                        "type": "event_msg",
                        "payload": {
                            "type": "thread_settings_applied",
                            "thread_settings": {
                                "model_provider_id": "openai"
                            },
                        },
                    }
                ) + "\n",
                encoding="utf-8",
            )

            scan = relink.scan_sessions(home / "sessions", "OpenAI")
            self.assertEqual(scan.thread_settings_mismatches, 1)
            self.assertEqual(scan.thread_settings_counts["openai"], 1)
            self.assertEqual(len(scan.files_needing_change), 1)
        finally:
            temp.cleanup()

    def test_integrated_three_place_relink_and_verify(self):
        temp, home = self.make_home()
        try:
            (home / "config.toml").write_text(
                'model_provider = "OpenAI"\n',
                encoding="utf-8",
            )

            db = home / "state_5.sqlite"
            self.make_db(db)

            session = home / "sessions" / "rollout-test.jsonl"
            session.write_text(
                "\n".join(
                    [
                        compact(
                            {
                                "type": "session_meta",
                                "payload": {
                                    "id": "thread-1",
                                    "model_provider": "openai",
                                },
                            }
                        ),
                        compact(
                            {
                                "type": "event_msg",
                                "payload": {
                                    "type": "thread_settings_applied",
                                    "thread_settings": {
                                        "model_provider_id": "custom"
                                    },
                                },
                            }
                        ),
                    ]
                ) + "\n",
                encoding="utf-8",
            )

            relink.sync_database_provider(db, "OpenAI")

            scan = relink.scan_sessions(home / "sessions", "OpenAI")
            relink.sync_sessions(
                home / "sessions",
                "OpenAI",
                scan.files_needing_change,
            )

            paths = relink.CodexPaths(
                home=home,
                config=home / "config.toml",
                database=db,
                sessions=home / "sessions",
                backup_root=home / "history_relink_backups",
            )

            ok, post_scan, db_mismatches = relink.verify(paths, "OpenAI")
            self.assertTrue(ok)
            self.assertEqual(db_mismatches, 0)
            self.assertEqual(post_scan.session_meta_mismatches, 0)
            self.assertEqual(post_scan.thread_settings_mismatches, 0)
        finally:
            temp.cleanup()

    def test_backup_contains_database_and_full_modified_rollout(self):
        temp, home = self.make_home()
        try:
            (home / "config.toml").write_text(
                'model_provider = "OpenAI"\n',
                encoding="utf-8",
            )
            db = home / "state_5.sqlite"
            self.make_db(db)

            nested = home / "sessions" / "2026" / "08" / "21"
            nested.mkdir(parents=True)
            session = nested / "rollout-test.jsonl"

            original = (
                '{"type":"session_meta","payload":{"model_provider":"openai"}}\n'
                '{"type":"event_msg","payload":{"type":"thread_settings_applied",'
                '"thread_settings":{"model_provider_id":"openai"}}}\n'
            )
            session.write_text(original, encoding="utf-8")

            paths = relink.CodexPaths(
                home=home,
                config=home / "config.toml",
                database=db,
                sessions=home / "sessions",
                backup_root=home / "history_relink_backups",
            )

            backup = relink.create_backup(paths, {session}, "OpenAI")

            self.assertTrue((backup / "state_5.sqlite.bak").exists())
            backed_session = (
                backup
                / "sessions"
                / "2026"
                / "08"
                / "21"
                / "rollout-test.jsonl"
            )
            self.assertTrue(backed_session.exists())
            self.assertEqual(
                backed_session.read_text(encoding="utf-8"),
                original,
            )
        finally:
            temp.cleanup()


if __name__ == "__main__":
    unittest.main()
