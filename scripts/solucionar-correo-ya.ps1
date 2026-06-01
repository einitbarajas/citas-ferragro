#Requires -Version 5.1
<#
  Activa correo en Render (obligatorio para que funcione en producción).
  Uso:
    .\scripts\solucionar-correo-ya.ps1
    .\scripts\solucionar-correo-ya.ps1 -RenderApiKey "rnd_..."
#>
param([string] $RenderApiKey = "")

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$keyFile = Join-Path $repoRoot ".render-api-key.local"
$smtpPath = Join-Path $repoRoot "smtp-render.env"

if (-not (Test-Path $smtpPath)) {
    & (Join-Path $repoRoot "scripts\configurar-smtp-render.ps1") -SkipDeploy
}

if (-not $RenderApiKey) {
    if (Test-Path $keyFile) { $RenderApiKey = (Get-Content -LiteralPath $keyFile -Raw).Trim() }
}
if (-not $RenderApiKey) {
    $dot = Get-Content (Join-Path $repoRoot ".env") -ErrorAction SilentlyContinue
    foreach ($line in $dot) {
        if ($line -match '^\s*RENDER_API_KEY\s*=\s*(.+)\s*$') {
            $RenderApiKey = $Matches[1].Trim().Trim('"').Trim("'")
            break
        }
    }
}
if (-not $RenderApiKey) {
    Write-Host ""
    Write-Host "Necesito tu API key de Render (no caduca)." -ForegroundColor Yellow
    Write-Host "  https://dashboard.render.com/u/settings#api-keys" -ForegroundColor Cyan
    Write-Host ""
    $RenderApiKey = Read-Host "Pega RENDER_API_KEY (rnd_...)"
}
if (-not $RenderApiKey) { throw "Sin RENDER_API_KEY no puedo subir Resend al servidor." }

Set-Content -LiteralPath $keyFile -Value $RenderApiKey.Trim() -Encoding UTF8 -NoNewline
$env:RENDER_API_KEY = $RenderApiKey.Trim()

Write-Host ""
Write-Host "Subiendo Resend + smtp.env a Render y desplegando..." -ForegroundColor Cyan
python (Join-Path $repoRoot "scripts\push_resend_to_render.py")
exit $LASTEXITCODE
