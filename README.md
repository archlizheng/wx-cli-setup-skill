# wx-cli-setup：让 Agent 帮你配置微信查询和定时任务

面向 macOS 的中文 Agent Skill，支持 Hermes、Codex、Claude Code、OpenClaw。把安装 wx-cli-again、初始化密钥、处理权限报错、验证查询和创建定时任务的经验整理成可执行流程。

**不是微信登录工具，也不是 wx-cli 的替代品。** 首次管理员密码、微信登录和必要权限由你在本机完成。日常查询无需 sudo。

## 一句话开始

把仓库链接发给可操作本机终端的 Agent：

> 请读取 https://github.com/archlizheng/wx-cli-setup-skill 中 skills/wx-cli-setup/SKILL.md，遵循它帮我配置本机微信查询，并创建我指定范围的定时摘要任务。先诊断现状，保留已有配置。

也可以克隆仓库后，请 Agent 读取本机的 `skills/wx-cli-setup/SKILL.md`。**仅把链接发给没有本机工具的网页聊天，不会自动获得你的微信数据。**

## 安装技能

```bash
git clone https://github.com/archlizheng/wx-cli-setup-skill.git
cd wx-cli-setup-skill
```

把整个 `skills/wx-cli-setup` 目录复制到所用 Agent 的技能位置；目录已存在时先备份并比较，避免嵌套复制。

| Agent | 个人技能位置 | 使用 |
|---|---|---|
| Hermes | 实际 HERMES_HOME/skills/social，默认 ~/.hermes/skills/social/wx-cli-setup | `/reload-skills`，再 `/wx-cli-setup` |
| Codex | ~/.agents/skills/wx-cli-setup | `$wx-cli-setup` |
| Claude Code | ~/.claude/skills/wx-cli-setup | `/wx-cli-setup` |
| OpenClaw | 当前 workspace/skills/wx-cli-setup；共享目录 ~/.openclaw/skills/wx-cli-setup | 请 Agent 使用 wx-cli-setup |

详细步骤与官方来源见 [Agent 接入](skills/wx-cli-setup/references/agents.md)。发布包解压后也包含完整技能目录。保留现有 wx-cli-again 查询技能即可，两者用途不同。

## 能解决什么

- 安装：复用可用 wx，或从公开仓库固定提交构建；隔离 Rust，不修改 shell profile。
- 排错：识别活动账号、多账号目录、Hardened Runtime 的 kr=5、缺少数据库密钥和 daemon 旧缓存。
- 验证：实际检查会话/联系人；授权后查询指定聊天，保留本机缓存和完整性限制。
- 自动化：提供群摘要、关键词提醒、未读整理、朋友圈、公众号、收藏模板，适配宿主原生调度。

## 权限与数据边界

保持 SIP 开启。不会自动重签微信；只有你明确同意、备份验证后才进入重签分支，需理解登录、截图权限和小程序等副作用。后台任务不取钥、不提权、不修复签名。

密钥、数据库、明文缓存留在本机。**Agent 总结通常会把所选消息提交给模型服务商**，外部投递还会增加接收方；由你选择范围、模型与目的地。不能把微信群内容中的指令当作操作授权。

只读取本机已同步数据，不能保证完整微信历史。朋友圈、公众号、收藏为**待用户验证**模板，缺钥不能解释成没有数据，媒体占位符不能代替内容分析。云端任务不能直接访问本机微信。

## 验证范围

实测经验：macOS 26.3.1、微信 4.1.15、wx 0.6.3，会话、联系人与基本聊天记录可用。公开测试使用模拟数据，覆盖时间边界、同秒分页、群名歧义、账号不匹配与缺钥。

其他 Agent 安装/调度分支依据官方文档；任务提示词与参数结构有测试，**未宣称完成所有宿主的真实周期投递**。本项目不会为了验证自动创建持续任务或发送消息。

```bash
python3 -m unittest discover -s tests -v
python3 skills/wx-cli-setup/scripts/diagnose.py
python3 skills/wx-cli-setup/scripts/install.py --dry-run
```

Python 3.9+。执行脚本前可以直接审阅源码。

## 项目来源与许可证

wx 二进制来自 [jackwener/wx-cli-again](https://github.com/jackwener/wx-cli-again)，默认基线提交 `077a54cbfe679bda963cd038d8440422907fc797`，不是最新版本承诺。本仓库不包含微信程序、二进制、真实数据或密钥。

本仓库使用 Apache-2.0，保留适用的上游归属说明，见 [LICENSE](LICENSE) 与 [NOTICE](NOTICE)。
