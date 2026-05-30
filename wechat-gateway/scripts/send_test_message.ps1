param(
    [string]$Text = "郭老师，我现在想做一个自己的AI分身，第一步到底应该先做什么？",
    [string]$FromUser = "demo-user"
)

$ErrorActionPreference = "Stop"

$body = @{
    from_user = $FromUser
    text = $Text
} | ConvertTo-Json

Invoke-RestMethod `
    -Method Post `
    -Uri "http://127.0.0.1:8791/webhook/manual" `
    -ContentType "application/json; charset=utf-8" `
    -Body $body
