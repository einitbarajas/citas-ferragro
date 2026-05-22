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
    10) init/011_auth_sessions_login_audit.sql — sesiones refresh y auditoría de login
    11) init/012_db_roles_template.sql — plantilla de roles de BD (opcional)
    12) init/013_provider_account_status.sql — estado suspendido y purga programada de proveedores
    13) init/014_bodegas_franjas_flexibles.sql — bodegas y turnos explícitos por bodega
    14) init/015_performance_indexes.sql — índices de rendimiento en citas e historial
    15) init/016_equipos_descarga.sql — equipos de descarga en bodegas y proveedores
    16) init/020_admin_bodega.sql — rol AdminBodega y asignación por bodega
    17) init/021_equipos_descarga_integridad.sql — citas/franjas alineadas al muelle de su bodega
    18) init/023_admin_bodega_usuario.sql — usuario AdminBodega de producción (opcional)
    16) run-database-crud.ps1 — funciones PL/pgSQL en database-crud/
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
  @{ Label = "012_db_roles_template"; Rel = "init\012_db_roles_template.sql" },
  @{ Label = "013_provider_account_status"; Rel = "init\013_provider_account_status.sql" },
  @{ Label = "014_bodegas_franjas_flexibles"; Rel = "init\014_bodegas_franjas_flexibles.sql" },
  @{ Label = "015_performance_indexes"; Rel = "init\015_performance_indexes.sql" },
  @{ Label = "016_equipos_descarga"; Rel = "init\016_equipos_descarga.sql" },
  @{ Label = "017_equipos_entidades"; Rel = "init\017_equipos_descarga_entidades.sql" },
  @{ Label = "018_franjas_unique_equipo"; Rel = "init\018_franjas_unique_por_equipo.sql" },
  @{ Label = "019_franjas_semanales_equipo"; Rel = "init\019_franjas_semanales_unique_por_equipo.sql" },
  @{ Label = "020_admin_bodega"; Rel = "init\020_admin_bodega.sql" },
  @{ Label = "021_equipos_integridad"; Rel = "init\021_equipos_descarga_integridad.sql" },
  @{ Label = "022_fix_proveedor_ci_email"; Rel = "init\022_fix_proveedor_ci_email.sql" },
  @{ Label = "023_admin_bodega_user"; Rel = "init\023_admin_bodega_usuario.sql" }
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
