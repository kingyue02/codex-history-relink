# Codex History Relink

**切换 Codex API、Provider 或登录模式后，运行一次即可重新挂载本地历史记录。**

这是一个一次性运行的 Codex Desktop 本地历史修复工具。

使用逻辑非常简单：

```text
切换 Codex API / Provider / 登录模式
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
- 无需命令行配置
- Release 版本无需安装 Python
- 核心支持 Windows / macOS / Linux
- 自动发现 `CODEX_HOME` 或 `~/.codex`
- 同时支持：
  - `~/.codex/state_*.sqlite`
  - `~/.codex/sqlite/state_*.sqlite`
- 结合数据库和 `-wal` 活跃时间选择实际正在使用的状态库
- 动态读取任意 `model_provider`
- 配置未显式写 Provider 时使用 Codex 内置默认 `openai`
- 仅改写历史 Provider 元数据，保留历史 `model`
- 按 Provider 在本地保存和恢复完整 `auth.json`
- 绝不在日志中输出或上传认证内容
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

1. 先在 Codex 中切换到目标 API、Provider 或登录模式。
2. 最好关闭 Codex，或者确保 Codex 当前没有正在生成回复。
3. 运行对应系统的 `CodexHistoryRelink`。
4. 如果侧边栏没有立即刷新，重新打开 Codex。

目标 Provider 第一次没有认证 Profile 时，工具会在修改历史前暂停：

1. 第一次运行会在本地保存源 Provider 的 `auth.json`。
2. 在 Codex 中登录目标 Provider。
3. 再运行一次，保存目标 Profile 并完成历史重挂载。

Profile 建立后，再次双向切换只需运行一次，认证状态和历史会一起恢复。整个过程不需要填写命令行参数。

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

- 不上传聊天记录或认证数据
- 不发送遥测，不发起网络请求
- 完整 `auth.json` 只在本机 Provider Profile 之间复制
- 绝不把认证内容写入日志
- 不迁移云端账号聊天
- 不主动改写历史 model

详细说明见 [SECURITY.md](SECURITY.md)。

## 当前状态

`v0.3.1-rc1` 为 Pre-release。

核心历史重挂载双向流程已在真实 Windows Codex Desktop 环境中验证；新增认证 Profile 流程已通过自动化测试，正在等待 RC 真实设备验证：

```text
OpenAI → 自定义 Provider → 修复成功
自定义 Provider → OpenAI → 修复成功
```

目前不宣称“官方账号 A → 官方账号 B”已经过验证。

运行时验证：

- ✅ Windows x64：核心历史重挂载已通过真实设备验证；认证 Profile 修复等待 RC 反馈
- ⚠ macOS Intel：CI 构建通过，等待真实设备验证
- ⚠ macOS Apple Silicon：CI 构建通过，等待真实设备验证
- ⚠ Linux x64：CI 构建通过，等待真实设备验证

CI 成功只代表测试、打包和二进制生成通过，不等于已经在真实 Codex Desktop 环境中验证。

## License

MIT
