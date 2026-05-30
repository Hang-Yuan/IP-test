param(
    [string]$FromUser = "wxid_friend",
    [string]$Text = "Gewechat callback test",
    [string]$GatewayUrl = "http://127.0.0.1:8791/webhook/gewechat"
)

$ErrorActionPreference = "Stop"

py -3.10 -m gateway.adapters.gewechat_bridge simulate-callback --gateway-url $GatewayUrl --to $FromUser --text $Text
