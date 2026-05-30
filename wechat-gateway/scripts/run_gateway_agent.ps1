param(
    [ValidateSet("claude", "codex")]
    [string]$Agent = "claude",
    [int]$Port = 8791,
    [string[]]$AutoSendAllowTarget = @()
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
Set-Location $ProjectRoot

$env:WECHAT_AGENT_MODE = $Agent
$env:WECHAT_AGENT_TIMEOUT = if ($env:WECHAT_AGENT_TIMEOUT) { $env:WECHAT_AGENT_TIMEOUT } else { "900" }
$env:WECHAT_SUB_AGENT_TIMEOUT = if ($env:WECHAT_SUB_AGENT_TIMEOUT) { $env:WECHAT_SUB_AGENT_TIMEOUT } else { "360" }
$env:WECHAT_M2_TIMEOUT = if ($env:WECHAT_M2_TIMEOUT) { $env:WECHAT_M2_TIMEOUT } else { "360" }
$env:WECHAT_PARALLEL_SUB_AGENTS = if ($env:WECHAT_PARALLEL_SUB_AGENTS) { $env:WECHAT_PARALLEL_SUB_AGENTS } else { "1" }
$env:WECHAT_SEND_DRIVER = "keyboard"
$env:WECHAT_COMMAND_SEND_DRIVER = "keyboard"
$env:WECHAT_CODEX_SKILL_PATH = if ($env:WECHAT_CODEX_SKILL_PATH) { $env:WECHAT_CODEX_SKILL_PATH } else { "$ProjectRoot\..\skills\guo-hongbin\SKILL.md" }

if ($AutoSendAllowTarget.Count -gt 0) {
    $env:WECHAT_AUTO_SEND_ALLOW_TARGETS = ($AutoSendAllowTarget -join ",")
}
elseif ([string]::IsNullOrWhiteSpace($env:WECHAT_AUTO_SEND_ALLOW_TARGETS)) {
    $env:WECHAT_AUTO_SEND_ALLOW_TARGETS = ""
}

if ($Agent -eq "claude") {
    $env:WECHAT_AGENT_COMMAND = "python `"$ProjectRoot\scripts\agent_claude_bridge.py`""
}
else {
    $env:WECHAT_AGENT_COMMAND = "python `"$ProjectRoot\scripts\agent_codex_bridge.py`""
}

python -m gateway.server --host 127.0.0.1 --port $Port
