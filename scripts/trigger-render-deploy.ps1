# Dispara deploy en Render usando Deploy Hook (una sola vez por ejecución).
# Uso:
#   $env:RENDER_DEPLOY_HOOK = "https://api.render.com/deploy/srv-...?key=..."
#   .\scripts\trigger-render-deploy.ps1

$hook = $env:RENDER_DEPLOY_HOOK
if (-not $hook) {
    Write-Host "Define RENDER_DEPLOY_HOOK con la URL del Deploy Hook de Render." -ForegroundColor Yellow
    Write-Host "Render -> ferragro-api -> Settings -> Deploy Hook -> Create Hook"
    exit 1
}
Invoke-WebRequest -Uri $hook -Method POST -UseBasicParsing | Out-Null
Write-Host "Deploy solicitado. Revisa Events en:" -ForegroundColor Green
Write-Host "https://dashboard.render.com/web/srv-d82dvanaqgkc739362u0"
