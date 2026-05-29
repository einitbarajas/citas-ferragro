#Requires -Version 5.1
<#
  Guía para activar Resend en Render (correo sin SMTP en plan free).
  Uso: .\scripts\configurar-resend-render.ps1
#>
$serviceId = "srv-d82dvanaqgkc739362u0"
$health = "https://ferragro-api.onrender.com/health"

Write-Host ""
Write-Host "=== Correo en Render (Resend) ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Render FREE bloquea Gmail SMTP. Necesitas Resend:" -ForegroundColor Yellow
Write-Host "  1. https://resend.com -> cuenta free"
Write-Host "  2. Verifica remitente: nataliabarajas412@gmail.com"
Write-Host "  3. API Keys -> copia re_..."
Write-Host "  4. Render -> ferragro-api -> Environment:"
Write-Host "       RESEND_API_KEY=re_..."
Write-Host "       RESEND_FROM_EMAIL=nataliabarajas412@gmail.com"
Write-Host "  5. Save -> Manual Deploy"
Write-Host ""
Write-Host "Guía completa: ARREGLAR-CORREO-AHORA.md"
Write-Host ""
Start-Process "https://resend.com/api-keys"
Start-Process "https://dashboard.render.com/web/$serviceId/env"

try {
    $h = Invoke-RestMethod -Uri $health -TimeoutSec 60
    Write-Host "Producción: provider=$($h.data.email_provider) resend=$($h.data.resend_ready)" -ForegroundColor DarkGray
} catch { }
