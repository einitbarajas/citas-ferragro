#Requires -Version 5.1
# Abre Render en los sitios correctos y copia smtp-render.env al portapapeles.
$repoRoot = Split-Path -Parent $PSScriptRoot
$smtpPath = Join-Path $repoRoot "smtp-render.env"
if (-not (Test-Path $smtpPath)) {
    & (Join-Path $repoRoot "scripts\configurar-smtp-render.ps1") -SkipDeploy
}
Set-Clipboard -Value (Get-Content -LiteralPath $smtpPath -Raw)
Write-Host "smtp-render.env copiado al portapapeles." -ForegroundColor Green
Write-Host ""
Write-Host "Opcion rapida (Environment):" -ForegroundColor Yellow
Write-Host "  RESEND_API_KEY = (de smtp-render.env, linea re_...)" -ForegroundColor Gray
Write-Host "  RESEND_SANDBOX = true" -ForegroundColor Gray
Write-Host ""
Write-Host "Opcion completa: Secret File smtp.env -> pegar (Ctrl+V) -> Save" -ForegroundColor Cyan
Write-Host "Luego: Manual Deploy -> latest commit (obligatorio)" -ForegroundColor Cyan
Write-Host ""
Start-Process "https://dashboard.render.com/web/srv-d82dvanaqgkc739362u0/env"
Start-Sleep -Seconds 1
Start-Process "https://dashboard.render.com/web/srv-d82dvanaqgkc739362u0/secrets"
