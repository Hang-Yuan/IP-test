# IP-test

郭洪斌 IP 微信文字呈现 demo：本地微信消息监听 -> 8791 gateway -> Codex 并行 sub-agent -> 郭洪斌 skill -> 单目标回发微信。

## 目录

```text
.
├─ skills/guo-hongbin/          # Codex skill 包：M2 主控 + C1/M3/M4/R1/语料
└─ wechat-gateway/              # 本地微信接入、路由、发送、测试脚本
```

没有提交运行时数据：`wechat-gateway/data/`、消息记录、二维码、截图、日志、本机微信缓存都被排除。

## 链路

```text
PC 微信本地数据库
  -> wechat_db_monitor.py 监听新消息
  -> POST http://127.0.0.1:8791/wechat/inbound
  -> gateway/server.py 单目标锁 + 防群发校验
  -> scripts/agent_codex_bridge.py
       1. 并行启动 C1 / M3 / M4 三个 Codex 子进程
       2. C1 读 sub_C1.md
       3. M3 读 sub_M3.md + R1/原始语料索引
       4. M4 读 sub_M4.md + R1/原始语料索引
       5. M2 读 _main.md + 三路意见后生成最终回复
  -> wechat_keyboard.py / wx4py_bridge.py 回发到本轮消息发送人
```

默认回复控制在 150 字以内；只有用户明确要求详细展开、方案、拆解、长回复或多步骤建议时才放开长度。

## 前置条件

- Windows
- Python 3.10+
- 已登录的 PC 微信测试号
- Codex CLI 已安装并登录
- 不建议直接用主号做测试

安装 Python 依赖：

```powershell
cd path\to\IP-test
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r .\wechat-gateway\requirements.txt
```

## 配置

最少需要两个值：

```powershell
$env:WECHAT_ACCOUNT_WXID = "wxid_your_test_account"
$env:WECHAT_CODEX_SKILL_PATH = "$PWD\skills\guo-hongbin\SKILL.md"
```

如果 `codex` 不在 PATH，额外设置：

```powershell
$env:CODEX_CLI = "C:\Users\you\AppData\Local\OpenAI\Codex\bin\codex.exe"
```

如果微信数据库无法自动发现，设置：

```powershell
$env:WECHAT_DB_ROOT = "C:\path\to\xwechat_files\wxid_your_test_account\db_storage"
```

可参考 `wechat-gateway/config.example.env`。

## 启动

开第一个终端，启动 gateway：

```powershell
cd path\to\IP-test\wechat-gateway
$env:WECHAT_ACCOUNT_WXID = "wxid_your_test_account"
.\scripts\run_gateway_agent.ps1 -Agent codex -Port 8791
```

开第二个终端，启动微信数据库监听和自动回发：

```powershell
cd path\to\IP-test\wechat-gateway
$env:WECHAT_ACCOUNT_WXID = "wxid_your_test_account"
$env:WECHAT_DB_MONITOR_PUSH_TIMEOUT = "900"
.\scripts\watch_wechat_inbox.ps1 -Push -AutoSend
```

现在让另一个微信号给这个测试号发消息。监听器会把新消息送到 8791，Codex 生成后只回到本轮发送人。

## 本地验证

健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8791/health
```

不触发真实微信发送的后端模拟：

```powershell
cd path\to\IP-test\wechat-gateway
.\scripts\simulate_inbound_message.ps1 -FromUser "smoke-test-user" -Text "校长您好，我想了解一下这个课程适不适合我"
```

测试防群发保护：

```powershell
cd path\to\IP-test\wechat-gateway
python -m unittest discover -s tests -v
```

## 关键环境变量

| 变量 | 说明 |
|---|---|
| `WECHAT_ACCOUNT_WXID` | 当前 PC 微信登录账号的 wxid |
| `WECHAT_DB_ROOT` | 可选，微信 `db_storage` 路径 |
| `WECHAT_AGENT_MODE` | 使用 `codex` |
| `WECHAT_AGENT_COMMAND` | 默认由启动脚本指向 `scripts/agent_codex_bridge.py` |
| `WECHAT_CODEX_SKILL_PATH` | `skills/guo-hongbin/SKILL.md` |
| `CODEX_CLI` | 可选，codex.exe 绝对路径 |
| `WECHAT_PARALLEL_SUB_AGENTS` | 默认 `1`，开启 C1/M3/M4 并行 |
| `WECHAT_AGENT_TIMEOUT` | 默认建议 `1800` |
| `WECHAT_SUB_AGENT_TIMEOUT` | 默认建议 `900` |
| `WECHAT_M2_TIMEOUT` | 默认建议 `900` |
| `WECHAT_SEND_DRIVER` | 默认建议 `keyboard` |
| `WECHAT_AUTO_SEND_ALLOW_TARGETS` | 可选白名单；为空时监听全部对话，但仍只回本轮 sender |
| `WECHAT_AUTO_SEND_BLOCK_TARGETS` | 可选黑名单，默认建议屏蔽文件传输助手等系统会话 |

## 安全边界

- 自动发送前会校验目标必须等于本轮入站 sender / room_id。
- 拒绝 `*`、`all`、多目标分隔符等群发目标。
- 同一个 inbound event 已经发送过时会阻断重复发送。
- 这个仓库不包含本机消息 JSONL、微信数据库、日志、二维码或账号缓存。
