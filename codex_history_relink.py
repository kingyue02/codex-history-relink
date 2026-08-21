from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import sys
import time
from collections import Counter
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

VERSION = "0.4.1-rc1"
MAX_BACKUPS = 3


@dataclass(frozen=True)
class CodexPaths:
    """Codex 本地历史相关路径。"""
    home: Path
    config: Path
    database: Path
    sessions: Path
    backup_root: Path


def database_activity_ns(path: Path) -> int:
    """同时考虑 SQLite 本体和 WAL 的最近活动时间。"""
    latest = 0
    for candidate in (path, Path(str(path) + "-wal")):
        try:
            latest = max(latest, candidate.stat().st_mtime_ns)
        except FileNotFoundError:
            pass
    return latest


def resolve_paths(codex_home: str | None = None) -> CodexPaths:
    """自动定位 Codex Home 和实际在使用的 state_5.sqlite。"""
    home = Path(codex_home).expanduser() if codex_home else Path.home() / ".codex"
    candidates = [
        home / "state_5.sqlite",
        home / "sqlite" / "state_5.sqlite",
    ]
    existing = [p for p in candidates if p.exists()]
    if not existing:
        raise RuntimeError(
            "没有找到 state_5.sqlite。\n"
            f"已检查：{candidates[0]}\n"
            f"        {candidates[1]}"
        )

    database = max(
        existing,
        key=lambda p: (database_activity_ns(p), p == home / "state_5.sqlite"),
    )

    return CodexPaths(
        home=home,
        config=home / "config.toml",
        database=database,
        sessions=home / "sessions",
        backup_root=home / "history_relink_backups",
    )


def read_current_provider(config_path: Path) -> str:
    """
    读取 config.toml 顶层 model_provider。

    大小写必须原样保留，例如：
      openai  !=  OpenAI

    如果官方配置完全省略 model_provider，则按 Codex 默认值 openai 处理。
    """
    if not config_path.exists():
        raise RuntimeError(f"找不到配置文件：{config_path}")

    text = config_path.read_text(encoding="utf-8")

    # 只扫描 TOML 顶层，避免误读 [model_providers.xxx]。
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            break
        match = re.match(r'^model_provider\s*=\s*"([^"]+)"\s*$', line)
        if match:
            return match.group(1)

    return "openai"


def database_provider_counts(db_path: Path) -> Counter[str]:
    """统计数据库 threads.model_provider 分布。"""
    with closing(sqlite3.connect(db_path)) as conn:
        rows = conn.execute(
            """
            SELECT model_provider, COUNT(*)
            FROM threads
            GROUP BY model_provider
            ORDER BY COUNT(*) DESC
            """
        ).fetchall()

    counts: Counter[str] = Counter()
    for provider, count in rows:
        counts[str(provider) if provider is not None else "(null)"] = int(count)
    return counts


def count_database_mismatches(db_path: Path, target_provider: str) -> int:
    """统计数据库里还有多少线程不是目标 Provider。"""
    with closing(sqlite3.connect(db_path)) as conn:
        row = conn.execute(
            """
            SELECT COUNT(*)
            FROM threads
            WHERE model_provider IS NULL
               OR model_provider <> ?
            """,
            (target_provider,),
        ).fetchone()
    return int(row[0])


def sync_database_provider(db_path: Path, target_provider: str) -> int:
    """
    核心修改 ①：
      threads.model_provider -> 当前 Provider

    只改 Provider，不改 model/cwd/thread id。
    """
    with closing(sqlite3.connect(db_path, timeout=30.0)) as conn:
        conn.execute("PRAGMA busy_timeout = 30000")
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.execute(
            """
            UPDATE threads
            SET model_provider = ?
            WHERE model_provider IS NULL
               OR model_provider <> ?
            """,
            (target_provider, target_provider),
        )
        updated = int(cursor.rowcount)
        conn.commit()
    return updated


@dataclass
class SessionScan:
    files_scanned: int
    parse_errors: int
    files_needing_change: set[Path]
    session_meta_counts: Counter[str]
    thread_settings_counts: Counter[str]
    session_meta_mismatches: int
    thread_settings_mismatches: int


@dataclass
class SessionSyncResult:
    files_scanned: int
    files_changed: int
    session_meta_changed: int
    thread_settings_changed: int


def iter_rollouts(sessions_dir: Path) -> list[Path]:
    """列出全部 rollout JSONL。"""
    if not sessions_dir.exists():
        return []
    return sorted(sessions_dir.rglob("rollout-*.jsonl"))


