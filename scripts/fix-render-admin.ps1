#Requires -Version 5.1
<#
  Corrige el Admin en la BD de Render (correo + contraseña + quita bloqueos).
  Uso:
    .\scripts\fix-render-admin.ps1
  Te pedirá pegar la External Database URL (Render → ferragro-db → Connections).
#>
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $RepoRoot "backend"
$Python = Join-Path $Backend ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    $Python = "python"
}

$url = $env:RENDER_DATABASE_URL
if ([string]::IsNullOrWhiteSpace($url)) {
    Write-Host "`nPega la External Database URL de Render (ferragro-db → Connections):" -ForegroundColor Cyan
    $url = Read-Host
}

if ([string]::IsNullOrWhiteSpace($url)) {
    throw "Falta DATABASE_URL."
}

$env:DATABASE_URL = $url.Trim()
$env:ENVIRONMENT = "production"

Write-Host "`nCorrigiendo Admin en Render..." -ForegroundColor Yellow
Push-Location $Backend
try {
    & $Python scripts/fix_production_admin.py
    if ($LASTEXITCODE -ne 0) { throw "fix_production_admin terminó con código $LASTEXITCODE" }
} finally {
    Pop-Location
}

Write-Host "`nPrueba en: https://frontend-ferragro.vercel.app" -ForegroundColor Green
