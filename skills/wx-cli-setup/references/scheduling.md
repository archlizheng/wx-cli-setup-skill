# 定时任务配置

## 通用步骤

先收集任务类型、账号/群聊/数据源、查询窗口、频率、时区、输出位置。默认用当前系统时区，用户选择北京时间时为 Asia/Shanghai；提示词脚本的默认示例时区为 Asia/Shanghai，Agent 必须把实际确定的时区显式传入。默认输出当前 Agent 或本机，远程投递需明确授权。

先读取宿主当前任务列表，按任务意图和范围找已有任务；匹配则更新，不重复创建。只检查用户授权的数据源，不默认监控所有私聊。对必要查询手动预检，不为了测试自动向微信或其他平台发消息。

通过 `scripts/job_prompt.py` 生成完整提示词后，补齐实际 wx/Python/状态路径、数据源范围和输出位置。生成器不创建任务，也不证明用户已授权模板里的投递位置。群名有歧义时先确认精确群 ID。每次运行冻结当前时间，读取过去指定窗口；机器休眠期间可能漏运行，不声称自动补齐。需要无遗漏增量追踪时另行设计有持久游标的方案，首版不提供该承诺。

权限修复、取钥、重签都在人工作业中完成，不进入后台提示词。缺钥或查询不完整必须报告，不能按“零消息”静默处理。关键词未命中、没有新内容时不发常规通知。模型调用可能产生费用并把选定内容发给模型服务商，用户需理解数据范围。

## Hermes

优先原生 `cronjob_manage`，以运行时 schema 为准。当前 0.21.6 示例字段：

```json
{"action":"create","name":"微信群摘要","schedule":"every 1h","prompt":"这里放完整生成的提示词","skill":"wx-cli-setup","workdir":"实际 wx 状态目录绝对路径","deliver":"local"}
```

`deliver=local` 仅本机保存；在聊天里用户明确要求回当前聊天时使用来源投递，不猜 chat_id，也不默认 all。执行前检查网关或 scheduler 运行，实际命令 `hermes cron status` / `hermes cron list` 以 `--help` 确认为准。cron 在全新会话运行，最终回复才是输出，不能依赖创建任务时的对话。

仅用户要求时 pin 模型，不修改全局模型。版本支持时先创建 paused 任务，检查任务 ID、next run、workdir、投递目标；本机预检完成后按授权启用。测试发送必须限定用户授权目的地；无法测试的投递标注未验证。记录执行状态和 delivery 状态，执行成功不等于投递成功。暂停/更新/删除先 list 获取真实 ID。

资料：[Hermes cron](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/cron.md)。

## Codex

使用宿主提供的 automation_update 或定时任务 UI；先发现工具 schema，不编辑 automation.toml 模拟创建成功。默认当前聊天的 heartbeat；只有用户要求每次新任务或独立工作才用本机 cron，并选择真实项目。配置必须运行在可访问 wx 数据的同一台 Mac，不能用云端环境读本机数据。

自然语言提示描述时间和动作；原生工具内部可构造调度规则，不向用户展示生硬 RRULE。保留现有模型与通知偏好。明确调用本技能与绝对脚本路径，不依赖自动选技能。

资料：[官方定时任务](https://learn.chatgpt.com/docs/automations)。

## Claude Code

`/loop`、CronCreate/CronList/CronDelete 是会话内任务，要提示用户会话生命周期、过期和触发延迟，不把它当常驻服务。长期读取本机微信优先 Claude Code Desktop 的本地 scheduled task；云端 routine 无法访问本机数据库。按当前 UI/工具能力创建，不假造不存在的 API。

资料：[官方调度](https://code.claude.com/docs/en/scheduled-tasks)。

## OpenClaw

使用当前网关原生 cron/automations 工具，或经过 `openclaw automations --help` / `openclaw cron --help` 确认的 CLI。校验网关实际运行于该 Mac，工作目录、账号与工具权限正确。持久独立任务使用 isolated session、完整提示词。通过本机版本支持的 delivery 配置投递到明确授权的位置；没有授权则本机或当前 Agent 结果。

资料：[官方 automations](https://docs.openclaw.ai/automation/cron-jobs)。

## 验收

记录任务 ID、频率、时区、下一次触发时间、运行宿主、输出位置。查询预检成功 → 创建证据 → 手动运行或观察一次原生执行 → 检查结果 → 在明确授权范围验证投递。不能测试时分开标注“参数验证”和“真实运行待验证”，不得写成完全成功。

本项目验证提示词生成与参数构造，没有实际创建持续任务或向外投递。不要把支持文档当作所有宿主端到端实测。
