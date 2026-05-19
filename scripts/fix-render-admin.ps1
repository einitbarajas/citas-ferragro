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

$localEnv = Join-Path $RepoRoot ".env.render.local"
$url = $env:RENDER_DATABASE_URL
if ([string]::IsNullOrWhiteSpace($url) -and (Test-Path -LiteralPath $localEnv)) {
    foreach ($line in Get-Content -LiteralPath $localEnv -Encoding UTF8) {
        if ($line -match '^\s*RENDER_DATABASE_URL\s*=\s*(.+)\s*$') {
            $url = $Matches[1].Trim().Trim([char]0x22).Trim("'")
            break
        }
        if ($line -match '^\s*DATABASE_URL\s*=\s*(.+)\s*$' -and $line -match 'render\.com') {
            $url = $Matches[1].Trim().Trim([char]0x22).Trim("'")
            break
        }
    }
}
if ([string]::IsNullOrWhiteSpace($url)) {
    Write-Host "`nCrea el archivo .env.render.local en la raíz del repo con:" -ForegroundColor Yellow
    Write-Host '  RENDER_DATABASE_URL=postgresql://ferragro:...@dpg-....oregon-postgres.render.com:5432/ferragro' -ForegroundColor DarkGray
    Write-Host "(Render → ferragro-db → Connections → External Database URL)`n" -ForegroundColor DarkGray
    Write-Host "O pégala ahora:" -ForegroundColor Cyan
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
