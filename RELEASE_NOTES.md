# Codex History Relink v0.4.1-rc1

基于完整手工实机验证重新整理的最小 Release Candidate。

本版本仅同步三个经过验证的 Provider 元数据位置：

1. SQLite `threads.model_provider`
2. rollout `session_meta.payload.model_provider`
3. rollout `thread_settings_applied.payload.thread_settings.model_provider_id`

明确不修改 `config.toml`、`auth.json`、API Key、`base_url`、模型、工作目录、
thread id、聊天正文或 `session_index.jsonl`。

这是 Pre-release，请先使用 `--status` 或 `--dry-run` 检查，再执行正式迁移。
