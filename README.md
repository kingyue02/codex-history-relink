# Codex History Relink v0.4.1-rc1

这是基于一次完整手工实机验证后重新整理的最小版本。

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

## 使用

建议先关闭 Codex Desktop。

查看状态：

```powershell
CodexHistoryRelink.exe --status
```

只扫描：

```powershell
CodexHistoryRelink.exe --dry-run
```

执行迁移：

```powershell
CodexHistoryRelink.exe
```

默认读取 `%USERPROFILE%\.codex\config.toml` 顶层 `model_provider`。

也可手动指定：

```powershell
CodexHistoryRelink.exe --provider OpenAI
```

## 备份

每次真正修改前自动创建：

`~/.codex/history_relink_backups/<时间>-to-<Provider>/`

包含：

- SQLite 一致性备份
- 本次真正要修改的完整 rollout 文件
- `manifest.json`

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

开发环境也可以直接运行 `python .\codex_history_relink.py`。Release 页面提供
Windows x64、macOS Intel、macOS Apple Silicon 和 Linux x64 二进制文件。
