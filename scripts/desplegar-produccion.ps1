#Requires -Version 5.1
<#
  Deja producción al día (Render API + comprobación + abre paneles).

  Uso:
    .\scripts\desplegar-produccion.ps1
    .\scripts\desplegar-produccion.ps1 -HookUrl "https://api.render.com/deploy/srv-...?key=..."

  Guarda el hook una vez (no lo subas a Git):
    "https://..." | Set-Content -Path ".render-hook.local" -NoNewline
#>
param([string]$HookUrl = $env:RENDER_DEPLOY_HOOK)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$healthUrl = "https://ferragro-api.onrender.com/health"
$portalUrl = "https://frontend-ferragro.vercel.app"
$renderPanel = "https://dashboard.render.com/web/srv-d82dvanaqgkc739362u0"
$vercelPanel = "https://vercel.com/ferragro/frontend/deployments"
$hookFile = Join-Path $repoRoot ".render-hook.local"

Set-Location $repoRoot

$expected = "2026-05-25-prod-v1"
$line = Select-String "backend\app\main.py" -Pattern '^API_BUILD_ID' -ErrorAction SilentlyContinue
if ($line -and $line.Line -match '"([^"]+)"') { $expected = $Matches[1] }

$localSha = (git rev-parse --short HEAD).Trim()

function Get-Health {
    Invoke-RestMethod $healthUrl -TimeoutSec 120
}

Write-Host ""
Write-Host "=== Desplegar produccion (Ferragro) ===" -ForegroundColor Cyan
Write-Host "Commit local:  $localSha"
Write-Host "build_id meta: $expected"
Write-Host ""

try {
    $h = Get-Health
    $bid = $h.data.build_id
    $git = $h.data.render_git_commit
    $gitShort = if ($git) { $git.Substring(0, [Math]::Min(7, $git.Length)) } else { "?" }
    Write-Host "Produccion ahora: build_id=$bid  git=$gitShort" -ForegroundColor $(if ($bid -eq $expected -and $gitShort -eq $localSha) { "Green" } else { "Yellow" })
} catch {
    Write-Host "No responde /health (cold start?). Espera 60s y reintenta." -ForegroundColor Red
}

if (-not $HookUrl -and (Test-Path $hookFile)) {
    $HookUrl = (Get-Content $hookFile -Raw).Trim()
}

if ($bid -eq $expected -and $gitShort -eq $localSha) {
    Write-Host ""
    Write-Host "El API ya esta en la version nueva." -ForegroundColor Green
    Write-Host "Si el portal se ve viejo: Vercel -> Redeploy -> $portalUrl -> Ctrl+F5"
    Start-Process $vercelPanel
    exit 0
}

# --- Render ---
Write-Host ""
Write-Host "[1/2] Render API..." -ForegroundColor Yellow

if (-not $HookUrl) {
    Write-Host "Sin Deploy Hook. Opciones:" -ForegroundColor Cyan
    Write-Host "  A) Pega la URL ahora (Render -> ferragro-api -> Settings -> Deploy Hook)"
    Write-Host "  B) Manual Deploy en el panel que se abrira"
    $HookUrl = Read-Host "Hook URL (Enter para solo abrir panel)"
    if ($HookUrl) {
        $HookUrl.Trim() | Set-Content $hookFile -NoNewline
        [Environment]::SetEnvironmentVariable("RENDER_DEPLOY_HOOK", $HookUrl.Trim(), "User")
        Write-Host "Hook guardado en .render-hook.local y variable de usuario." -ForegroundColor DarkGray
    }
}

if ($HookUrl) {
    Write-Host "Disparando deploy en Render..."
    Invoke-WebRequest -Uri $HookUrl.Trim() -Method POST -UseBasicParsing | Out-Null
    Write-Host "Esperando /health (max 8 min)..."
    for ($i = 1; $i -le 24; $i++) {
        Start-Sleep -Seconds 20
        try {
            $h2 = Get-Health
            Write-Host "  $i : build_id=$($h2.data.build_id)"
            if ($h2.data.build_id -eq $expected) {
                Write-Host "API actualizado." -ForegroundColor Green
                break
            }
        } catch {
            Write-Host "  $i : esperando..."
        }
    }
} else {
    Write-Host "Abre Render -> Manual Deploy -> Deploy latest commit ($localSha)" -ForegroundColor Yellow
    Start-Process $renderPanel
}

# --- Vercel ---
Write-Host ""
Write-Host "[2/2] Vercel (portal)..." -ForegroundColor Yellow
Write-Host "  Redeploy en: $vercelPanel"
Write-Host "  Luego: $portalUrl  (Ctrl+F5)"
Start-Process $vercelPanel

Write-Host ""
Write-Host "Comprueba: $healthUrl" -ForegroundColor Cyan
Write-Host "  build_id debe ser: $expected"
Write-Host "  render_git_commit debe empezar por: $localSha"
Write-Host ""

try {
    $hf = Get-Health
    if ($hf.data.build_id -ne $expected) {
        Write-Host "El API aun no muestra el build nuevo. Revisa Render -> Events (Build failed?)." -ForegroundColor Red
        exit 1
    }
} catch {
    exit 1
}

exit 0
