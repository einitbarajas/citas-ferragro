#Requires -Version 5.1
<#
  Arregla login en producción (misma acción que ENTRAR-AHORA.sql).
  Uso desde la carpeta db:
    .\ejecutar-ENTRAR-AHORA.ps1

  Necesita la External Database URL de Render (ferragro-db → Connections).
  Guárdala en ..\ .env.render.local o pégala cuando lo pida.
#>
$ErrorActionPreference = "Stop"
$DbFolder = $PSScriptRoot
$RepoRoot = Split-Path -Parent $DbFolder
. (Join-Path $DbFolder "PsqlDb.ps1")

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
    Write-Host ""
    Write-Host "Pega la External Database URL de Render (ferragro-db -> Connections):" -ForegroundColor Cyan
    Write-Host "Ejemplo: postgresql://ferragro:****@dpg-....oregon-postgres.render.com:5432/ferragro" -ForegroundColor DarkGray
    $url = Read-Host "URL"
}

if ([string]::IsNullOrWhiteSpace($url)) {
    throw "Falta la URL de la base de datos."
}

if ($url -notmatch 'render\.com') {
    Write-Host "ADVERTENCIA: la URL no parece ser de Render." -ForegroundColor Yellow
}

$env:DATABASE_URL = $url.Trim()
$env:ENVIRONMENT = "production"
$env:RENDER_DATABASE_URL = $env:DATABASE_URL

$sqlFile = Join-Path $DbFolder "scripts\ENTRAR-AHORA.sql"
$python = Join-Path $RepoRoot "backend\.venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    $python = "python"
}

Write-Host "`n=== Arreglando admin en produccion ===" -ForegroundColor Cyan

try {
    $psql = Resolve-PsqlExecutable
    Write-Host "Ejecutando SQL con psql..." -ForegroundColor DarkGray
    & $psql $env:DATABASE_URL -v ON_ERROR_STOP=1 -f $sqlFile
    if ($LASTEXITCODE -ne 0) { throw "psql termino con codigo $LASTEXITCODE" }
} catch {
    Write-Host "psql no disponible o fallo; usando Python..." -ForegroundColor Yellow
    Push-Location (Join-Path $RepoRoot "backend")
    try {
        & $python scripts/fix_production_admin.py
        if ($LASTEXITCODE -ne 0) { throw "fix_production_admin termino con codigo $LASTEXITCODE" }
    } finally {
        Pop-Location
    }
}

Write-Host "`n=== Listo ===" -ForegroundColor Green
Write-Host "Portal: https://frontend-ferragro.vercel.app"
Write-Host "  Correo:     ebarajas@ferragro.com"
Write-Host "  Contrasena: FerragroPortal2026!"
Write-Host ""
Write-Host "Render API: haz Manual Deploy -> Deploy latest commit si /health sigue en build 2026-05-15" -ForegroundColor DarkGray

# Guardar URL para la proxima vez (no se sube a git)
if (-not (Test-Path -LiteralPath $localEnv)) {
    $save = Read-Host "Guardar URL en .env.render.local para la proxima vez? (s/n)"
    if ($save -match '^[sSyY]') {
        @(
            "# No subir a GitHub"
            "RENDER_DATABASE_URL=$($env:DATABASE_URL)"
        ) | Set-Content -LiteralPath $localEnv -Encoding UTF8
        Write-Host "Guardado en .env.render.local" -ForegroundColor DarkGray
    }
}
