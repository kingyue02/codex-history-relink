# Codex History Relink

**切换 Codex 账号、API 或 Provider 后，运行一次即可重新挂载本地历史记录。**

这是一个一次性运行的 Codex Desktop 本地历史修复工具。

使用逻辑非常简单：

```text
切换 Codex 账号 / API / Provider
                ↓
运行 CodexHistoryRelink
                ↓
自动把本地历史重新挂载到当前 Provider
                ↓
完成
```

不提供 GUI，不要求选择路径，不要求输入 Provider，不常驻后台。

## 为什么需要它

Codex Desktop 在切换登录方式、API 或模型供应商后，有时本地会话文件仍然存在，但侧边栏历史消失。

其中一个原因是，本地线程仍然归属于之前的 `model_provider`。

Codex History Relink 会自动检测当前 Provider，并把本地历史安全地重新映射到当前 Provider。

它**不会**把一个云端账号的聊天迁移到另一个云端账号。

## 功能

- 一次性运行
- 无用户输入
- Release 版本无需安装 Python
- 核心支持 Windows / macOS / Linux
- 自动发现 `CODEX_HOME` 或 `~/.codex`
- 同时支持：
  - `~/.codex/state_*.sqlite`
  - `~/.codex/sqlite/state_*.sqlite`
- 结合数据库和 `-wal` 活跃时间选择实际正在使用的状态库
- 动态读取任意 `model_provider`
- 配置未显式写 Provider 时使用 Codex 内置默认 `openai`
- 默认只修改 `model_provider`
- 保留历史 `model`
- 只有真实发生 Provider mismatch 时才备份
- 最多保留最近 5 个成功备份集
- session/index 使用原子替换和占用重试
- SQLite 写入支持锁等待和重试
- 跨平台单实例锁
- 修复失败时自动尝试回滚
- 自动重建 `session_index.jsonl`
- 修复后要求 Provider mismatch 为 0 才判定成功
- 自动生成本地日志
- 不上传聊天记录

## 普通用户怎么用

1. 先在 Codex 中切换到目标账号、API 或 Provider。
2. 最好关闭 Codex，或者确保 Codex 当前没有正在生成回复。
3. 运行对应系统的 `CodexHistoryRelink`。
4. 如果侧边栏没有立即刷新，重新打开 Codex。

整个过程不需要填写任何参数。

## 日志

正常日志：

```text
~/.codex/history_sync_logs/latest.txt
~/.codex/history_sync_logs/latest.json
```

如果连 Codex 本地目录都无法识别：

```text
~/CodexHistoryRelink-error.txt
```

## 备份

只有检测到真实 Provider mismatch 时才创建备份。

默认目录：

```text
~/.codex/history_sync_backups/
```

默认只保留最近 **5** 个成功备份集。

只有新一次修复验证成功后，程序才会删除更老的备份。

## 隐私和安全

Codex History Relink：

- 不上传聊天记录
- 不发送遥测
- 不读取或迁移 API Key
- 不迁移云端账号聊天
- 不主动改写历史 model
- 只修改恢复本地历史显示所需的 Provider 归属和索引信息

详细说明见 [SECURITY.md](SECURITY.md)。

## 当前状态

`v0.3.0-rc1` 为 Release Candidate。

核心双向流程已经在真实 Windows Codex Desktop 环境中验证：

```text
OpenAI → 自定义 Provider → 修复成功
自定义 Provider → OpenAI → 修复成功
```

## License

MIT
