param(
    [Parameter(Mandatory=$true)]
    [string]$ToWxid,

    [Parameter(Mandatory=$true)]
    [string]$Text,

    [string]$AppId = $env:GEWECHAT_APP_ID,
    [string]$ApiUrl = "http://127.0.0.1:2531/v2/api"
)

$ErrorActionPreference = "Stop"

py -3.10 -m gateway.adapters.gewechat_bridge send --api-url $ApiUrl --app-id $AppId --to $ToWxid --text $Text
