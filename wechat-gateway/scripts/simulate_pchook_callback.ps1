param(
    [string]$FromUser = "filehelper",
    [string]$Text = "PC Hook callback test",
    [string]$GatewayUrl = "http://127.0.0.1:8791/webhook/pchook"
)

$ErrorActionPreference = "Stop"

py -3.10 -m gateway.adapters.pc_hook_bridge simulate-callback --gateway-url $GatewayUrl --to $FromUser --text $Text
