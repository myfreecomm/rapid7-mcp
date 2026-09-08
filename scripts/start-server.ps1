$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $repoRoot 'logs'
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir | Out-Null
}

$logFile = Join-Path $logDir 'server.log'
$uv = 'C:\Users\lsgol\AppData\Local\Programs\Python\Python312\Scripts\uv.exe'

Set-Location $repoRoot

"$(Get-Date -Format o) starting rapid7-mcp server" | Out-File -FilePath $logFile -Append -Encoding utf8

& $uv run uvicorn rapid7_mcp.main:app --port 8000 *>> $logFile
