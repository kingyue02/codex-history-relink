# Codex History Relink

**Restore local Codex history after switching accounts, APIs, or providers — run it once.**

Codex History Relink is a one-shot repair utility for local Codex Desktop history visibility.

It is intentionally simple:

```text
Switch Codex account / API / provider
                ↓
Run CodexHistoryRelink
                ↓
Local history is relinked to the active provider
                ↓
Done
```

No GUI. No configuration wizard. No provider prompt. No background process.

## Why this exists

After switching Codex login mode, API, or model provider, local conversation files may still exist while the sidebar no longer shows them. The local history can be associated with a previous `model_provider`.

Codex History Relink detects the active provider and safely remaps local history metadata to that provider.

It does **not** transfer cloud conversations between accounts.

## Features

- One-shot execution
- No user input required
- No Python required for release binaries
- Windows, macOS, and Linux core support
- Automatically discovers `CODEX_HOME` or `~/.codex`
- Supports both:
  - `~/.codex/state_*.sqlite`
  - `~/.codex/sqlite/state_*.sqlite`
- Uses DB + WAL activity to select the active state database
- Dynamically detects any explicit `model_provider`
- Uses built-in `openai` as the implicit default when `model_provider` is absent
- Only rewrites `model_provider`
- Preserves historical `model`
- Backs up only when a real mismatch exists
- Keeps the latest 5 successful backup sets
- Uses atomic file replacement and busy-file retry
- Uses SQLite lock retry
- Uses a cross-platform single-instance lock
- Attempts automatic rollback on repair failure
- Rebuilds `session_index.jsonl`
- Verifies zero remaining provider mismatches before declaring success
- Writes local JSON and text logs
- Never uploads conversations

## Usage

### End users

1. Switch Codex to the target account / API / provider.
2. Preferably close Codex or leave it idle.
3. Run the binary once.
4. Reopen or refresh Codex if the sidebar does not refresh immediately.

Windows:

```text
CodexHistoryRelink-Windows-x64.exe
```

macOS Apple Silicon:

```text
CodexHistoryRelink-macOS-arm64
```

macOS Intel:

```text
CodexHistoryRelink-macOS-x64
```

Linux x64:

```text
CodexHistoryRelink-Linux-x64
```

## Logs

Normal logs are written to:

```text
~/.codex/history_sync_logs/latest.txt
~/.codex/history_sync_logs/latest.json
```

If Codex environment discovery fails before the normal log directory can be resolved:

```text
~/CodexHistoryRelink-error.txt
```

## Backups

Backups are created only when a real provider mismatch is detected.

Location:

```text
~/.codex/history_sync_backups/
```

By default, the most recent **5** successful backup sets are retained.

Old backups are deleted only after a new repair passes verification.

## Privacy and security

Codex History Relink:

- does not upload conversation history
- does not send telemetry
- does not read or migrate API keys
- does not transfer cloud conversations
- does not intentionally change historical model values
- only touches local Codex history metadata needed for relinking

See [SECURITY.md](SECURITY.md) for more detail.

## Scope

This utility is for:

- switching Codex API providers
- switching login mode
- switching accounts where local history becomes hidden
- restoring visibility when local session files still exist

It is not for:

- recovering deleted local files
- moving cloud conversations between accounts
- cross-device history migration

## Developer build

Python 3.10+ is only required for development.

### Windows debug build

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows_debug.ps1
```

### Windows release build

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1
```

### macOS / Linux

```bash
bash scripts/build_unix.sh
```

## Release process

Tagging a version such as:

```text
v0.3.0-rc1
```

runs GitHub Actions on Windows, macOS Intel, macOS Apple Silicon, and Linux.

The release workflow produces native binaries and SHA256 checksums.

## Status

`v0.3.0-rc1` is a release candidate.

The core relink workflow has been validated in both directions between OpenAI login and a custom provider on a real Windows Codex Desktop environment.

## License

MIT
