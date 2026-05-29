#Requires -Version 5.1
<#
  Sube la API key de correo a Render (Resend o Brevo). Solo te pide la key una vez.
  Uso:
    .\scripts\activar-correo-render.ps1
    .\scripts\activar-correo-render.ps1 -ResendKey "re_..." -RenderApiKey "rnd_..."
#>
param(
    [string] $ResendKey = "",
    [string] $BrevoKey = "",
    [string] $RenderApiKey = $env:RENDER_API_KEY,
    [switch] $ResendSandbox
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$serviceId = "srv-d82dvanaqgkc739362u0"
$healthUrl = "https://ferragro-api.onrender.com/health"

function Set-RenderEnvVar {
    param([string] $Key, [string] $Value, [string] $Token, [string] $Service)
    $uri = "https://api.render.com/v1/services/$Service/env-vars/$Key"
    $body = (@{ key = $Key; value = $Value } | ConvertTo-Json -Compress)
    $headers = @{
        Authorization = "Bearer $Token"
        Accept        = "application/json"
        "Content-Type" = "application/json"
    }
    Invoke-RestMethod -Uri $uri -Method Put -Headers $headers -Body $body | Out-Null
    Write-Host "  OK $Key" -ForegroundColor Green
}

function Invoke-RenderDeploy {
    param([string] $Token, [string] $Service)
    $uri = "https://api.render.com/v1/services/$Service/deploys"
    $headers = @{
        Authorization  = "Bearer $Token"
        Accept         = "application/json"
        "Content-Type" = "application/json"
    }
    Invoke-RestMethod -Uri $uri -Method Post -Headers $headers -Body "{}" | Out-Null
}

Write-Host ""
Write-Host "=== Activar correo en Render (sin dominio en Resend) ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "NO uses ferragro-api.onrender.com en Resend Domains." -ForegroundColor Yellow
Write-Host "Solo necesitas la API key (re_...) de https://resend.com/api-keys" -ForegroundColor Yellow
Write-Host ""

if (-not $ResendKey -and -not $BrevoKey) {
    $ResendKey = Read-Host "Pega tu RESEND_API_KEY (re_...) o Enter para omitir"
}
if (-not $BrevoKey -and -not $ResendKey) {
    $BrevoKey = Read-Host "O pega BREVO_API_KEY (xkeysib-...) o Enter"
}

if (-not $ResendKey -and -not $BrevoKey) {
    Write-Host "Necesitas al menos una API key." -ForegroundColor Red
    Start-Process "https://resend.com/api-keys"
    exit 1
}

if (-not $RenderApiKey) {
    $keyFile = Join-Path $repoRoot ".render-api-key.local"
    if (Test-Path -LiteralPath $keyFile) {
        $RenderApiKey = (Get-Content -LiteralPath $keyFile -Raw).Trim()
    }
}
if (-not $RenderApiKey) {
    Write-Host "Falta RENDER_API_KEY (Render -> Account -> API Keys -> rnd_...)" -ForegroundColor Yellow
    $RenderApiKey = Read-Host "Pega RENDER_API_KEY"
}
if (-not $RenderApiKey) {
    Write-Host "Sin Render API key no puedo subir variables automaticamente." -ForegroundColor Red
    Write-Host "Copia manualmente en Render Environment:"
    if ($ResendKey) {
        Write-Host "  RESEND_API_KEY=$ResendKey"
        Write-Host "  RESEND_SANDBOX=true"
    }
    if ($BrevoKey) { Write-Host "  BREVO_API_KEY=$BrevoKey" }
    Start-Process "https://dashboard.render.com/web/$serviceId/env"
    exit 1
}

Write-Host "Subiendo variables a Render..." -ForegroundColor Cyan
if ($ResendKey) {
    Set-RenderEnvVar -Key "RESEND_API_KEY" -Value $ResendKey.Trim() -Token $RenderApiKey -Service $serviceId
    # Sin dominio verificado en Resend: sandbox envía a la cuenta Gmail de Resend.
    Set-RenderEnvVar -Key "RESEND_SANDBOX" -Value "true" -Token $RenderApiKey -Service $serviceId
    Write-Host "  RESEND_SANDBOX=true (no necesitas Domains en Resend)" -ForegroundColor DarkGray
}
if ($BrevoKey) {
    Set-RenderEnvVar -Key "BREVO_API_KEY" -Value $BrevoKey.Trim() -Token $RenderApiKey -Service $serviceId
    Set-RenderEnvVar -Key "SMTP_FROM_EMAIL" -Value "nataliabarajas412@gmail.com" -Token $RenderApiKey -Service $serviceId
}

Write-Host "Desplegando API..." -ForegroundColor Cyan
try {
    Invoke-RenderDeploy -Token $RenderApiKey -Service $serviceId
} catch {
    Write-Host "Deploy API fallo; haz Manual Deploy en Render." -ForegroundColor Yellow
}

Write-Host "Esperando health (hasta 6 min)..." -ForegroundColor Cyan
for ($i = 1; $i -le 24; $i++) {
    Start-Sleep -Seconds 15
    try {
        $h = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 90
        $p = $h.data.email_provider
        $ok = $h.data.resend_ready -or $h.data.brevo_ready
        Write-Host "  [$i] build=$($h.data.build_id) provider=$p resend=$($h.data.resend_ready) brevo=$($h.data.brevo_ready)"
        if ($ok -and $h.data.build_id -like "*email-https*") {
            Write-Host ""
            Write-Host "Correo listo. Prueba Olvide mi contrasena en citas." -ForegroundColor Green
            exit 0
        }
    } catch {
        Write-Host "  [$i] desplegando..."
    }
}

Write-Host "Variables guardadas. Si el build no cambio, Manual Deploy en Render." -ForegroundColor Yellow
exit 1
