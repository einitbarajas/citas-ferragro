#Requires -Version 5.1
<#
  Despliegue a producción (Render API + recordatorio Vercel).
  Uso:
    .\scripts\deploy-produccion.ps1
    $env:RENDER_DEPLOY_HOOK = 'https://api.render.com/deploy/srv-...?key=...'
    .\scripts\deploy-produccion.ps1 -SkipGitPush
#>
param(
    [switch]$SkipGitPush
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$apiUrl = "https://ferragro-api.onrender.com"
$renderPanel = "https://dashboard.render.com/web/srv-d82dvanaqgkc739362u0"
$expectedBuild = "2026-05-21-unload-teams-v1"

Set-Location $repoRoot

if (-not $SkipGitPush) {
    $status = git status --porcelain
    if ($status) {
        Write-Host "Hay cambios sin commit. Haz commit y push antes, o usa -SkipGitPush." -ForegroundColor Yellow
        git status -sb
        exit 1
    }
    Write-Host "Rama actual:" (git branch --show-current) -ForegroundColor Cyan
    Write-Host "Ultimo commit:" (git log -1 --oneline) -ForegroundColor DarkGray
    $ahead = git rev-list --count origin/main..HEAD 2>$null
    if ([int]$ahead -gt 0) {
        Write-Host "Publicando $ahead commit(s) a origin/main..." -ForegroundColor Cyan
        git push origin main
    } else {
        Write-Host "main ya esta en origin. Si Render no actualizo, usa Deploy Hook o Manual Deploy." -ForegroundColor Yellow
    }
}

$hook = $env:RENDER_DEPLOY_HOOK
if ($hook) {
    Write-Host "Disparando deploy en Render..." -ForegroundColor Cyan
    Invoke-WebRequest -Uri $hook.Trim() -Method POST -UseBasicParsing | Out-Null
} else {
    Write-Host "RENDER_DEPLOY_HOOK no definido. Abre Render -> Manual Deploy -> Deploy latest commit" -ForegroundColor Yellow
    Start-Process $renderPanel
}

Write-Host ""
Write-Host "Vercel (frontend):" -ForegroundColor Cyan
Write-Host "  https://vercel.com/dashboard -> proyecto citas-ferragro -> Deployments -> Redeploy (Production)"
Write-Host ""
Write-Host "BD Render (solo si aun no corriste migraciones 016-019):" -ForegroundColor Cyan
Write-Host '  $env:DATABASE_URL = "<External Database URL de Render>"'
Write-Host "  .\db\run-database-all.ps1"
Write-Host "  .\db\run-database-crud.ps1"
Write-Host ""

Write-Host "Esperando API (puede tardar 3-5 min si estaba dormido)..." -ForegroundColor Cyan
for ($i = 1; $i -le 12; $i++) {
    Start-Sleep -Seconds 15
    try {
        $r = Invoke-RestMethod -Uri "$apiUrl/health" -Method GET -TimeoutSec 90
        $bid = $r.data.build_id
        Write-Host "  intento $i : build_id = $bid"
        if ($bid -eq $expectedBuild) {
            Write-Host "API en produccion actualizada ($expectedBuild)." -ForegroundColor Green
            exit 0
        }
    } catch {
        Write-Host "  intento $i : sin respuesta aun..." -ForegroundColor DarkGray
    }
}
Write-Host "El API aun no muestra $expectedBuild. Revisa Events en Render y vuelve a ejecutar este script." -ForegroundColor Yellow
exit 1
