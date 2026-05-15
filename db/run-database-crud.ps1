#Requires -Version 5.1
<#
.SYNOPSIS
  Aplica todas las funciones PL/pgSQL bajo database-crud/.

.PARAMETER DatabaseUrl
  URI postgresql://... Si se omite, se usa DATABASE_URL del -EnvFile.

.PARAMETER EnvFile
  Ruta al .env (por defecto: .env en la raíz del repo).

.EXAMPLE
  cd db; .\run-database-crud.ps1
#>
[CmdletBinding()]
param(
  [string] $DatabaseUrl = "",
  [string] $EnvFile = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$DbFolder = $PSScriptRoot
$RepoRoot = Split-Path -Parent $DbFolder

. (Join-Path $DbFolder "PsqlDb.ps1")

if ([string]::IsNullOrWhiteSpace($EnvFile)) {
  $EnvFile = Join-Path $RepoRoot ".env"
}

if ([string]::IsNullOrWhiteSpace($DatabaseUrl)) {
  $DatabaseUrl = Read-DatabaseUrlFromEnv -Path $EnvFile
}

$psqlExe = Resolve-PsqlExecutable
$files = Get-ChildItem (Join-Path $DbFolder "database-crud") -Recurse -Filter "*.sql" | Sort-Object FullName

Write-Host "`n=== Ferragro: funciones CRUD (PL/pgSQL) ===" -ForegroundColor Cyan
Write-Host "DATABASE_URL: $($DatabaseUrl -replace ':[^:@/]+@', ':****@')" -ForegroundColor DarkGray

foreach ($file in $files) {
  Invoke-FerragroSqlFile -DatabaseUrl $DatabaseUrl -PsqlExe $psqlExe -SqlPath $file.FullName -Label $file.FullName
}

Write-Host "`n=== CRUD completado sin errores. ===" -ForegroundColor Green
