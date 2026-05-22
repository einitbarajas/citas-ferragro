#Requires -Version 5.1
<#
  Un solo script para dejar produccion al dia.
  - Vercel: despliega con CLI (usa tu sesion vercel login).
  - Render: usa RENDER_DEPLOY_HOOK o te pide la URL una vez.

  Uso:
    .\scripts\poner-produccion-actual.ps1
    .\scripts\poner-produccion-actual.ps1 -HookUrl "https://api.render.com/deploy/srv-...?key=..."
#>
param(
    [string]$HookUrl = $env:RENDER_DEPLOY_HOOK
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$apiHealth = "https://ferragro-api.onrender.com/health"
$frontUrl = "https://frontend-ferragro.vercel.app"
$renderPanel = "https://dashboard.render.com/web/srv-d82dvanaqgkc739362u0"

Set-Location $repoRoot

$expectedBuild = (Select-String "backend\app\main.py" -Pattern '^API_BUILD_ID').Line
if ($expectedBuild -match '"([^"]+)"') { $expectedBuild = $Matches[1] }

Write-Host ""
Write-Host "=== Poner produccion actual (Ferragro) ===" -ForegroundColor Cyan
Write-Host "build_id esperado: $expectedBuild"
Write-Host "Git:" (git log -1 --oneline)
Write-Host ""

# --- Git push si hay cambios ---
$dirty = git status --porcelain
if ($dirty) {
    Write-Host "Hay cambios locales sin commit. Haz commit antes o descarta." -ForegroundColor Yellow
    git status -sb
    exit 1
}
$ahead = [int](git rev-list --count origin/main..HEAD 2>$null)
if ($ahead -gt 0) {
    Write-Host "Publicando $ahead commit(s) a GitHub..."
    git push origin main
}

# --- Vercel ---
Write-Host "[1/2] Vercel frontend..." -ForegroundColor Yellow
Set-Location (Join-Path $repoRoot "frontend")
npx vercel@54.4.0 deploy --prod --yes 2>&1 | Out-Host
Write-Host "  -> $frontUrl" -ForegroundColor Green
Set-Location $repoRoot

# --- Render ---
Write-Host ""
Write-Host "[2/2] Render API..." -ForegroundColor Yellow
if (-not $HookUrl) {
    Write-Host ""
    Write-Host "Pega la Deploy Hook URL de Render (Settings -> Deploy Hook -> Create Hook):" -ForegroundColor Cyan
    Write-Host "  Panel: $renderPanel" -ForegroundColor DarkGray
    $HookUrl = Read-Host "RENDER_DEPLOY_HOOK"
}
if (-not $HookUrl) {
    Write-Host "Sin hook: abre Render -> Manual Deploy -> Deploy latest commit" -ForegroundColor Yellow
    Start-Process $renderPanel
    exit 1
}

Write-Host "  Disparando deploy..."
Invoke-WebRequest -Uri $HookUrl.Trim() -Method POST -UseBasicParsing | Out-Null

Write-Host "  Esperando /health (max 8 min)..."
for ($i = 1; $i -le 24; $i++) {
    Start-Sleep -Seconds 20
    try {
        $h = Invoke-RestMethod $apiHealth -TimeoutSec 120
        $bid = $h.data.build_id
        Write-Host "  $i : $bid"
        if ($bid -eq $expectedBuild) {
            Write-Host ""
            Write-Host "Produccion actualizada." -ForegroundColor Green
            Write-Host "  Portal: $frontUrl"
            Write-Host "  API:    $apiHealth"
            Write-Host ""
            Write-Host "Guarda el hook para no pegarlo cada vez:" -ForegroundColor DarkGray
            Write-Host '  [Environment]::SetEnvironmentVariable("RENDER_DEPLOY_HOOK","' + $HookUrl.Trim() + '","User")'
            exit 0
        }
    } catch {
        Write-Host "  $i : esperando..."
    }
}

Write-Host ""
Write-Host "El API aun no muestra $expectedBuild." -ForegroundColor Red
Write-Host "Render -> Events: busca Build failed. Si falla, copia el log." -ForegroundColor Yellow
Start-Process $renderPanel
exit 1
