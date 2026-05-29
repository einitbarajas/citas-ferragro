#Requires -Version 5.1
<#
  Prueba login SMTP con smtp-render.env (mismo flujo que olvidé mi contraseña).
  Uso: .\scripts\probar-smtp-recuperacion.ps1
#>
$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $repoRoot "smtp-render.env"
if (-not (Test-Path -LiteralPath $envFile)) {
    throw "No existe smtp-render.env en la raíz del repo."
}
Get-Content -LiteralPath $envFile | ForEach-Object {
    if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$') {
        Set-Item -Path "env:$($Matches[1])" -Value $Matches[2]
    }
}
$env:ENVIRONMENT = "production"
$backend = Join-Path $repoRoot "backend"
Push-Location $backend
try {
    $py = if (Test-Path ".\.venv\Scripts\python.exe") { ".\.venv\Scripts\python.exe" } else { "python" }
    & $py -c @"
from app.core.config import refresh_smtp_settings
from app.services.mailer import smtp_login_probe, send_temporary_password_email

ready = refresh_smtp_settings(force_secret_overlay=True)
print('smtp_send_ready', ready)
print('smtp_login_ok', smtp_login_probe())
"@
} finally {
    Pop-Location
}
