# Security and Privacy

Codex History Relink directly modifies local Codex Desktop state. Its design intentionally minimizes the scope of those changes.

## Data handling

The application does not:
- upload local conversations
- transmit local history to a remote service
- send telemetry
- read API keys for migration
- copy credentials between providers
- transfer cloud conversations between accounts

All repair work is local.

## Files touched

Depending on the local Codex layout, the tool may read or modify:
- `config.toml` — read only
- `state_*.sqlite` — `threads.model_provider`
- `sessions/**/rollout-*.jsonl` — first-line `session_meta.model_provider`
- `session_index.jsonl` — rebuilt to restore sidebar indexing

It intentionally preserves historical `model` values.

## Safety controls

Before a real repair:
- database schema is validated
- a single-instance lock is acquired
- a SQLite snapshot is created
- the session index is backed up if present
- session first-line metadata is backed up

During repair:
- SQLite lock/busy errors are retried
- session/index replacement uses temporary files and atomic replacement
- file busy errors are retried

After repair:
- provider mismatches are re-scanned
- old backups are only rotated after successful verification
- failed repairs trigger an automatic rollback attempt

## Backups

Backups are local and stored under:

```text
~/.codex/history_sync_backups/
```

The default retention cap is five successful backup sets.

## Reporting security issues

Do not include private conversation contents, API keys, or complete local database files in public GitHub issues.

Prefer sharing:
- application version
- operating system
- `latest.txt`
- sanitized `latest.json`
- Codex local directory layout
- error messages with personal paths redacted when desired
