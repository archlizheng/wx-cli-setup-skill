# 通用微信任务模板

这些模板由 Agent 按用户范围、宿主原生 schema 创建任务，不是可直接执行的系统 crontab。`job_prompt.py` 只渲染提示词，不会创建、发送或修改任务。

## 生成方式

```bash
python3 scripts/job_prompt.py --kind group-summary --chat '用户指定群' --minutes 60 --timezone Asia/Shanghai
python3 scripts/job_prompt.py --kind keyword --chat '用户指定群' --keywords 发布 会议 --minutes 60 --timezone Asia/Shanghai
python3 scripts/job_prompt.py --kind unread --timezone Asia/Shanghai
python3 scripts/job_prompt.py --kind sns --minutes 1440 --timezone Asia/Shanghai
python3 scripts/job_prompt.py --kind articles --minutes 1440 --timezone Asia/Shanghai
python3 scripts/job_prompt.py --kind favorites --timezone Asia/Shanghai
```

`--destination` 是用户已经明确同意的目的地描述，默认本机/当前 Agent；生成该字段不授予发送权限。渲染结果含技能绝对路径，因此在目标用户的机器渲染，不能把开发者机器渲染的提示词直接发布。

| 类型 | 输出重点 | 实际数据范围与限制 |
|---|---|---|
| group-summary | 主题、结论、待办、资源、时间 | 固定窗口、指定群；分页并保留 coverage |
| keyword | 关键词、时间、最小必要上下文 | 只扫描授权聊天窗口；未命中不提醒 |
| unread | 待处理会话、优先级 | 执行时快照，不是过去窗口新增未读；按用户授权名单筛选 |
| sns | 动态主题、值得关注的信息 | **未实测**；需 sns 密钥，仅本地刷到的缓存 |
| articles | 推送标题、摘要、原链接 | **未实测**；需 biz_message 密钥；不默认联网读取正文 |
| favorites | 主题归类、链接与待处理内容 | **未实测**；需 favorite 密钥；不支持增量参数时按快照报告 |

## 聊天查询接口

`query_window.py --chat NAME_OR_ID`，使用 `--minutes N` 或成对 `--since ISO --until ISO`，不能混用。`--timezone` 为 IANA 时区，日期含显式时差时尊重时差；DST 歧义墙钟时间要求显式时差。`--wx` / `--state-dir` 可显式指定绝对路径，`--max-messages` 默认 10000，达到上限报告截断。

结果是 JSON，包含 `chat_id`、`window`、`count`、`messages`、`coverage` 与 `account_match`。窗口为 [start,end)，固定边界后用 offset 分页，避免同秒多消息被严格时间游标丢失。群名查找先 contacts 再 sessions，不读取其他群的消息。歧义或查询失败退出码 2；候选需要用户指定精确群 ID。

`coverage.scope=local_synced_data_only` 始终存在。unknown_shards、possibly_stale、截断必须保留；空窗口只表示本地没读到，不能证明群里没聊。query_source_unavailable 是来源/分片不可用，不能当作空窗口。视频、图片、语音只能标注未解析，不凭聊天调侃确认真实事件。
