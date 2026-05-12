#Requires -Version 5.1
<#
.SYNOPSIS
  Aplica el flujo completo de base de datos Ferragro: esquema, triggers, parche FK historial, funciones CRUD y (opcional) seed.

.DESCRIPTION
  Orden de ejecución:
    1) init/001_schema.sql — tablas, tipos, índices, roles base
    2) init/002_audit_triggers.sql — auditoría de citas
    3) init/003_historial_id_actor_drop_fk.sql — quita FK antigua en HistorialCambios.IdActor (idempotente)
    4) init/004_franjas_citas.sql — franjas horarias permitidas para inicio de citas
    5) init/005_profile_photo.sql — tabla de URL de foto de perfil por credencial
    6) init/006_admin_events.sql — auditoría de acciones administrativas sobre perfiles
    7) init/007_nit_10_digits.sql — migración de NIT/IdProveedor a 10 dígitos
    8) init/009_franjas_por_fecha.sql — franjas especiales por fecha exacta
    9) init/010_drop_dias_permitidos_cita.sql — elimina tabla legacy no utilizada
    10) run-database-crud.ps1 — funciones PL/pgSQL en database-crud/
    11) seeds/003_seed_data.sql — solo con -Seed (TRUNCATE + datos de ejemplo; solo desarrollo)

.PARAMETER DatabaseUrl
  URI postgresql://... Si se omite, se usa DATABASE_URL del -EnvFile.

.PARAMETER EnvFile
  Ruta al .env (por defecto: .env en la raíz del repo).

.PARAMETER Seed
  Si se indica, ejecuta el seed después del CRUD (TRUNCATE + datos de ejemplo).

.EXAMPLE
  cd db; .\run-database-all.ps1

.EXAMPLE
  .\run-database-all.ps1 -Seed
#>
[CmdletBinding()]
param(
  [string] $DatabaseUrl = "",
  [string] $EnvFile = "",
  [switch] $Seed
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

$initSteps = @(
  @{ Label = "001_schema";          Rel = "init\001_schema.sql" },
  @{ Label = "002_audit_triggers"; Rel = "init\002_audit_triggers.sql" },
  @{ Label = "003_historial_patch"; Rel = "init\003_historial_id_actor_drop_fk.sql" },
  @{ Label = "004_franjas_citas"; Rel = "init\004_franjas_citas.sql" },
  @{ Label = "005_profile_photo"; Rel = "init\005_profile_photo.sql" },
  @{ Label = "006_admin_events"; Rel = "init\006_admin_events.sql" },
  @{ Label = "007_nit_10_digits"; Rel = "init\007_nit_10_digits.sql" },
  @{ Label = "009_franjas_por_fecha"; Rel = "init\009_franjas_por_fecha.sql" },
  @{ Label = "010_drop_dias_permitidos_cita"; Rel = "init\010_drop_dias_permitidos_cita.sql" },
  @{ Label = "011_auth_sessions_login_audit"; Rel = "init\011_auth_sessions_login_audit.sql" },
  @{ Label = "012_db_roles_template"; Rel = "init\012_db_roles_template.sql" }
)

$totalSteps = $initSteps.Count + 1
if ($Seed) { $totalSteps++ }

Write-Host "`n=== Ferragro: despliegue completo de base de datos ($totalSteps pasos) ===" -ForegroundColor Cyan
Write-Host "DATABASE_URL: $($DatabaseUrl -replace ':[^:@/]+@', ':****@')" -ForegroundColor DarkGray

$ix = 0
foreach ($s in $initSteps) {
  $ix++
  Write-Host "`n[$ix/$totalSteps] $($s.Label)" -ForegroundColor Green
  $path = Join-Path $DbFolder $s.Rel
  Invoke-FerragroSqlFile -DatabaseUrl $DatabaseUrl -PsqlExe $psqlExe -SqlPath $path -Label $s.Label
}

$ix++
Write-Host "`n[$ix/$totalSteps] database-crud (PL/pgSQL)" -ForegroundColor Green
$crudScript = Join-Path $DbFolder "run-database-crud.ps1"
& $crudScript -DatabaseUrl $DatabaseUrl -EnvFile $EnvFile
if ($LASTEXITCODE -ne 0) {
  throw "run-database-crud.ps1 terminó con código $LASTEXITCODE"
}

if ($Seed) {
  $ix++
  Write-Host "`n[$ix/$totalSteps] seeds/003_seed_data (TRUNCATE + datos demo)" -ForegroundColor Magenta
  $seedPath = Join-Path $DbFolder "seeds\003_seed_data.sql"
  Invoke-FerragroSqlFile -DatabaseUrl $DatabaseUrl -PsqlExe $psqlExe -SqlPath $seedPath -Label "003_seed_data"
}

Write-Host "`n=== Completado sin errores. ===" -ForegroundColor Green
exit 0
