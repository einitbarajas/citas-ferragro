#Requires -Version 5.1
<#
  Activa correo en producción (Render + Resend desde .env).

  Uso (pega tu key de Render una sola vez):
    .\scripts\hacer-correo-funcionar.ps1 -RenderApiKey "rnd_..."

  La key: https://dashboard.render.com/u/settings#api-keys
#>
param(
    [Parameter(Mandatory = $true)]
    [string] $RenderApiKey
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $repoRoot ".env"

if (-not (Test-Path -LiteralPath $envFile)) {
    throw "No existe .env en la raíz del repo."
}
if (-not (Select-String -Path $envFile -Pattern '^\s*RESEND_API_KEY\s*=' -Quiet)) {
    throw "Falta RESEND_API_KEY en .env"
}

$line = "RENDER_API_KEY=$($RenderApiKey.Trim())"
if (Select-String -Path $envFile -Pattern '^\s*RENDER_API_KEY\s*=' -Quiet) {
    (Get-Content -LiteralPath $envFile -Encoding UTF8) | ForEach-Object {
        if ($_ -match '^\s*RENDER_API_KEY\s*=') { $line } else { $_ }
    } | Set-Content -LiteralPath $envFile -Encoding UTF8
} else {
    Add-Content -LiteralPath $envFile -Value ""
    Add-Content -LiteralPath $envFile -Value $line
}

$env:RENDER_API_KEY = $RenderApiKey.Trim()
Write-Host "Subiendo Resend + SMTP a Render y desplegando..." -ForegroundColor Cyan
& (Join-Path $repoRoot "scripts\configurar-smtp-render.ps1") -ApiKey $RenderApiKey.Trim()
exit $LASTEXITCODE