def scan_sessions(sessions_dir: Path, target_provider: str) -> SessionScan:
    """
    只扫描实机验证过的两个 Provider 路径：

    ② session_meta
       $.payload.model_provider

    ③ event_msg -> thread_settings_applied
       $.payload.thread_settings.model_provider_id

    不递归修改任意同名字段，避免误伤聊天正文或其他 JSON。
    """
    files = iter_rollouts(sessions_dir)
    meta_counts: Counter[str] = Counter()
    settings_counts: Counter[str] = Counter()
    files_needing_change: set[Path] = set()

    parse_errors = 0
    meta_mismatches = 0
    settings_mismatches = 0

    for path in files:
        with path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                if not raw_line.strip():
                    continue

                try:
                    obj = json.loads(raw_line)
                except json.JSONDecodeError:
                    parse_errors += 1
                    continue

                # 核心路径 ②
                if obj.get("type") == "session_meta":
                    payload = obj.get("payload")
                    if isinstance(payload, dict):
                        provider = payload.get("model_provider")
                        if provider is not None:
                            provider_text = str(provider)
                            meta_counts[provider_text] += 1
                            if provider_text != target_provider:
                                meta_mismatches += 1
                                files_needing_change.add(path)

                # 核心路径 ③
                payload = obj.get("payload")
                if (
                    obj.get("type") == "event_msg"
                    and isinstance(payload, dict)
                    and payload.get("type") == "thread_settings_applied"
                ):
                    thread_settings = payload.get("thread_settings")
                    if isinstance(thread_settings, dict):
                        provider = thread_settings.get("model_provider_id")
                        if provider is not None:
                            provider_text = str(provider)
                            settings_counts[provider_text] += 1
                            if provider_text != target_provider:
                                settings_mismatches += 1
                                files_needing_change.add(path)

    return SessionScan(
        files_scanned=len(files),
        parse_errors=parse_errors,
        files_needing_change=files_needing_change,
        session_meta_counts=meta_counts,
        thread_settings_counts=settings_counts,
        session_meta_mismatches=meta_mismatches,
        thread_settings_mismatches=settings_mismatches,
    )


def split_line_ending(raw_line: str) -> tuple[str, str]:
    """拆分正文与原始换行符。"""
    if raw_line.endswith("\r\n"):
        return raw_line[:-2], "\r\n"
    if raw_line.endswith("\n"):
        return raw_line[:-1], "\n"
    if raw_line.endswith("\r"):
        return raw_line[:-1], "\r"
    return raw_line, ""


def atomic_write_text(path: Path, text: str) -> None:
    """先写临时文件，再原子替换，避免留下半截 JSONL。"""
    temp = path.with_name(f".{path.name}.relink-{os.getpid()}-{time.time_ns()}.tmp")
    try:
        with temp.open("w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def sync_session_file(path: Path, target_provider: str) -> tuple[int, int]:
    """
    修改单个 rollout 文件。

    返回：
      (session_meta 修改次数, thread_settings_applied 修改次数)
    """
    with path.open("r", encoding="utf-8", newline="") as handle:
        original_lines = handle.readlines()

    new_lines: list[str] = []
    meta_changed = 0
    settings_changed = 0

    for raw_line in original_lines:
        content, ending = split_line_ending(raw_line)

        if not content.strip():
            new_lines.append(raw_line)
            continue

        obj = json.loads(content)
        changed_this_line = False

        # 核心修改 ②
        if obj.get("type") == "session_meta":
            payload = obj.get("payload")
            if isinstance(payload, dict):
                provider = payload.get("model_provider")
                if provider is not None and str(provider) != target_provider:
                    payload["model_provider"] = target_provider
                    meta_changed += 1
                    changed_this_line = True

        # 核心修改 ③
        # 注意：thread_settings_applied 是 payload.type，不是顶层 type。
        payload = obj.get("payload")
        if (
            obj.get("type") == "event_msg"
            and isinstance(payload, dict)
            and payload.get("type") == "thread_settings_applied"
        ):
            thread_settings = payload.get("thread_settings")
            if isinstance(thread_settings, dict):
                provider = thread_settings.get("model_provider_id")
                if provider is not None and str(provider) != target_provider:
                    thread_settings["model_provider_id"] = target_provider
                    settings_changed += 1
                    changed_this_line = True

        # 未修改的 4 万多行保持原文本不动；
        # 只有真正修改的 JSON 行才重新序列化。
        if changed_this_line:
            content = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))

        new_lines.append(content + ending)

    if meta_changed or settings_changed:
        atomic_write_text(path, "".join(new_lines))

    return meta_changed, settings_changed


