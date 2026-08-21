# Codex History Relink

**Bring your local Codex conversations back after switching APIs, providers, or login modes.**

切换 Codex API、Provider 或登录模式后，如果原有本地聊天记录不再显示，运行一次即可重新挂载。

> Windows x64 only · One-shot repair · Automatic backup · No authentication changes

## Why this tool exists

Codex stores Provider metadata in both its local SQLite database and session rollout files. After switching APIs, providers, or login modes, that metadata can stop matching the active Provider—even though the conversations are still stored locally.

Codex History Relink reads the active `model_provider`, updates the verified metadata locations, and checks that they are consistent again.

适合以下情况：

- 切换 Provider 后，旧对话仍在本地，但 Codex Desktop 中不再正常显示
- 从 OpenAI 登录切换到自定义 Provider，之后再切回 OpenAI 登录
- 希望先检查问题，再决定是否修改本地历史数据

## What it changes

工具只同步以下三个经过验证的位置：

1. SQLite：`threads.model_provider`
2. rollout：`session_meta.payload.model_provider`
3. rollout：`thread_settings_applied.payload.thread_settings.model_provider_id`

它**不会修改**：

- `config.toml`（只读）
- `auth.json`、API Key 或登录凭据
- `base_url`、`model` 或 `review_model`
- 工作目录、thread id 或聊天正文
- `session_index.jsonl`

## Download

Download the Windows executable from [GitHub Releases](https://github.com/kingyue02/codex-history-relink/releases/tag/v0.4.1-rc1):

`CodexHistoryRelink-Windows-x64.exe`

No Python installation is required.

## Quick start

先关闭 Codex Desktop，然后在 EXE 所在目录打开 PowerShell。

### 1. Check the current state

```powershell
.\CodexHistoryRelink-Windows-x64.exe --status
```

### 2. Preview without changing files

```powershell
.\CodexHistoryRelink-Windows-x64.exe --dry-run
```

### 3. Relink the history

```powershell
.\CodexHistoryRelink-Windows-x64.exe
```

完成后重新启动 Codex Desktop。

默认从 `%USERPROFILE%\.codex\config.toml` 读取顶层 `model_provider`。也可以手动指定目标 Provider：

```powershell
.\CodexHistoryRelink-Windows-x64.exe --provider OpenAI
```

如需指定其他 Codex Home：

```powershell
.\CodexHistoryRelink-Windows-x64.exe --codex-home "D:\path\to\.codex"
```

## Safety and backup

执行真实修改前，程序会自动创建备份：

`%USERPROFILE%\.codex\history_relink_backups\<时间>-to-<Provider>\`

备份包括 SQLite 一致性备份、所有即将修改的 rollout 文件及 `manifest.json`。只有同时满足以下条件，程序才会输出 `SUCCESS`：

- Database mismatches = 0
- session_meta mismatches = 0
- thread settings mismatches = 0
- JSON parse errors = 0

## Validation status

- ✅ Windows x64：已进行实机验证
- ✅ 已验证流程：OpenAI login → custom provider → OpenAI login
- ⚠️ 尚未宣称或验证“官方账号 A → 官方账号 B”的历史互通
- ❌ 不提供 macOS 或 Linux 构建

This is currently a Release Candidate. Run `--status` and `--dry-run` first, and keep the generated backup until you have confirmed that the history appears correctly.

## Development

```powershell
python -m unittest discover -s tests -v
python .\codex_history_relink.py --help
```

## Disclaimer

This is an independent community utility and is not an official OpenAI product.