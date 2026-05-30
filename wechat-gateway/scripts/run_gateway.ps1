param(
    [string[]]$AutoSendAllowTarget = @()
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if ([string]::IsNullOrWhiteSpace($env:WECHAT_AGENT_MODE)) {
    $env:WECHAT_AGENT_MODE = "mock"
}
if ($AutoSendAllowTarget.Count -gt 0) {
    $env:WECHAT_AUTO_SEND_ALLOW_TARGETS = ($AutoSendAllowTarget -join ",")
}
elseif ([string]::IsNullOrWhiteSpace($env:WECHAT_AUTO_SEND_ALLOW_TARGETS)) {
    $env:WECHAT_AUTO_SEND_ALLOW_TARGETS = ""
}

py -3.10 -m gateway.server --host 127.0.0.1 --port 8791
