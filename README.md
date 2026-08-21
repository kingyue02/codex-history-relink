# Codex History Relink v0.4.1-rc1

Windows-only one-shot utility for relinking local Codex history after switching APIs, providers, or login modes.

切换 Codex API、Provider 或登录模式后，运行一次即可重新挂载本地历史记录。

## 平台

- Windows x64
- 未提供 macOS 或 Linux 版本

## 已验证的核心机制

只把当前 `config.toml` 的 `model_provider` 同步到三处：

1. SQLite：`threads.model_provider`
2. rollout：`session_meta.payload.model_provider`
3. rollout：`event_msg -> thread_settings_applied -> payload.thread_settings.model_provider_id`

## 明确不修改

- `config.toml`（只读）
- `auth.json`
- API Key
- `base_url`
- `model`
- `review_model`
- `cwd`
- thread id
- 聊天正文
- `session_index.jsonl`

## 下载

在 GitHub 的 Releases 页面下载 `CodexHistoryRelink-Windows-x64.exe`。

## 使用

建议先关闭 Codex Desktop。

```powershell
.\CodexHistoryRelink-Windows-x64.exe --status
.\CodexHistoryRelink-Windows-x64.exe --dry-run
.\CodexHistoryRelink-Windows-x64.exe
```

默认读取 `%USERPROFILE%\.codex\config.toml` 顶层的 `model_provider`。也可以手动指定：

```powershell
.\CodexHistoryRelink-Windows-x64.exe --provider OpenAI
```

## 备份

每次真正修改前自动创建：

`%USERPROFILE%\.codex\history_relink_backups\<时间>-to-<Provider>\`

其中包括 SQLite 一致性备份、本次将修改的 rollout 文件和 `manifest.json`。

## 验证标准

同步后必须同时满足：

- Database mismatches = 0
- session_meta mismatches = 0
- thread settings mismatches = 0
- JSON parse errors = 0

程序才会输出 `SUCCESS`。

## 测试

```powershell
python -m unittest discover -s tests -v
```
