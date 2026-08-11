# Codex History Relink

**Restore local Codex history after switching APIs, providers, or login modes — run it once.**

Codex History Relink is a one-shot repair utility for local Codex Desktop history visibility.

It is intentionally simple:

```text
Switch Codex API / provider / login mode
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
- No command-line configuration required
- No Python required for release binaries
- Windows, macOS, and Linux core support
- Automatically discovers `CODEX_HOME` or `~/.codex`
- Supports both:
  - `~/.codex/state_*.sqlite`
  - `~/.codex/sqlite/state_*.sqlite`
- Uses DB + WAL activity to select the active state database
- Dynamically detects any explicit `model_provider`
- Uses built-in `openai` as the implicit default when `model_provider` is absent
- Rewrites only history Provider metadata and preserves historical `model`
- Saves and restores the complete local `auth.json` per Provider
- Never logs or uploads authentication contents
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

1. Switch Codex to the target API, Provider, or login mode.
2. Preferably close Codex or leave it idle.
3. Run the binary once.
4. Reopen or refresh Codex if the sidebar does not refresh immediately.

The first time a target Provider has no saved authentication Profile, the utility pauses before changing history:

1. The first run saves the source Provider's `auth.json` locally.
2. Sign in to the target Provider in Codex.
3. Run the utility again to save the target Profile and complete the relink.

Later switches between enrolled Providers restore authentication and history automatically.

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

- does not upload conversation history or authentication data
- does not send telemetry or make network requests
- copies the complete local `auth.json` only between local Provider Profiles
- never writes authentication contents to logs
- does not transfer cloud conversations
- does not intentionally change historical model values

See [SECURITY.md](SECURITY.md) for more detail.

## Scope

This utility is for:

- switching Codex API providers
- switching login modes that change the active Provider identity
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
v0.3.1-rc1
```

runs GitHub Actions on Windows, macOS Intel, macOS Apple Silicon, and Linux.

The release workflow produces native binaries and SHA256 checksums.

## Status

`v0.3.1-rc1` is a Pre-release.

The core history relink workflow has been validated in both directions between OpenAI login and a custom Provider on a real Windows Codex Desktop environment. The new authentication Profile flow is covered by automated tests and is being released for RC real-device validation. Official account A → official account B is not currently claimed as validated.

Runtime validation:

- ✅ Windows x64: core history relink validated on a real device; authentication Profile fix awaiting RC feedback
- ⚠ macOS Intel: CI build passed, awaiting real-device validation
- ⚠ macOS Apple Silicon: CI build passed, awaiting real-device validation
- ⚠ Linux x64: CI build passed, awaiting real-device validation

A successful CI build confirms packaging, tests, and binary creation; it does not by itself confirm behavior in a real Codex Desktop environment.

## License

MIT
