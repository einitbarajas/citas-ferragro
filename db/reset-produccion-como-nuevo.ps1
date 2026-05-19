#Requires -Version 5.1
<#
.SYNOPSIS
  Vacía la BD de producción (Render) y crea solo el Admin inicial.

.PARAMETER DatabaseUrl
  External Database URL de Render (ferragro-db → Connections).
  Si se omite, usa la variable de entorno RENDER_DATABASE_URL.

.EXAMPLE
  $env:RENDER_DATABASE_URL = "postgresql://ferragro:****@dpg-....render.com:5432/ferragro"
  .\reset-produccion-como-nuevo.ps1
#>
[CmdletBinding()]
param(
  [string] $DatabaseUrl = $env:RENDER_DATABASE_URL
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$DbFolder = $PSScriptRoot
. (Join-Path $DbFolder "PsqlDb.ps1")

if ([string]::IsNullOrWhiteSpace($DatabaseUrl)) {
  throw @"
Falta la URL de la base en Render.

1. Render → ferragro-db → Connections → External Database URL
2. En PowerShell:
   `$env:RENDER_DATABASE_URL = 'postgresql://...'
   .\reset-produccion-como-nuevo.ps1

O pega la URL en el panel PSQL de Render y ejecuta:
   db/scripts/reset-produccion-como-nuevo.sql
"@
}

$sqlFile = Join-Path $DbFolder "scripts\reset-produccion-como-nuevo.sql"
$psqlExe = Resolve-PsqlExecutable

Write-Host "`n=== Reset producción (como nuevo + Admin) ===" -ForegroundColor Magenta
Write-Host "ATENCIÓN: se borrarán TODOS los usuarios, proveedores y citas." -ForegroundColor Yellow
$confirm = Read-Host "Escribe SI para continuar"
if ($confirm -ne 'SI') {
  Write-Host "Cancelado." -ForegroundColor DarkGray
  exit 0
}

Write-Host "DATABASE: $($DatabaseUrl -replace ':[^:@/]+@', ':****@')" -ForegroundColor DarkGray
& $psqlExe $DatabaseUrl -v ON_ERROR_STOP=1 -f $sqlFile
if ($LASTEXITCODE -ne 0) {
  throw "reset-produccion terminó con código $LASTEXITCODE"
}

Write-Host "`n=== Base lista (solo 1 Admin) ===" -ForegroundColor Green
Write-Host "Portal: https://frontend-ferragro.vercel.app" -ForegroundColor DarkGray
Write-Host "  Correo:     ebarajas@ferragro.com"
Write-Host "  Contraseña: FerragroPortal2026!"
Write-Host "  Documento:  90000001"
Write-Host "`nRecuperación de clave: sí (correo real en Outlook/SMTP de Render)." -ForegroundColor DarkGray
