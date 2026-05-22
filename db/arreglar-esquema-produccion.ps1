#Requires -Version 5.1
<#
  Aplica en la BD de Render las migraciones que faltan (014-022) + funciones CRUD.
  Corrige: "column Citas.IdBodega does not exist" y rol AdminBodega.

  Uso (desde carpeta db):
    .\arreglar-esquema-produccion.ps1

  O con URL ya definida:
    $env:DATABASE_URL = "postgresql://...@....render.com/ferragro"
    .\arreglar-esquema-produccion.ps1

  URL: Render -> ferragro-db -> Connections -> External Database URL
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
  Write-Host ""
  Write-Host "Pega la External Database URL de Render (ferragro-db -> Connections):" -ForegroundColor Cyan
  $DatabaseUrl = Read-Host "DATABASE_URL"
}
if ([string]::IsNullOrWhiteSpace($DatabaseUrl)) {
  throw "Falta DATABASE_URL"
}

$env:DATABASE_URL = $DatabaseUrl.Trim()
$psqlExe = Resolve-PsqlExecutable

$migrations = @(
  "014_bodegas_franjas_flexibles.sql",
  "015_performance_indexes.sql",
  "016_equipos_descarga.sql",
  "017_equipos_descarga_entidades.sql",
  "018_franjas_unique_por_equipo.sql",
  "019_franjas_semanales_unique_por_equipo.sql",
  "020_admin_bodega.sql",
  "021_equipos_descarga_integridad.sql",
  "022_fix_proveedor_ci_email.sql"
)

Write-Host ""
Write-Host "=== Migraciones produccion Render (014-022) ===" -ForegroundColor Cyan
Write-Host "NO usa -Seed: no borra datos de citas/proveedores." -ForegroundColor DarkGray
Write-Host ""

$ix = 0
foreach ($file in $migrations) {
  $ix++
  $path = Join-Path $DbFolder "init\$file"
  Write-Host "[$ix/$($migrations.Count)] $file" -ForegroundColor Green
  Invoke-FerragroSqlFile -DatabaseUrl $env:DATABASE_URL -PsqlExe $psqlExe -SqlPath $path -Label $file
}

Write-Host ""
Write-Host "[CRUD] run-database-crud.ps1" -ForegroundColor Green
& (Join-Path $DbFolder "run-database-crud.ps1") -DatabaseUrl $env:DATABASE_URL
if ($LASTEXITCODE -ne 0) {
  throw "run-database-crud fallo con codigo $LASTEXITCODE"
}

Write-Host ""
Write-Host "=== Esquema actualizado ===" -ForegroundColor Green
Write-Host "1. Cierra sesion en https://frontend-ferragro.vercel.app"
Write-Host "2. Ctrl+F5 y vuelve a entrar"
Write-Host "3. Equipo -> debe salir Administrador de bodega"
Write-Host ""
Write-Host "Si quieres guardar la URL: copiala a $localEnv como RENDER_DATABASE_URL=..." -ForegroundColor DarkGray

if (-not (Test-Path $localEnv)) {
  $save = Read-Host "Guardar URL en .env.render.local? (s/n)"
  if ($save -match '^[sSyY]') {
    @("# No subir a git", "RENDER_DATABASE_URL=$($env:DATABASE_URL)") | Set-Content $localEnv -Encoding UTF8
  }
}

exit 0
