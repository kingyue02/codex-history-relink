# Codex History Relink v0.3.1-rc1

Release candidate fixing authentication state when switching Codex providers.

## What changed

- Saves the complete local `auth.json` as a provider-specific local profile.
- Restores the target provider authentication profile together with history metadata.
- Uses a two-stage login flow the first time a provider has no saved profile.
- Includes active authentication state in automatic repair rollback.
- Never logs or uploads authentication contents.

## First-time provider setup

When switching from provider A to provider B for the first time:

1. Run the utility. It saves A's authentication locally and asks for B login.
2. Sign in to provider B in Codex.
3. Run the utility again to save B's profile and relink history.

Later A/B switches can restore both authentication and local history automatically.

## Validation

- Windows x64: core history relink validated on a real device; authentication Profile fix passed automated tests and awaits RC feedback.
- macOS Intel: CI build passed; awaiting real-device validation.
- macOS Apple Silicon: CI build passed; awaiting real-device validation.
- Linux x64: CI build passed; awaiting real-device validation.

This is a Pre-release. Keep local backups and report only sanitized logs.
