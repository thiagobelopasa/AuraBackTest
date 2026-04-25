#Requires -Version 5.1
<#
    Build local do AuraBackTest (sem publicar).
    Gera instalador em /release/AuraBackTest-Setup-*.exe
#>
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host '[1/5] Backend — PyInstaller' -ForegroundColor Cyan
Push-Location backend
if (-not (Test-Path .venv)) {
    python -m venv .venv
}
& .\.venv\Scripts\python.exe -m pip install --upgrade pip --quiet
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt --quiet
& .\.venv\Scripts\python.exe -m pip install pyinstaller==6.11.0 --quiet
& .\.venv\Scripts\pyinstaller.exe AuraBackTestServer.spec --noconfirm --clean
Pop-Location

Write-Host '[2/5] Movendo backend dist' -ForegroundColor Cyan
if (Test-Path backend-dist) { Remove-Item -Recurse -Force backend-dist }
Move-Item backend/dist/AuraBackTestServer backend-dist

Write-Host '[3/5] Frontend — Vite build' -ForegroundColor Cyan
Push-Location frontend
npm ci
npm run build
Pop-Location

Write-Host '[4/5] Electron — npm install' -ForegroundColor Cyan
Push-Location electron
npm install
Write-Host '[5/5] Electron — builder (sem publish)' -ForegroundColor Cyan
npm run dist
Pop-Location

Write-Host "`nPronto. Instalador em: $root\release\" -ForegroundColor Green
Get-ChildItem -Path "$root\release" -Filter '*.exe' | Format-Table Name, Length
