#!/usr/bin/env bash
set -euo pipefail

python3 -m pip install --upgrade pip
python3 -m pip install pyinstaller .

rm -rf build dist

export CODEX_HISTORY_RELINK_BUILD_COMMIT="$(git rev-parse --short HEAD 2>/dev/null || true)"
export CODEX_HISTORY_RELINK_BUILD_TAG="$(git describe --tags --exact-match 2>/dev/null || true)"

python3 -m PyInstaller \
  --clean \
  --onefile \
  --name CodexHistoryRelink \
  --paths src \
  run_relink.py

echo
echo "Built: dist/CodexHistoryRelink"
