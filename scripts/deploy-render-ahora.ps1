#Requires -Version 5.1
<#
  Dispara deploy del API en Render.
  Opción A: variable RENDER_DEPLOY_HOOK (Render → ferragro-api → Settings → Deploy Hook)
  Opción B: abre el panel para Manual Deploy
#>
$ErrorActionPreference = "Stop"
$hook = $env:RENDER_DEPLOY_HOOK
$panel = "https://dashboard.render.com/web/srv-d82dvanaqgkc739362u0"

if (-not [string]::IsNullOrWhiteSpace($hook)) {
    Write-Host "Solicitando deploy en Render..." -ForegroundColor Cyan
    Invoke-WebRequest -Uri $hook.Trim() -Method POST -UseBasicParsing | Out-Null
    Write-Host "Deploy iniciado. Espera 3-5 min y revisa:" -ForegroundColor Green
    Write-Host "  https://ferragro-api.onrender.com/health" -ForegroundColor DarkGray
    Write-Host "  (build_id debe ser 2026-05-19-deploy-main o mas reciente)" -ForegroundColor DarkGray
    exit 0
}

Write-Host "RENDER_DEPLOY_HOOK no esta configurado." -ForegroundColor Yellow
Write-Host @"

1. Abre: $panel
2. Clic en "Manual Deploy" → "Deploy latest commit"
3. Espera estado Live (3-5 min)
4. Verifica: https://ferragro-api.onrender.com/health

Para automatizar en el futuro:
  Render → ferragro-api → Settings → Deploy Hook → Create Hook
  PowerShell:
    `$env:RENDER_DEPLOY_HOOK = 'https://api.render.com/deploy/srv-...?key=...'
    .\scripts\deploy-render-ahora.ps1

"@ -ForegroundColor DarkGray
Start-Process $panel
exit 1
