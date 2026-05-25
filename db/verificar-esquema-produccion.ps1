#Requires -Version 5.1
<#
  Comprueba que la BD de Render tiene las columnas que el API espera.
  No modifica datos.

  Uso (desde db):
    .\verificar-esquema-produccion.ps1
#>
[CmdletBinding()]
param([string] $DatabaseUrl = "")

$ErrorActionPreference = "Stop"
$DbFolder = $PSScriptRoot
$RepoRoot = Split-Path -Parent $DbFolder
. (Join-Path $DbFolder "PsqlDb.ps1")

$localEnv = Join-Path $RepoRoot ".env.render.local"
if ([string]::IsNullOrWhiteSpace($DatabaseUrl)) {
  $DatabaseUrl = $env:DATABASE_URL
}
if ([string]::IsNullOrWhiteSpace($DatabaseUrl) -and (Test-Path $localEnv)) {
  foreach ($line in Get-Content $localEnv -Encoding UTF8) {
    if ($line -match '^\s*(RENDER_DATABASE_URL|DATABASE_URL)\s*=\s*(.+)\s*$') {
      $DatabaseUrl = $Matches[2].Trim().Trim('"').Trim("'")
      break
    }
  }
}
if ([string]::IsNullOrWhiteSpace($DatabaseUrl)) {
  Write-Host "Pega la External Database URL de Render (ferragro-db -> Connections):" -ForegroundColor Cyan
  $DatabaseUrl = Read-Host "DATABASE_URL"
}
if ([string]::IsNullOrWhiteSpace($DatabaseUrl)) {
  throw "Falta DATABASE_URL"
}

$sql = Join-Path $DbFolder "scripts\verificar-esquema-produccion.sql"
$psqlExe = Resolve-PsqlExecutable
Write-Host ""
Write-Host "=== Verificacion esquema produccion ===" -ForegroundColor Cyan
& $psqlExe $DatabaseUrl.Trim() -v ON_ERROR_STOP=1 -f $sql
if ($LASTEXITCODE -ne 0) {
  throw "verificar-esquema fallo con codigo $LASTEXITCODE"
}
Write-Host ""
Write-Host "Si todas las columnas dicen OK y citas_join_ok > 0, el esquema esta bien." -ForegroundColor Green
Write-Host "Si el portal sigue con error: cierra sesion, Ctrl+F5, y revisa logs de ferragro-api (no ferragro-db)." -ForegroundColor DarkGray
