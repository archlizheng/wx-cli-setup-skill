# 接入各 Agent

同一台 Mac 共用一个 wx 程序与该用户的状态目录，但不要把密钥放到技能文件夹。只安装到用户指定的宿主。保留现有微信查询技能。技能只依赖终端和 Python，无必需 MCP。

推荐先克隆本仓库，再把 `skills/wx-cli-setup` 安装到宿主发现目录。直接读取仓库里的 SKILL.md 也能完成配置，不必先安装 wx。

| 宿主 | 技能位置 | 调用方式 | 状态 |
|---|---|---|---|
| Hermes | 实际 HERMES_HOME 的 `skills/social/wx-cli-setup`，默认 `~/.hermes/skills/social/wx-cli-setup` | `/reload-skills` 后 `/wx-cli-setup` | 本机技能发现与 wx 基础通路验证 |
| Codex | `~/.agents/skills/wx-cli-setup`（或用户指定的 CODEX_HOME/skills） | `$wx-cli-setup` 或自然语言 | 本机技能发现与 wx 基础通路验证 |
| Claude Code | `~/.claude/skills/wx-cli-setup`，项目可用 `.claude/skills/` | `/wx-cli-setup` | 官方目录规则；待用户本机验证 |
| OpenClaw | 当前 workspace 的 `skills/wx-cli-setup`；共享可用 `~/.openclaw/skills/wx-cli-setup`，优先核对本机配置 | 让 Agent 使用 wx-cli-setup；按宿主发现规则加载 | 官方目录规则；待用户本机验证 |

Codex/Hermes 可用符号链接共用源码；Claude/OpenClaw 兼容说明用目录复制，避免未经验证的链接发现差异。发布 ZIP 解压后复制整个技能目录，不能只复制 SKILL.md。相对 references/scripts 必须保留。

以下是 Codex 安装示例，`wx_skill_repo` 替换为实际仓库路径：

```bash
wx_skill_repo="$HOME/projects/wx-cli-setup-skill"
mkdir -p "$HOME/.agents/skills"
cp -R "$wx_skill_repo/skills/wx-cli-setup" "$HOME/.agents/skills/"
```

目录已存在时比较内容、先备份再按用户要求更新，不能直接套用复制命令造成嵌套目录。宿主发现不到时检查实际配置根目录、禁用列表和工具权限。不要为了启用技能关闭宿主安全限制。

Hermes 0.21.6 支持 `/reload-skills` 重扫并提示新技能；系统提示索引有独立缓存，显式调用最可靠。需要自动识别仍未生效时再考虑正常重启网关，先检查是否有正在执行的任务。Codex 发现通常在下一轮刷新。其他宿主按当前官方说明处理，不保证全部热加载。

定时进程可能没有交互 shell 的 PATH；将绝对 wx、Python、技能路径写进任务。日志和状态保持在本机，别随公开技能提交。

官方资料：[Codex](https://learn.chatgpt.com/docs/build-skills)、[Claude Code](https://code.claude.com/docs/en/skills)、[OpenClaw](https://docs.openclaw.ai/tools/skills)。
