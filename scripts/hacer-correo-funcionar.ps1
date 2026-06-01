#Requires -Version 5.1
<#
  Activa correo en producción (Render + Resend desde .env).

  Uso (pega tu key de Render una sola vez):
    .\scripts\hacer-correo-funcionar.ps1 -RenderApiKey "rnd_..."

  La key: https://dashboard.render.com/u/settings#api-keys
#>
param(
    [string] $RenderApiKey = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $repoRoot ".env"

if (-not (Test-Path -LiteralPath $envFile)) {
    throw "No existe .env en la raíz del repo."
}

if (-not $RenderApiKey) {
    $keyFile = Join-Path $repoRoot ".render-api-key.local"
    if (Test-Path -LiteralPath $keyFile) {
        $RenderApiKey = (Get-Content -LiteralPath $keyFile -Raw).Trim()
    }
}
if (-not $RenderApiKey) {
    $dot = Get-Content -LiteralPath $envFile -Encoding UTF8
    foreach ($line in $dot) {
        if ($line -match '^\s*RENDER_API_KEY\s*=\s*(.+)\s*$') {
            $RenderApiKey = $Matches[1].Trim().Trim('"').Trim("'")
            break
        }
    }
}
if (-not $RenderApiKey) {
    Write-Host "Falta RENDER_API_KEY." -ForegroundColor Red
    Write-Host "  1) Crea key en https://dashboard.render.com/u/settings#api-keys" -ForegroundColor Yellow
    Write-Host "  2) Guardala en .render-api-key.local (una linea rnd_...) o ejecuta:" -ForegroundColor Yellow
    Write-Host '     .\scripts\hacer-correo-funcionar.ps1 -RenderApiKey "rnd_..."' -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Manual: pega smtp-render.env en Render Environment (ya en portapapeles si corriste subir-resend-render.ps1)" -ForegroundColor Yellow
    & (Join-Path $repoRoot "scripts\subir-resend-render.ps1")
    exit 1
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
