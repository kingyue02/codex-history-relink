$ErrorActionPreference = "Stop"

python -m pip install --upgrade pip
python -m pip install pyinstaller .

if (Test-Path "build") {
    Remove-Item -Recurse -Force "build"
}
if (Test-Path "dist") {
    Remove-Item -Recurse -Force "dist"
}
if (Test-Path "CodexHistoryRelink-Debug.spec") {
    Remove-Item -Force "CodexHistoryRelink-Debug.spec"
}

$env:CODEX_HISTORY_RELINK_BUILD_COMMIT = (git rev-parse --short HEAD 2>$null)
$env:CODEX_HISTORY_RELINK_BUILD_TAG = (git describe --tags --exact-match 2>$null)

python -m PyInstaller `
  --clean `
  --onefile `
  --console `
  --name "CodexHistoryRelink-Debug" `
  --paths "src" `
  "run_relink.py"

Write-Host ""
Write-Host "Built: dist\CodexHistoryRelink-Debug.exe"