def sync_sessions(
    sessions_dir: Path,
    target_provider: str,
    files_to_change: set[Path],
) -> SessionSyncResult:
    """只修改预扫描确认需要迁移的 rollout 文件。"""
    meta_changed = 0
    settings_changed = 0
    files_changed = 0

    for path in sorted(files_to_change):
        changed_meta, changed_settings = sync_session_file(path, target_provider)
        if changed_meta or changed_settings:
            files_changed += 1
            meta_changed += changed_meta
            settings_changed += changed_settings

    return SessionSyncResult(
        files_scanned=len(iter_rollouts(sessions_dir)),
        files_changed=files_changed,
        session_meta_changed=meta_changed,
        thread_settings_changed=settings_changed,
    )


def backup_database(db_path: Path, output_path: Path) -> None:
    """使用 SQLite backup API 创建一致性数据库备份。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(db_path)) as source:
        with closing(sqlite3.connect(output_path)) as target:
            source.backup(target)


def safe_name(value: str) -> str:
    """把 Provider 名称转换为安全目录名。"""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value)
    return cleaned or "provider"


def create_backup(
    paths: CodexPaths,
    files_to_change: set[Path],
    target_provider: str,
) -> Path:
    """
    同步前备份：
      - 当前实际数据库
      - 本次真正会修改的完整 rollout 文件

    不复制整个 sessions，避免不必要的体积。
    """
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = paths.backup_root / f"{stamp}-to-{safe_name(target_provider)}"
    backup_dir.mkdir(parents=True, exist_ok=False)

    backup_database(paths.database, backup_dir / "state_5.sqlite.bak")

    sessions_backup = backup_dir / "sessions"
    for source in sorted(files_to_change):
        relative = source.relative_to(paths.sessions)
        destination = sessions_backup / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    manifest = {
        "version": VERSION,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "target_provider": target_provider,
        "database": str(paths.database),
        "rollout_files_backed_up": len(files_to_change),
    }

    (backup_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return backup_dir


def prune_old_backups(backup_root: Path, max_backups: int = MAX_BACKUPS) -> int:
    """
    自动清理旧备份，只保留最近 max_backups 份。

    说明：
    - 只处理 history_relink_backups 下、由本工具创建且包含 manifest.json 的目录；
    - 不会误删用户手工放进去的其他文件或目录；
    - 按目录修改时间从新到旧排序；
    - 只在本次同步验证成功后调用，因此失败时不会提前删除旧备份。
    """
    if max_backups < 1:
        raise ValueError("max_backups 必须至少为 1")

    if not backup_root.exists():
        return 0

    # 只认带 manifest.json 的目录，避免误删其他内容。
    backups = [
        path
        for path in backup_root.iterdir()
        if path.is_dir() and (path / "manifest.json").exists()
    ]

    # 最近的排在前面。
    backups.sort(
        key=lambda path: path.stat().st_mtime_ns,
        reverse=True,
    )

    removed = 0

    for old_backup in backups[max_backups:]:
        shutil.rmtree(old_backup)
        removed += 1

    return removed


def print_counter(title: str, counts: Counter[str]) -> None:
    print(title)
    if not counts:
        print("  (none)")
        return
    for provider, count in counts.most_common():
        print(f"  {provider!r}: {count}")


def print_status(paths: CodexPaths, target_provider: str) -> SessionScan:
    """显示当前状态，不修改任何内容。"""
    print(f"Codex History Relink v{VERSION}")
    print()
    print(f"Codex home : {paths.home}")
    print(f"Config     : {paths.config}")
    print(f"Database   : {paths.database}")
    print(f"Sessions   : {paths.sessions}")
    print(f"Target     : {target_provider!r}")
    print()

    db_counts = database_provider_counts(paths.database)
    session_scan = scan_sessions(paths.sessions, target_provider)

    print_counter("Database providers:", db_counts)
    print()
    print_counter(
        "session_meta.payload.model_provider:",
        session_scan.session_meta_counts,
    )
    print()
    print_counter(
        "thread_settings_applied.model_provider_id:",
        session_scan.thread_settings_counts,
    )
    print()

    print("Mismatches:")
    print(f"  Database threads       : {count_database_mismatches(paths.database, target_provider)}")
    print(f"  session_meta fields    : {session_scan.session_meta_mismatches}")
    print(f"  thread settings fields : {session_scan.thread_settings_mismatches}")
    print(f"  Rollout files to change: {len(session_scan.files_needing_change)}")
    print(f"  JSON parse errors      : {session_scan.parse_errors}")

    return session_scan


def verify(paths: CodexPaths, target_provider: str) -> tuple[bool, SessionScan, int]:
    """验证三处 Provider 是否全部一致。"""
    db_mismatches = count_database_mismatches(paths.database, target_provider)
    session_scan = scan_sessions(paths.sessions, target_provider)

    ok = (
        db_mismatches == 0
        and session_scan.session_meta_mismatches == 0
        and session_scan.thread_settings_mismatches == 0
        and session_scan.parse_errors == 0
    )

    return ok, session_scan, db_mismatches


def run_sync(paths: CodexPaths, target_provider: str, dry_run: bool) -> int:
    print_status(paths, target_provider)
    print()

    pre_scan = scan_sessions(paths.sessions, target_provider)
    db_mismatches = count_database_mismatches(paths.database, target_provider)

    if pre_scan.parse_errors:
        print(
            f"ERROR: 检测到 {pre_scan.parse_errors} 个 JSON 解析错误；为避免破坏历史，本次不修改。",
            file=sys.stderr,
        )
        return 2

    if dry_run:
        print("Dry-run：只扫描，不修改任何文件。")
        return 0

    if (
        db_mismatches == 0
        and pre_scan.session_meta_mismatches == 0
        and pre_scan.thread_settings_mismatches == 0
    ):
        print("所有历史 Provider 已经与当前 Provider 一致，无需修改。")
        return 0

    backup_dir = create_backup(paths, pre_scan.files_needing_change, target_provider)
    print(f"Backup     : {backup_dir}")
    print()

    # ① SQLite
    db_updated = sync_database_provider(paths.database, target_provider)

    # ② + ③ rollout
    session_result = sync_sessions(
        paths.sessions,
        target_provider,
        pre_scan.files_needing_change,
    )

    print("Migration:")
    print(f"  Database rows updated          : {db_updated}")
    print(f"  Rollout files changed          : {session_result.files_changed}")
    print(f"  session_meta fields changed    : {session_result.session_meta_changed}")
    print(f"  thread settings fields changed : {session_result.thread_settings_changed}")
    print()

    ok, post_scan, post_db_mismatches = verify(paths, target_provider)

    print("Verification:")
    print(f"  Database mismatches        : {post_db_mismatches}")
    print(f"  session_meta mismatches    : {post_scan.session_meta_mismatches}")
    print(f"  thread settings mismatches : {post_scan.thread_settings_mismatches}")
    print(f"  JSON parse errors          : {post_scan.parse_errors}")
    print()

    if not ok:
        print(
            "ERROR: 验证未通过。备份位于："
            f"{backup_dir}",
            file=sys.stderr,
        )
        return 3

    # 只有本次同步和最终验证都成功后，才轮转旧备份。
    # 这样如果迁移失败，当前安全备份和之前的旧备份都会保留下来。
    removed_backups = prune_old_backups(
        paths.backup_root,
        MAX_BACKUPS,
    )

    print("SUCCESS: 三处 Provider 已全部同步到当前 Provider。")
    print(f"Backups: 最多保留最近 {MAX_BACKUPS} 份，本次清理旧备份 {removed_backups} 份。")
    print("建议重新启动 Codex Desktop 后再打开旧聊天继续使用。")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="把 Codex 本地历史线程的 Provider 元数据重新绑定到当前 Provider。"
    )
    parser.add_argument("--codex-home", help="指定 Codex Home；默认 ~/.codex")
    parser.add_argument(
        "--provider",
        help="手动指定目标 Provider；默认读取 config.toml 顶层 model_provider。",
    )
    parser.add_argument("--status", action="store_true", help="只显示状态，不修改文件。")
    parser.add_argument("--dry-run", action="store_true", help="完整预扫描，但不修改文件。")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        paths = resolve_paths(args.codex_home)
        target_provider = (
            args.provider
            if args.provider is not None
            else read_current_provider(paths.config)
        )

        if not target_provider.strip():
            raise RuntimeError("目标 Provider 不能为空。")

        if args.status:
            print_status(paths, target_provider)
            return 0

        return run_sync(paths, target_provider, args.dry_run)

    except KeyboardInterrupt:
        print("\n已取消。", file=sys.stderr)
        return 130

    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
