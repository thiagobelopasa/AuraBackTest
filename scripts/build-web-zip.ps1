#Requires -Version 5.1
<#
    Empacota uma versao "web" do AuraBackTest pra entregar pra QA.
    Gera release/AuraBackTest-Web-<versao>.zip contendo:
      - backend/ (sem .venv nem __pycache__)
      - frontend/dist/ (ja buildado)
      - mql5_include/
      - AuraBackTest-Web.bat (launcher so-Python)
      - LEIA-ME.txt

    Amigo que receber so precisa:
      - Python 3.11+
      - MT5 instalado
      - Rodar o .bat
#>
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$version = (Get-Content "$root\electron\package.json" -Raw | ConvertFrom-Json).version
$zipName = "AuraBackTest-Web-$version.zip"
$outDir = "$root\release"
$stageDir = "$outDir\_stage"
$zipPath = "$outDir\$zipName"

Write-Host "[1/4] Rebuilding frontend..." -ForegroundColor Cyan
Push-Location "$root\frontend"
npm run build | Out-Null
Pop-Location

if (-not (Test-Path "$root\frontend\dist\index.html")) {
    Write-Error "frontend/dist/index.html nao foi gerado pelo build."
    exit 1
}

Write-Host "[2/4] Staging files..." -ForegroundColor Cyan
if (Test-Path $stageDir) { Remove-Item -Recurse -Force $stageDir }
New-Item -ItemType Directory -Path $stageDir | Out-Null

# Backend (sem venv, cache, DB) — mas mantém tests/ pro amigo rodar QA
robocopy "$root\backend" "$stageDir\backend" /E /XD .venv __pycache__ dist build data /XF *.pyc aurabacktest.db | Out-Null

# Frontend dist
robocopy "$root\frontend" "$stageDir\frontend" dist /E | Out-Null
# Cria package.json vazio em frontend pra manter estrutura esperada pelo main.py
# (na verdade main.py ja procura frontend/dist — nao precisa)

# MQL5 include
Copy-Item -Recurse "$root\mql5_include" "$stageDir\mql5_include"

# Launcher + readme
Copy-Item "$root\AuraBackTest-Web.bat" $stageDir
Copy-Item "$root\LEIA-ME.txt" $stageDir

Write-Host "[3/4] Creating zip..." -ForegroundColor Cyan
if (Test-Path $zipPath) { Remove-Item -Force $zipPath }
Compress-Archive -Path "$stageDir\*" -DestinationPath $zipPath -CompressionLevel Optimal

Write-Host "[4/4] Cleanup..." -ForegroundColor Cyan
Remove-Item -Recurse -Force $stageDir

$size = [math]::Round((Get-Item $zipPath).Length / 1MB, 1)
Write-Host ""
Write-Host "Pronto: $zipPath ($size MB)" -ForegroundColor Green
Write-Host ""
Write-Host "Instrucoes pro amigo que recebe o zip:" -ForegroundColor Yellow
Write-Host "  1. Extrair em qualquer pasta"
Write-Host "  2. Duplo-clique em AuraBackTest-Web.bat"
Write-Host "  3. Aguardar primeira execucao (instala deps Python)"
Write-Host "  4. Navegador abre em http://localhost:8000/app"
