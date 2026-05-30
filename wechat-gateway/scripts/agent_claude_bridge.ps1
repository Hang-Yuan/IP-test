param()

$ErrorActionPreference = "Stop"
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONUTF8 = "1"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
python "$ProjectRoot\scripts\agent_claude_bridge.py"
