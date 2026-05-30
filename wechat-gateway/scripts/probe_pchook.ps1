param(
    [string]$ApiUrl = "http://127.0.0.1:8981/api"
)

$ErrorActionPreference = "Stop"

py -3.10 -m gateway.adapters.pc_hook_bridge probe --api-url $ApiUrl
