param(
    [string]$Account = $env:WECHAT_ACCOUNT_WXID,
    [string]$DbRoot = "",
    [int]$Seconds = 0,
    [double]$Interval = 3,
    [switch]$Push,
    [switch]$AutoSend,
    [switch]$IncludeExisting,
    [switch]$KeepFiles,
    [string[]]$AllowUser = @(),
    [string[]]$AllowDisplay = @()
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
Set-Location $ProjectRoot

$arguments = @(
    "-m", "gateway.adapters.wechat_db_monitor",
    "watch",
    "--account", $Account,
    "--interval", "$Interval"
)

if ($DbRoot) {
    $arguments += @("--db-root", $DbRoot)
}
if ($Seconds -gt 0) {
    $arguments += @("--seconds", "$Seconds")
}
if ($Push) {
    $arguments += "--push"
}
if ($AutoSend) {
    $arguments += "--auto-send"
}
if ($IncludeExisting) {
    $arguments += "--include-existing"
}
if ($KeepFiles) {
    $arguments += "--keep-files"
}
foreach ($item in $AllowUser) {
    if (-not [string]::IsNullOrWhiteSpace($item)) {
        $arguments += @("--allow-user", $item)
    }
}
foreach ($item in $AllowDisplay) {
    if (-not [string]::IsNullOrWhiteSpace($item)) {
        $arguments += @("--allow-display", $item)
    }
}

python @arguments
