#Requires -Version 5.1
<#
  Autoriza CORS para citas.ferragro.vercel.app en Render (ferragro-api).
  Opción A — API key (recomendado):
    $env:RENDER_API_KEY = "rnd_..."   # https://dashboard.render.com/u/settings#api-keys
    .\scripts\fix-cors-citas-render.ps1

  Opción B — manual: abre el panel, pega CORS_ORIGINS y Manual Deploy.
#>
param(
    [string] $ApiKey = $env:RENDER_API_KEY,
    [string] $ServiceId = "srv-d82dvanaqgkc739362u0",
    [switch] $SkipDeploy
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$CorsValue = "https://frontend-ferragro.vercel.app,https://citas.ferragro.vercel.app"
$TestOrigin = "https://citas.ferragro.vercel.app"
$ApiBase = "https://ferragro-api.onrender.com"

function Get-ApiKey {
    param([string] $Explicit)
    if (-not [string]::IsNullOrWhiteSpace($Explicit)) { return $Explicit.Trim() }
    $keyFile = Join-Path $repoRoot ".render-api-key.local"
    if (Test-Path -LiteralPath $keyFile) {
        $fromFile = (Get-Content -LiteralPath $keyFile -Raw).Trim()
        if ($fromFile) { return $fromFile }
    }
    return $null
}

function Set-RenderEnvVar {
    param([string] $Key, [string] $Value, [string] $Token, [string] $Service)
    $uri = "https://api.render.com/v1/services/$Service/env-vars/$Key"
    $body = @{ key = $Key; value = $Value } | ConvertTo-Json -Compress
    $headers = @{
        Authorization  = "Bearer $Token"
        Accept         = "application/json"
        "Content-Type" = "application/json"
    }
    Invoke-RestMethod -Uri $uri -Method Put -Headers $headers -Body $body | Out-Null
}

function Invoke-RenderDeployHook {
    $hook = $env:RENDER_DEPLOY_HOOK
    $hookFile = Join-Path $repoRoot ".render-hook.local"
    if (-not $hook -and (Test-Path -LiteralPath $hookFile)) {
        $hook = (Get-Content -LiteralPath $hookFile -Raw).Trim()
    }
    if ([string]::IsNullOrWhiteSpace($hook)) { return $false }
    Invoke-WebRequest -Uri $hook -Method POST -UseBasicParsing | Out-Null
    return $true
}

function Test-CorsForOrigin {
    param([string] $Origin)
    $headers = @{
        Origin                        = $Origin
        "Access-Control-Request-Method" = "POST"
        "Access-Control-Request-Headers" = "content-type"
    }
    try {
        $r = Invoke-WebRequest -Uri "$ApiBase/api/v1/auth/login" -Method OPTIONS -Headers $headers -UseBasicParsing -TimeoutSec 90
        $allow = $r.Headers["Access-Control-Allow-Origin"]
        return ($r.StatusCode -eq 200 -and $allow -eq $Origin)
    } catch {
        if ($_.Exception.Response) {
            $allow = $_.Exception.Response.Headers["Access-Control-Allow-Origin"]
            return ($allow -eq $Origin)
        }
        return $false
    }
}

$exportPath = Join-Path $repoRoot "cors-render.env"
Set-Content -LiteralPath $exportPath -Value "CORS_ORIGINS=$CorsValue" -Encoding UTF8 -NoNewline

Write-Host "CORS_ORIGINS recomendado:" -ForegroundColor Cyan
Write-Host "  $CorsValue" -ForegroundColor DarkGray
Write-Host ""

$ApiKey = Get-ApiKey -Explicit $ApiKey
if (-not $ApiKey) {
    Write-Host "Sin RENDER_API_KEY. Pasos manuales (2 min):" -ForegroundColor Yellow
    Write-Host "  1. Render -> ferragro-api -> Environment"
    Write-Host "  2. CORS_ORIGINS = (copia de cors-render.env en la raiz del repo)"
    Write-Host "  3. Save -> Manual Deploy"
    Write-Host ""
    Write-Host "Tras el deploy del codigo (regex Vercel en main.py), citas deberia funcionar aun sin cambiar env." -ForegroundColor DarkGray
    Start-Process "https://dashboard.render.com/web/$ServiceId/env"
    exit 1
}

Write-Host "Actualizando CORS_ORIGINS en Render..." -ForegroundColor Cyan
Set-RenderEnvVar -Key "CORS_ORIGINS" -Value $CorsValue -Token $ApiKey -Service $ServiceId
Write-Host "  OK CORS_ORIGINS" -ForegroundColor Green

if (-not $SkipDeploy) {
    if (Invoke-RenderDeployHook) {
        Write-Host "Deploy iniciado (hook). Esperando 2-4 min..." -ForegroundColor Green
        for ($i = 1; $i -le 24; $i++) {
            Start-Sleep -Seconds 15
            if (Test-CorsForOrigin -Origin $TestOrigin) {
                Write-Host "CORS OK para $TestOrigin" -ForegroundColor Green
                Write-Host "Prueba login: https://citas.ferragro.vercel.app (Ctrl+F5)" -ForegroundColor Green
                exit 0
            }
            Write-Host "  intento $i : API aun desplegando..."
        }
        Write-Host "Variable guardada; verifica Manual Deploy en Render si CORS sigue fallando." -ForegroundColor Yellow
        exit 1
    }
    Write-Host "Sin deploy hook: haz Manual Deploy en Render." -ForegroundColor Yellow
    Start-Process "https://dashboard.render.com/web/$ServiceId"
    exit 1
}

Write-Host "CORS guardado (sin redeploy). Ejecuta deploy-render-ahora.ps1" -ForegroundColor Green
