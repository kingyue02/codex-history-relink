# Codex History Relink v0.3.0-rc1

Release candidate for public testing.

## What it does

After switching Codex account / API / provider:

1. Run the appropriate `CodexHistoryRelink` binary once.
2. The tool detects the active provider.
3. It relinks local history metadata.
4. It verifies the result and exits.

No GUI and no configuration are required.

## Tested

Verified on Windows with both directions:

- OpenAI login -> custom provider
- custom provider -> OpenAI login

## Important

This is a release candidate. Keep local backups and report sanitized logs when testing on additional systems.
