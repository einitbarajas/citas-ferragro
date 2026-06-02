# Dispara deploy de ferragro-api en Render (lee .env o .render-hook.local).
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$hook = $env:RENDER_DEPLOY_HOOK
if (-not $hook -and (Test-Path "$root\.render-hook.local")) {
    $hook = (Get-Content "$root\.render-hook.local" -Raw).Trim()
}
if (-not $hook -and (Test-Path "$root\.env")) {
    foreach ($line in Get-Content "$root\.env") {
        if ($line -match '^\s*RENDER_DEPLOY_HOOK\s*=\s*(.+)\s*$') {
            $hook = $Matches[1].Trim().Trim('"').Trim("'")
            break
        }
    }
}
if (-not $hook) {
    Write-Host "Sin RENDER_DEPLOY_HOOK. Render -> ferragro-api -> Manual Deploy -> Deploy latest commit" -ForegroundColor Yellow
    Write-Host "Panel: https://dashboard.render.com/web/srv-d82dvanaqgkc739362u0"
    exit 1
}
Invoke-WebRequest -Uri $hook.Trim() -Method POST -UseBasicParsing | Out-Null
Write-Host "Deploy solicitado en Render. Espera 3-5 min y comprueba:" -ForegroundColor Green
Write-Host "https://ferragro-api.onrender.com/health  -> build_id: 2026-06-02-appointments-fix-v2"
