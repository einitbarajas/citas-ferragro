#Requires -Version 5.1
<#
.SYNOPSIS
  Prepara PostgreSQL para pytest con BD (mismo contenido que ci-prepare-database.sh).

.EXAMPLE
  cd db
  .\ci-prepare-database.ps1
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
Write-Host "`n=== Ferragro CI: init scripts ===" -ForegroundColor Cyan

Get-ChildItem (Join-Path $DbFolder "init") -Filter "*.sql" | Sort-Object Name | ForEach-Object {
  Invoke-FerragroSqlFile -DatabaseUrl $DatabaseUrl -PsqlExe $psqlExe -SqlPath $_.FullName -Label $_.Name
}

Write-Host "`n=== Ferragro CI: database-crud ===" -ForegroundColor Cyan
& (Join-Path $DbFolder "run-database-crud.ps1") -DatabaseUrl $DatabaseUrl

Write-Host "`n=== Ferragro CI: fixtures ===" -ForegroundColor Cyan
Invoke-FerragroSqlFile -DatabaseUrl $DatabaseUrl -PsqlExe $psqlExe `
  -SqlPath (Join-Path $DbFolder "ci\fixtures_for_tests.sql") -Label "fixtures_for_tests"

Write-Host "`n=== Base lista para pruebas con BD ===" -ForegroundColor Green
