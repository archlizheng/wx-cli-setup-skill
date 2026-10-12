# macOS 安装与排错

## 1. 检查与安装

需要本机 macOS、微信 4.x、登录账号，以及可运行命令的 Agent。辅助脚本需要 Python 3.9+；可使用宿主已提供的解释器，缺少时由用户选择安装官方 Python 或 Homebrew Python。不覆盖系统 Python。

从技能目录运行 `python3 scripts/diagnose.py`。诊断保留 `wx doctor --json` 的项目名称与布尔状态，丢弃详情路径、密钥、聊天正文。账号核对用当前微信进程实际打开的 db_storage 目录；`unverifiable` 表示未能核对，不表示一致。

`python3 scripts/install.py --dry-run` 查看安装动作，再执行无 sudo 的安装。已有 wx 必须通过版本与 history 参数检查才复用。默认固定源码为 [jackwener/wx-cli-again](https://github.com/jackwener/wx-cli-again) 提交 `077a54cbfe679bda963cd038d8440422907fc797`（wx 0.6.3）。这是实测基线，不声称是最新版本；升级另行审查目标提交。

首次构建需要 Git/Xcode CLT（缺少时用户运行 `xcode-select --install`）。脚本从官方 rust-lang 下载 rustup-init 并核对 SHA256，在 `~/.local/share/wx-cli-setup/` 隔离 CARGO_HOME/RUSTUP_HOME，`cargo build --release --locked`。默认二进制 `~/.local/bin/wx`，记录版本、提交和文件摘要，不修改 shell profile。源码来源/提交有冲突或已有改动时停止，不 reset 用户目录；换一个 `--runtime-dir`。

`--build` 才明确重建，替换前备份旧二进制。Agent 先读取脚本、解释下载与执行来源，再按宿主权限流程运行。环境阻止终端或其他动作时，遵守限制，交给用户完成，不绕开权限。

## 2. 账号与配置

默认状态目录 `~/.wx-cli`。已有配置时先核对当前账号，不能仅凭“最近修改的目录”选择；匹配失败让用户确认账号。不要默默把已有配置切换到另一账号。

没有配置时，让用户先登录预期账号、打开所需聊天，再运行初始化。若自动检测选错目录，先备份配置，查阅该 wx 版本配置格式，在明确确认账号后修正 `db_dir` 并重新初始化；保留旧账号配置与密钥，不混合不同账号。

始终以状态目录作为命令 cwd；默认位置不存在时由首次配置流程 `mkdir -p ~/.wx-cli`，`chmod 700 ~/.wx-cli`。配置与密钥文件应为 0600；日常查询不读出或打印原始密钥。

## 3. 首次取钥与补钥（人工作业）

在本机 GUI Terminal 中执行，wx 不在 PATH 时替换为已验证的绝对二进制路径：

```bash
cd ~/.wx-cli
sudo "$HOME/.local/bin/wx" init --hook-seconds 60
```

用户在终端输入 Mac 管理员密码；Agent 不索取密码。等日志显示 LLDB 等待后切换微信、打开相关页面。微信保持运行并登录。捕获不足时保留已验证密钥，执行：

```bash
cd ~/.wx-cli
sudo "$HOME/.local/bin/wx" key extract --hook-seconds 90
```

对应操作：会话库切换聊天或给自己的文件传输助手发测试消息；搜索库使用微信搜索；公众号打开订阅号；收藏、朋友圈分别打开相应页面。没有触发加解密的冷库可能拿不到钥，延长等待不是必然解法。LLDB 到期超时终止的日志不等于整体失败，检查最终匹配与实际查询。

补钥后仍报无法解密，且 doctor 已显示对应库有钥：`wx daemon stop`，再重试查询自动启动。后台可能还保留旧密钥。不要因此直接重签或循环 init --force。

## 4. task_for_pid / kr=5

1. 确认本机 GUI Terminal + sudo；检查系统设置 → 隐私与安全性 → 开发者工具，并在用户开启权限后退出重开终端。
2. 用 `codesign -dv --verbose=4 /Applications/WeChat.app` 与 `codesign -d --entitlements - /Applications/WeChat.app` 查签名。
3. 有针对性读取日志，避免输出无关系统日志：

```bash
/usr/bin/log show --last 15m --style compact --predicate 'process == "kernel" AND eventMessage CONTAINS[c] "macOSTaskPolicy"'
```

日志明确指出目标 hardened 且缺 get-task-allow 时，不反复要求开发者权限。实测 macOS 26.3.1 + 微信 4.1.15 会遇到该限制。上游成功案例仅覆盖旧 macOS；不能泛化为“官方包一定能直接取钥”。[Apple 调试权限说明](https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.security.cs.debugger)

## 5. 仅在明确同意后重签

说明这会改变微信代码身份与 Runtime 保护，可能需重新登录/重新授权截图、相机、麦克风，影响公众号与小程序。微信更新可能覆盖签名。安装授权不能当作重签授权；SIP 保持开启。

先确认实际应用路径（不要误签挂载 DMG 内的副本），备份并验证官方签名：

```bash
umask 077
wx_backup="$HOME/.local/share/wx-cli-setup/backups/pre-resign-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$wx_backup"
ditto /Applications/WeChat.app "$wx_backup/WeChat.app"
codesign --verify --deep --strict "$wx_backup/WeChat.app"
```

正常退出微信，确认进程已停止。只有备份验证成功、用户明确同意，才执行：

```bash
codesign --force --deep --sign - /Applications/WeChat.app
codesign --verify --deep --strict /Applications/WeChat.app
codesign -dv --verbose=4 /Applications/WeChat.app
```

如果文件所有权需要 sudo，由用户在本机终端执行；不要扩大磁盘权限来强行操作。重新打开微信并让用户处理登录与系统提示，再手动取钥。失败时停止；不要盲目多次改签。

恢复：退出微信，把重签的 app 移到备份旁的独立隔离位置，确认目标不存在，再将官方备份 ditto 回原路径并验证签名；或者从微信官方网站重装官方包。不要删除微信数据容器。恢复后取钥能力可能再次受官方签名限制。

## 6. 验证与覆盖范围

`wx sessions --json -n 1`、`wx contacts --json -n 1` 验证基本通路；诊断脚本不显示内容。授权后再查文件传输助手或指定聊天的少量 history，并检查 meta。`windowed` 是有过滤窗口，不自动等于缺失；unknown_shards、possibly_stale 和达到消息上限必须报告。

必要密钥按用户功能判断，不要求所有数据库全齐，也不把 7/19 视作全功能成功。本地缓存不等于完整微信云端历史。公众号、朋友圈、收藏未在本项目实测，需用户自行尝试和验证。
