#Requires -Version 5.1
<#
.SYNOPSIS
  Crea el primer usuario Admin en la base (producción Render o local).

.DESCRIPTION
  Inserta credenciales + fila en Usuarios con rol Admin.
  Idempotente: si el correo ya existe, no duplica.

.PARAMETER DatabaseUrl
  URI postgresql://... Si se omite, usa DATABASE_URL del .env en la raíz.

.PARAMETER Email
  Correo del administrador (default: admin@ferragro.com).

.PARAMETER Password
  Contraseña en texto plano (mínimo 6 caracteres). Si se omite, se genera una aleatoria.

.PARAMETER DocumentId
  Documento del usuario (7-10 dígitos, default: 90000001).

.PARAMETER FullName
  Nombre completo (default: Administrador Portal).

.PARAMETER ResetPassword
  Si el correo ya existe, actualiza la contraseña en lugar de omitir.

.EXAMPLE
  cd db
  .\bootstrap-admin.ps1 -DatabaseUrl "postgresql://user:pass@host:5432/ferragro"

.EXAMPLE
  .\bootstrap-admin.ps1 -Email "admin@miempresa.com" -Password "MiClaveSegura12"
#>
[CmdletBinding()]
param(
  [string] $DatabaseUrl = "",
  [string] $Email = "admin@ferragro.com",
  [string] $Password = "",
  [string] $DocumentId = "90000001",
  [string] $FullName = "Administrador Portal",
  [string] $EnvFile = "",
  [switch] $ResetPassword
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

if ([string]::IsNullOrWhiteSpace($Password)) {
  $Password = -join ((48..57 + 65..90 + 97..122) | Get-Random -Count 16 | ForEach-Object { [char]$_ })
  $generatedPassword = $true
} else {
  $generatedPassword = $false
}

if ($Password.Length -lt 6) {
  throw "La contraseña debe tener al menos 6 caracteres."
}

if ($DocumentId -notmatch '^\d{7,10}$') {
  throw "DocumentId debe ser numérico de 7 a 10 dígitos."
}

function Escape-SqlLiteral([string] $Value) {
  return $Value.Replace("'", "''")
}

$psqlExe = Resolve-PsqlExecutable
$eEmail = Escape-SqlLiteral $Email
$ePassword = Escape-SqlLiteral $Password
$eDocumento = Escape-SqlLiteral $DocumentId
$eNombre = Escape-SqlLiteral $FullName

$resetBlock = if ($ResetPassword) {
@"
  IF EXISTS (SELECT 1 FROM "Credenciales" WHERE "Correo" = '$eEmail') THEN
    PERFORM credenciales_update_password_plain(
      (SELECT "IdCredencial" FROM "Credenciales" WHERE "Correo" = '$eEmail' LIMIT 1),
      '$ePassword'
    );
    RAISE NOTICE 'Contraseña actualizada para %', '$eEmail';
    RETURN;
  END IF;
"@
} else {
@"
  IF EXISTS (SELECT 1 FROM "Credenciales" WHERE "Correo" = '$eEmail') THEN
    RAISE NOTICE 'El correo % ya existe. Usa -ResetPassword para cambiar la clave.', '$eEmail';
    RETURN;
  END IF;
"@
}

$sql = @"
DO `$`$
DECLARE
  v_cred_id INTEGER;
  v_rol_admin INTEGER;
BEGIN
  SELECT "Id" INTO v_rol_admin FROM "Rol" WHERE "Nombre" = 'Admin' LIMIT 1;
  IF v_rol_admin IS NULL THEN
    RAISE EXCEPTION 'No existe el rol Admin. Ejecuta antes db/run-database-all.ps1';
  END IF;

$resetBlock

  v_cred_id := credenciales_create_plain('$eEmail', '$ePassword');

  INSERT INTO "Usuarios" ("IdDocumento", "NombreCompleto", "IdCredencial", "IdRol")
  VALUES ('$eDocumento', '$eNombre', v_cred_id, v_rol_admin)
  ON CONFLICT ("IdDocumento") DO NOTHING;

  RAISE NOTICE 'Admin creado: % (documento %)', '$eEmail', '$eDocumento';
END `$`$;
"@

$tempSql = Join-Path $env:TEMP "ferragro-bootstrap-admin.sql"
Set-Content -LiteralPath $tempSql -Value $sql -Encoding UTF8

Write-Host "`n=== Bootstrap: primer usuario Admin ===" -ForegroundColor Cyan
Write-Host "Correo:     $Email" -ForegroundColor DarkGray
Write-Host "Documento:  $DocumentId" -ForegroundColor DarkGray
Write-Host "DATABASE:   $($DatabaseUrl -replace ':[^:@/]+@', ':****@')" -ForegroundColor DarkGray

& $psqlExe $DatabaseUrl -v ON_ERROR_STOP=1 -f $tempSql
Remove-Item -LiteralPath $tempSql -Force -ErrorAction SilentlyContinue

if ($LASTEXITCODE -ne 0) {
  throw "bootstrap-admin terminó con código $LASTEXITCODE"
}

Write-Host "`n=== Listo ===" -ForegroundColor Green
Write-Host "Inicia sesión en el portal con:" -ForegroundColor White
Write-Host "  Correo:    $Email"
if ($generatedPassword) {
  Write-Host "  Contraseña (generada, guárdala ahora):" -ForegroundColor Yellow
  Write-Host "  $Password" -ForegroundColor Yellow
} else {
  Write-Host "  Contraseña: la que indicaste al ejecutar el script."
}
Write-Host "`nDesde el panel Admin podrás crear usuarios de Logística." -ForegroundColor DarkGray
