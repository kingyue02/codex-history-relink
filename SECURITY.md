# Security and Privacy

Codex History Relink modifies local Codex Desktop state. Authentication Profile support is intentionally local-only and Provider-neutral.

## Data handling

The application does not:

- upload local conversations or authentication data
- transmit local history to a remote service
- send telemetry or make network requests
- print `auth.json` contents, API keys, tokens, or refresh tokens
- transfer cloud conversations between accounts

The application may read, copy, restore, and back up the complete local `auth.json`. Authentication bytes remain on the local machine and are never parsed for Provider-specific fields.

## Files touched

Depending on the local Codex layout, the tool may read or modify:

- `config.toml` — read only
- `auth.json` — locally profiled, restored, and included in transactional rollback
- `history_relink_profiles/<provider-id>/auth.json` — latest local authentication Profile for each Provider
- `state_*.sqlite` — `threads.model_provider`
- `sessions/**/rollout-*.jsonl` — first-line `session_meta.model_provider`
- `session_index.jsonl` — rebuilt to restore sidebar indexing

It intentionally preserves historical `model` values.

## Authentication Profile safety

- Profiles store the complete `auth.json` for forward compatibility.
- Profile directory names are sanitized and include a hash of the Provider identity.
- Profile and authentication backup files use best-effort owner-only permissions (`0600` for files and `0700` for directories on POSIX systems).
- A target Profile is restored only when it already exists or after a two-stage first-time enrollment.
- Authentication contents are never included in normal or fallback logs.

On the first switch from Provider A to an unenrolled Provider B, the utility saves A's authentication locally, removes the active copy, and stops before changing history. The user signs in to B and runs the utility again. This avoids sending A credentials to B or B credentials to A.

## Safety controls

Before a real repair:

- database schema is validated
- a single-instance lock is acquired
- a SQLite snapshot is created
- the active `auth.json` is backed up when present
- the session index is backed up if present
- session first-line metadata is backed up

During repair:

- SQLite lock/busy errors are retried
- auth/session/index replacement uses temporary files and atomic replacement
- file busy errors are retried

After repair:

- Provider mismatches are re-scanned
- old backups are only rotated after successful verification
- failed repairs trigger automatic rollback of history, session metadata, index, and active authentication

## Local storage

Transactional backups are stored under:

```text
~/.codex/history_sync_backups/
```

The default retention cap is five successful backup sets.

Provider authentication Profiles are stored under:

```text
~/.codex/history_relink_profiles/
```

Each Provider keeps only its latest Profile.

## Reporting security issues

Do not include private conversation contents, `auth.json`, API keys, tokens, complete local databases, or authentication Profile files in public GitHub issues.

Prefer sharing:

- application version
- operating system
- `latest.txt`
- sanitized `latest.json`
- Codex local directory layout
- error messages with personal paths redacted when desired
