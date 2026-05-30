param(
    [Parameter(Mandatory=$true)]
    [string]$FromUser,

    [Parameter(Mandatory=$true)]
    [string]$Text,

    [string]$ReplyTarget = "",
    [string]$Source = "manual-event",
    [switch]$AutoSend,
    [string]$GatewayUrl = "http://127.0.0.1:8791/wechat/inbound"
)

$ErrorActionPreference = "Stop"

$payload = @{
    from_user = $FromUser
    text = $Text
    source = $Source
    auto_send = [bool]$AutoSend
}

if (-not [string]::IsNullOrWhiteSpace($ReplyTarget)) {
    $payload.reply_target = $ReplyTarget
}

Invoke-RestMethod `
    -Uri $GatewayUrl `
    -Method Post `
    -ContentType "application/json; charset=utf-8" `
    -Body ($payload | ConvertTo-Json -Compress)
