# Cria um atalho "AuraBackTest" na Área de Trabalho que roda o .bat
# Uso: botão direito -> Executar com PowerShell

$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$batFile     = Join-Path $projectRoot 'AuraBackTest.bat'
$desktop     = [Environment]::GetFolderPath('Desktop')
$shortcut    = Join-Path $desktop 'AuraBackTest.lnk'

# Usa ícone embutido do Windows (gráfico de barras do shell32)
$iconSource  = "$env:SystemRoot\System32\shell32.dll,13"

$wsh = New-Object -ComObject WScript.Shell
$sc  = $wsh.CreateShortcut($shortcut)
$sc.TargetPath       = $batFile
$sc.WorkingDirectory = $projectRoot
$sc.Description      = 'AuraBackTest - backtesting MQL5 + analytics'
$sc.IconLocation     = $iconSource
$sc.WindowStyle      = 1
$sc.Save()

Write-Host ""
Write-Host "Atalho criado: $shortcut" -ForegroundColor Green
Write-Host "Clique duas vezes no icone AuraBackTest na Area de Trabalho para abrir o app."
Write-Host ""
