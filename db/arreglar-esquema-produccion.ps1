#Requires -Version 5.1
<#
  Aplica en la BD de Render las migraciones que faltan (013-023) + funciones CRUD.
  Corrige IdBodega, Proveedores.Estado, AdminBodega, etc.

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

$DatabaseUrl = Resolve-RenderDatabaseUrl -ExplicitUrl $DatabaseUrl -RepoRoot $RepoRoot
if (Test-PlaceholderDatabaseUrl $env:DATABASE_URL) {
  Write-Host "Ignorando DATABASE_URL de la sesion (parece ejemplo/placeholder). Usando .env.render.local si existe." -ForegroundColor Yellow
}
if ([string]::IsNullOrWhiteSpace($DatabaseUrl)) {
  Write-Host ""
  Write-Host "Pega la External Database URL de Render (ferragro-db -> Connections):" -ForegroundColor Cyan
  $DatabaseUrl = Read-Host "DATABASE_URL"
}
if ([string]::IsNullOrWhiteSpace($DatabaseUrl) -or (Test-PlaceholderDatabaseUrl $DatabaseUrl)) {
  throw "Falta DATABASE_URL valida. Guarda la External URL en .env.render.local como RENDER_DATABASE_URL=postgresql://..."
}

$env:DATABASE_URL = $DatabaseUrl.Trim()
$psqlExe = Resolve-PsqlExecutable

$migrations = @(
  "013_provider_account_status.sql",
  "014_bodegas_franjas_flexibles.sql",
  "015_performance_indexes.sql",
  "016_equipos_descarga.sql",
  "017_equipos_descarga_entidades.sql",
  "018_franjas_unique_por_equipo.sql",
  "019_franjas_semanales_unique_por_equipo.sql",
  "020_admin_bodega.sql",
  "021_equipos_descarga_integridad.sql",
  "022_fix_proveedor_ci_email.sql",
  "023_admin_bodega_usuario.sql"
)

Write-Host ""
Write-Host "=== Migraciones produccion Render (013-023) ===" -ForegroundColor Cyan
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

$python = Join-Path $RepoRoot "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }
Write-Host ""
Write-Host "[Usuario] ensure_admin_bodega_production.py" -ForegroundColor Green
Push-Location (Join-Path $RepoRoot "backend")
$env:PYTHONPATH = "."
& $python scripts\ensure_admin_bodega_production.py
$pyExit = $LASTEXITCODE
Pop-Location
if ($pyExit -ne 0) {
  Write-Host "Script Python fallo; el SQL 023 ya creo el usuario si psql OK." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== Esquema actualizado ===" -ForegroundColor Green
Write-Host "1. Cierra sesion en https://frontend-ferragro.vercel.app"
Write-Host "2. Ctrl+F5 y vuelve a entrar"
Write-Host "3. Equipo -> Administrador de bodega en el desplegable"
Write-Host "4. Login admin bodega: admin.bodega@ferragro.com / FerragroPortal2026!"
Write-Host ""
Write-Host "Si quieres guardar la URL: copiala a $localEnv como RENDER_DATABASE_URL=..." -ForegroundColor DarkGray

if (-not (Test-Path $localEnv)) {
  $save = Read-Host "Guardar URL en .env.render.local? (s/n)"
  if ($save -match '^[sSyY]') {
    @("# No subir a git", "RENDER_DATABASE_URL=$($env:DATABASE_URL)") | Set-Content $localEnv -Encoding UTF8
  }
}

exit 0
