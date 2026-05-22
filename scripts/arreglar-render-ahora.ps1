#Requires -Version 5.1
<#
  Diagnostico + disparo de deploy Render + comprobacion /health.
#>
param([string]$HookUrl = $env:RENDER_DEPLOY_HOOK)

$ErrorActionPreference = "Continue"
$repoRoot = Split-Path -Parent $PSScriptRoot
$healthUrl = "https://ferragro-api.onrender.com/health"
$warehousesUrl = "https://ferragro-api.onrender.com/api/v1/crud/warehouses"
$panel = "https://dashboard.render.com/web/srv-d82dvanaqgkc739362u0"

Set-Location $repoRoot
$expected = "2026-05-22-prod-sync-v2"
if (Test-Path "backend\app\main.py") {
    $line = Select-String "backend\app\main.py" -Pattern "^API_BUILD_ID"
    if ($line.Line -match '"([^"]+)"') { $expected = $Matches[1] }
}

Write-Host ""
Write-Host "=== Diagnostico Render (ferragro-api) ===" -ForegroundColor Cyan
Write-Host "build_id esperado: $expected"
Write-Host ""

try {
    $h = Invoke-RestMethod $healthUrl -TimeoutSec 90
    $bid = $h.data.build_id
    Write-Host "Health build_id: $bid" -ForegroundColor $(if ($bid -eq $expected) { "Green" } else { "Red" })
} catch {
    Write-Host "Health: sin respuesta ($($_.Exception.Message))" -ForegroundColor Red
    $bid = ""
}

try {
    Invoke-WebRequest $warehousesUrl -Method GET -UseBasicParsing -TimeoutSec 60 | Out-Null
    Write-Host "GET /crud/warehouses: OK (API nuevo)" -ForegroundColor Green
} catch {
    $code = $_.Exception.Response.StatusCode.value__
    Write-Host "GET /crud/warehouses: HTTP $code (API viejo si es 404)" -ForegroundColor Red
}

if ($bid -eq $expected) {
    Write-Host ""
    Write-Host "El API ya esta actualizado. Recarga el portal con Ctrl+F5." -ForegroundColor Green
    exit 0
}

Write-Host ""
Write-Host "El API sigue desactualizado." -ForegroundColor Yellow
Write-Host "Guia: ARREGLAR-RENDER-AHORA.md"
Write-Host ""

if (-not $HookUrl) {
    Write-Host "Pega la Deploy Hook URL (Render -> Settings -> Deploy Hook):" -ForegroundColor Cyan
    $HookUrl = Read-Host "URL"
}

if ($HookUrl) {
    try {
        $r = Invoke-WebRequest -Uri $HookUrl.Trim() -Method POST -UseBasicParsing
        Write-Host "Hook enviado (HTTP $($r.StatusCode)). Esperando..." -ForegroundColor Green
        for ($i = 1; $i -le 24; $i++) {
            Start-Sleep 20
            $h2 = Invoke-RestMethod $healthUrl -TimeoutSec 120
            Write-Host "  $i : $($h2.data.build_id)"
            if ($h2.data.build_id -eq $expected) {
                Write-Host "Listo." -ForegroundColor Green
                exit 0
            }
        }
    } catch {
        Write-Host "Hook fallo: $_" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "Abre Render -> Manual Deploy -> Deploy latest commit" -ForegroundColor Yellow
Start-Process $panel
Start-Process $healthUrl
exit 1
