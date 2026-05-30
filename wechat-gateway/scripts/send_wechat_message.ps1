param(
    [Parameter(Mandatory=$true)]
    [string]$Target,

    [Parameter(Mandatory=$true)]
    [string]$Text,

    [ValidateSet("keyboard", "wx4py", "auto")]
    [string]$Driver = "keyboard",

    [string]$GatewayUrl = "http://127.0.0.1:8791/wechat/send"
)

$ErrorActionPreference = "Stop"

$payload = @{
    target = $Target
    text = $Text
    driver = $Driver
} | ConvertTo-Json -Compress

Invoke-RestMethod -Uri $GatewayUrl -Method Post -ContentType "application/json; charset=utf-8" -Body $payload
