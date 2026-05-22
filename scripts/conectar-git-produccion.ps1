#Requires -Version 5.1
<#
  Abre los paneles de Vercel y Render y muestra qué secretos/configurar en GitHub.
  Uso: .\scripts\conectar-git-produccion.ps1
#>
$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$buildId = (Select-String -Path "backend\app\main.py" -Pattern '^API_BUILD_ID\s*=').Line
if ($buildId -match '"([^"]+)"') { $buildId = $Matches[1] } else { $buildId = "?" }

Write-Host ""
Write-Host "=== Enlazar GitHub con Vercel y Render ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Commit local:" (git log -1 --oneline) -ForegroundColor DarkGray
Write-Host "API_BUILD_ID esperado en /health:" $buildId -ForegroundColor DarkGray
Write-Host ""

Write-Host "VERCEL (elige una opcion)" -ForegroundColor Yellow
Write-Host "  A) Panel: Connect Git Repository, rama main, Root Directory = frontend"
Write-Host "     https://vercel.com/ferragro/frontend/settings/git"
Write-Host "  B) GitHub Actions: secreto VERCEL_TOKEN"
Write-Host "     https://github.com/einitbarajas/citas-ferragro/settings/secrets/actions"
Write-Host "     Token: https://vercel.com/account/tokens"
Write-Host ""

Write-Host "RENDER" -ForegroundColor Yellow
Write-Host "  1) Settings -> Build & Deploy: repo citas-ferragro, branch main, root backend, Auto-Deploy ON"
Write-Host "  2) Deploy Hook -> secreto GitHub RENDER_DEPLOY_HOOK"
Write-Host "  3) Manual Deploy -> Deploy latest commit (si Events muestra commit viejo 10fe606)"
Write-Host "     https://dashboard.render.com/web/srv-d82dvanaqgkc739362u0"
Write-Host ""

Write-Host "Documentacion completa: docs\CONECTAR_GIT_VERCEL_RENDER.md" -ForegroundColor Green
Write-Host ""

$open = Read-Host "Abrir paneles Vercel y Render en el navegador? (s/n)"
if ($open -eq "s") {
    Start-Process "https://vercel.com/ferragro/frontend/settings/git"
    Start-Process "https://github.com/einitbarajas/citas-ferragro/settings/secrets/actions"
    Start-Process "https://dashboard.render.com/web/srv-d82dvanaqgkc739362u0"
}
