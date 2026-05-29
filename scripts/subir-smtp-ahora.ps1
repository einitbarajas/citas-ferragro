#Requires -Version 5.1
<#
  Sube SMTP a Render desde .env o smtp-render.env y despliega.
  Requiere RENDER_API_KEY en .env o variable de entorno.
  Uso: .\scripts\subir-smtp-ahora.ps1
#>
$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $repoRoot ".env"
if (-not (Test-Path -LiteralPath $envFile)) { $envFile = Join-Path $repoRoot "smtp-render.env" }

& (Join-Path $repoRoot "scripts\configurar-smtp-render.ps1") -EnvFile $envFile
if ($LASTEXITCODE -ne 0) {
    & (Join-Path $repoRoot "scripts\pegar-smtp-en-render.ps1")
    exit 1
}

Write-Host ""
Write-Host "SMTP subido. Prueba olvidé contraseña en citas.ferragro.vercel.app" -ForegroundColor Green
