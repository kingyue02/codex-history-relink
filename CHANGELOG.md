# Changelog

## [0.3.0-rc1] - 2026-08-11

Release candidate focused on distribution readiness.

### Added
- English and Simplified Chinese README files.
- Security/privacy documentation.
- Build/version information in logs.
- GitHub Actions native builds for Windows, macOS Intel, macOS Apple Silicon, and Linux.
- SHA256 checksum generation for release artifacts.
- Release notes template.

### Retained from v0.2.2
- Root and `sqlite/` state database discovery.
- DB + WAL activity selection.
- Dynamic provider detection.
- Provider-only relinking by default.
- Atomic session/index writes.
- SQLite busy retry.
- Cross-platform process lock.
- Backup rotation capped at five successful sets.
- Automatic rollback attempt.
- Post-repair verification.

## [0.2.2] - 2026-08-11

- Added root / `sqlite/` DB discovery.
- Added WAL-aware activity selection.
- Added atomic file replacement retry.
- Added cross-platform single-instance locking.
- Added automatic rollback attempt.

## [0.2.1] - 2026-08-11

- Added backup rotation.
- Only backs up on real mismatch.
- Preserves historical model values.

## [0.2.0] - 2026-08-11

- Introduced one-shot no-GUI repair workflow.
