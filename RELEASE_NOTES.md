# Codex History Relink v0.4.1-rc1 — Windows x64

切换 Codex API、Provider 或登录模式后，如果原有本地聊天记录不再显示，本工具可将历史记录中的 Provider 元数据重新同步到当前 Provider。

## Before you run it

1. 关闭 Codex Desktop
2. 先运行 `--status` 查看当前状态
3. 再运行 `--dry-run` 预览修改
4. 确认后直接运行 EXE 执行修复

程序会在真实修改前自动备份相关数据库和 rollout 文件。

## Scope

- ✅ Windows x64
- ✅ 已验证：OpenAI login → custom provider → OpenAI login
- ⚠️ Release Candidate，请保留自动生成的备份
- ❌ 不提供 macOS 或 Linux 版本

本版本只同步三个经过验证的 Provider 元数据位置，不修改认证信息、API Key、Base URL、模型设置、thread id 或聊天正文。

下载文件：`CodexHistoryRelink-Windows-x64.exe`