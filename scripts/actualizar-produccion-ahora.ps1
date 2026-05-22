#Requires -Version 5.1
<#
  Actualiza produccion: Vercel (CLI) + guia/poll Render API.
  Uso:
    .\scripts\actualizar-produccion-ahora.ps1
    $env:RENDER_DEPLOY_HOOK = 'https://api.render.com/deploy/srv-...?key=...'
    .\scripts\actualizar-produccion-ahora.ps1
#>
$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$apiUrl = "https://ferragro-api.onrender.com/health"
$frontUrl = "https://frontend-ferragro.vercel.app"
$renderPanel = "https://dashboard.render.com/web/srv-d82dvanaqgkc739362u0"
$vercelGit = "https://vercel.com/ferragro/frontend/settings/git"
$ghSecrets = "https://github.com/einitbarajas/citas-ferragro/settings/secrets/actions"

Set-Location $repoRoot

$expectedBuild = (Select-String -Path "backend\app\main.py" -Pattern '^API_BUILD_ID\s*=').Line
if ($expectedBuild -match '"([^"]+)"') { $expectedBuild = $Matches[1] } else { $expectedBuild = "?" }

function Get-Health {
    try {
        return Invoke-RestMethod -Uri $apiUrl -Method GET -TimeoutSec 120
    } catch {
        return $null
    }
}

Write-Host ""
Write-Host "=== Actualizar produccion Ferragro ===" -ForegroundColor Cyan
Write-Host "Commit en main:" (git log -1 --oneline) -ForegroundColor DarkGray
Write-Host "build_id esperado:" $expectedBuild -ForegroundColor DarkGray
Write-Host ""

# --- Vercel ---
Write-Host "[1/3] Vercel (frontend)..." -ForegroundColor Yellow
Set-Location (Join-Path $repoRoot "frontend")
try {
    npx vercel@54.4.0 deploy --prod --yes 2>&1 | Out-Host
    Write-Host "  Front desplegado -> $frontUrl" -ForegroundColor Green
} catch {
    Write-Host "  Error Vercel CLI: $_" -ForegroundColor Red
    Write-Host "  Alternativa: panel $vercelGit" -ForegroundColor DarkGray
}
Set-Location $repoRoot

# --- Render ---
Write-Host ""
Write-Host "[2/3] Render (API)..." -ForegroundColor Yellow
$hook = $env:RENDER_DEPLOY_HOOK
if ($hook) {
    Write-Host "  Disparando Deploy Hook..."
    $resp = Invoke-WebRequest -Uri $hook.Trim() -Method POST -UseBasicParsing
    Write-Host "  Hook HTTP $($resp.StatusCode)" -ForegroundColor Green
} else {
    Write-Host "  RENDER_DEPLOY_HOOK no definido." -ForegroundColor Yellow
    Write-Host "  En Render: Manual Deploy -> Deploy latest commit" -ForegroundColor Yellow
    $open = Read-Host "  Abrir panel Render ahora? (s/n)"
    if ($open -eq "s") { Start-Process $renderPanel }
}

Write-Host ""
Write-Host "[3/3] Esperando API /health (max ~8 min)..." -ForegroundColor Yellow
$ok = $false
for ($i = 1; $i -le 24; $i++) {
    Start-Sleep -Seconds 20
    $h = Get-Health
    if (-not $h) {
        Write-Host "  intento $i : sin respuesta (cold start?)"
        continue
    }
    $bid = $h.data.build_id
    $git = $h.data.render_git_commit
    Write-Host "  intento $i : build_id=$bid git=$git"
    if ($bid -eq $expectedBuild) {
        $ok = $true
        break
    }
}

Write-Host ""
if ($ok) {
    Write-Host "Listo: API y front actualizados." -ForegroundColor Green
    Write-Host "  Portal: $frontUrl"
    Write-Host "  Health: $apiUrl"
    exit 0
}

Write-Host "El API aun NO tiene build_id=$expectedBuild" -ForegroundColor Red
Write-Host ""
Write-Host "Haz esto en Render (obligatorio si el hook no actualiza):" -ForegroundColor Yellow
Write-Host "  1. $renderPanel"
Write-Host "  2. Manual Deploy -> Deploy latest commit (NO Rollback a 10fe606)"
Write-Host "  3. Settings -> Auto-Deploy ON, repo main, root backend"
Write-Host ""
Write-Host "GitHub Actions (para el futuro):" -ForegroundColor Yellow
Write-Host "  Secretos: VERCEL_TOKEN y RENDER_DEPLOY_HOOK en $ghSecrets"
Write-Host "  Guia: docs\CONECTAR_GIT_VERCEL_RENDER.md"
Write-Host ""
exit 1
