#Requires -Version 5.1
<#
  Sube Resend + SMTP a Render. smtp-render.env ya debe tener RESEND_API_KEY.
  Uso: .\scripts\subir-resend-render.ps1
       .\scripts\subir-resend-render.ps1 -RenderApiKey "rnd_..."
#>
param([string] $RenderApiKey = $env:RENDER_API_KEY)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$smtpPath = Join-Path $repoRoot "smtp-render.env"

if (-not (Test-Path -LiteralPath $smtpPath)) {
    & (Join-Path $repoRoot "scripts\configurar-smtp-render.ps1") -EnvFile (Join-Path $repoRoot ".env")
}

$content = Get-Content -LiteralPath $smtpPath -Raw
Set-Clipboard -Value $content

if (-not $RenderApiKey) {
    $kf = Join-Path $repoRoot ".render-api-key.local"
    if (Test-Path -LiteralPath $kf) { $RenderApiKey = (Get-Content -LiteralPath $kf -Raw).Trim() }
}
$dot = @{}
foreach ($line in Get-Content (Join-Path $repoRoot ".env") -ErrorAction SilentlyContinue) {
    if ($line -match '^\s*RENDER_API_KEY\s*=\s*(.+)\s*$') { $RenderApiKey = $Matches[1].Trim().Trim('"') }
}

$reMatch = Select-String -Path $smtpPath -Pattern '^\s*RESEND_API_KEY\s*=\s*(.+)\s*$' | Select-Object -First 1
$resendKey = if ($reMatch) { $reMatch.Matches.Groups[1].Value.Trim().Trim('"').Trim("'") } else { "" }

if (-not $resendKey) {
    Write-Host "Falta RESEND_API_KEY en smtp-render.env" -ForegroundColor Red
    exit 1
}

if ($RenderApiKey) {
    & (Join-Path $repoRoot "scripts\activar-correo-render.ps1") -ResendKey $resendKey -RenderApiKey $RenderApiKey
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "smtp-render.env copiado al portapapeles." -ForegroundColor Green
Write-Host ""
Write-Host "En Render (se abrio el navegador):" -ForegroundColor Cyan
Write-Host "  1. Environment -> Add from .env -> pega (Ctrl+V) o elige smtp-render.env"
Write-Host "  2. Save Changes"
Write-Host "  3. Manual Deploy -> Deploy latest commit"
Write-Host ""
Write-Host "Luego abre: https://ferragro-api.onrender.com/health"
Write-Host "  Debe mostrar resend_ready: true"
Start-Process "https://dashboard.render.com/web/srv-d82dvanaqgkc739362u0/env"
