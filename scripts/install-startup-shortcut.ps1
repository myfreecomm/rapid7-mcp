$startupDir = [Environment]::GetFolderPath('Startup')
$shortcutPath = Join-Path $startupDir 'Rapid7MCPServer.lnk'
$vbsPath = 'D:\Repos\rapid7-mcp\scripts\start-server-hidden.vbs'

$wsh = New-Object -ComObject WScript.Shell
$shortcut = $wsh.CreateShortcut($shortcutPath)
$shortcut.TargetPath = 'wscript.exe'
$shortcut.Arguments = "`"$vbsPath`""
$shortcut.WorkingDirectory = 'D:\Repos\rapid7-mcp\scripts'
$shortcut.Description = 'Inicia o servidor rapid7-mcp (uvicorn, porta 8000) em segundo plano'
$shortcut.Save()

if (Test-Path $shortcutPath) {
    Write-Host "OK: atalho criado em $shortcutPath"
} else {
    Write-Host "FALHOU: atalho nao foi criado"
}
