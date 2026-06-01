#Requires -Version 5.1
<#
  Prueba el sistema de correo en producción (diagnóstico + envío opcional).

  Uso:
    .\scripts\probar-correo-completo.ps1
    .\scripts\probar-correo-completo.ps1 -Email "tu@gmail.com" -MaintenanceToken "..."
#>
param(
    [string] $ApiBase = "https://ferragro-api.onrender.com",
    [string] $Email = "",
    [string] $MaintenanceToken = "",
    [ValidateSet("notification", "recovery", "welcome")]
    [string] $Template = "notification"
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "=== Diagnóstico correo Ferragro ===" -ForegroundColor Cyan
Write-Host ""

$h = Invoke-RestMethod -Uri "$ApiBase/health" -TimeoutSec 90
$e = Invoke-RestMethod -Uri "$ApiBase/health/email" -TimeoutSec 90

Write-Host "build_id:        $($h.data.build_id)" -ForegroundColor $(if ($h.data.build_id -like "*email-delivery*") { "Green" } else { "Yellow" })
Write-Host "email_enabled:   $($h.data.email_enabled)"
Write-Host "email_provider:  $($h.data.email_provider)"
Write-Host "resend_ready:    $($h.data.resend_ready)"
Write-Host "resend_sandbox:  $($h.data.resend_sandbox)"
Write-Host "can_deliver:     $($e.data.can_deliver)"
Write-Host "panel_url:       $($e.data.public_panel_url)"
Write-Host ""

if (-not $e.data.can_deliver) {
    Write-Host "CORREO NO OPERATIVO. Ejecuta:" -ForegroundColor Red
    Write-Host "  .\scripts\configurar-smtp-render.ps1"
    Write-Host "Ver ARREGLAR-CORREO-AHORA.md"
    exit 1
}

if (-not $Email) {
    Write-Host "Correo operativo. Para envío real:" -ForegroundColor Green
    Write-Host '  .\scripts\probar-correo-completo.ps1 -Email "tu@gmail.com" -MaintenanceToken "..."'
    exit 0
}

if (-not $MaintenanceToken) {
    Write-Host "Falta -MaintenanceToken (variable MAINTENANCE_TOKEN en Render)." -ForegroundColor Yellow
    exit 1
}

$body = @{ email = $Email; template = $Template } | ConvertTo-Json
$headers = @{ "X-Maintenance-Token" = $MaintenanceToken; "Content-Type" = "application/json" }
$r = Invoke-RestMethod -Uri "$ApiBase/api/auth/maintenance/send-test-email" -Method Post -Headers $headers -Body $body -TimeoutSec 120
Write-Host "OK: $($r.message) provider=$($r.data.provider) template=$($r.data.template)" -ForegroundColor Green
