#Requires -Version 5.1
<#
  Arregla producción: SMTP en Render + deploy + verificación.
  Requiere en .env: RENDER_API_KEY=rnd_...
  Uso: .\scripts\arreglar-produccion-ahora.ps1
#>
$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$serviceId = "srv-d82dvanaqgkc739362u0"
$healthUrl = "https://ferragro-api.onrender.com/health"
$deepUrl = "https://ferragro-api.onrender.com/health/deep"

Write-Host ""
Write-Host "=== Arreglar producción (SMTP + deploy) ===" -ForegroundColor Cyan
Write-Host ""

& (Join-Path $repoRoot "scripts\configurar-smtp-render.ps1") -EnvFile (Join-Path $repoRoot ".env")
if ($LASTEXITCODE -ne 0) {
    $smtpPath = Join-Path $repoRoot "smtp-render.env"
    if (Test-Path $smtpPath) {
        Set-Clipboard -Value (Get-Content -LiteralPath $smtpPath -Raw)
        Write-Host "smtp-render.env copiado al portapapeles." -ForegroundColor Green
    }
    Write-Host ""
    Write-Host "Sin RENDER_API_KEY en .env:" -ForegroundColor Yellow
    Write-Host "  1. Render -> ferragro-api -> Secret File smtp.env -> pegar smtp-render.env -> Save"
    Write-Host "  2. Manual Deploy -> Deploy latest commit"
    Write-Host "  3. Vercel -> Redeploy frontend -> Ctrl+F5 en citas"
    Start-Process "https://dashboard.render.com/web/$serviceId/env"
    exit 1
}

$mainPy = Join-Path $repoRoot "backend\app\main.py"
$expectedBuild = "2026-05-29-fast-recovery-v1"
if (Test-Path $mainPy) {
    $c = Get-Content -LiteralPath $mainPy -Raw
    if ($c -match 'API_BUILD_ID\s*=\s*"([^"]+)"') { $expectedBuild = $Matches[1] }
}

Write-Host ""
Write-Host "Esperando build_id=$expectedBuild y smtp_login_ok=true ..." -ForegroundColor Cyan
for ($i = 1; $i -le 36; $i++) {
    Start-Sleep -Seconds 20
    try {
        $h = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 90
        $bid = $h.data.build_id
        Write-Host "  [$i] build_id=$bid"
        if ($bid -ne $expectedBuild) { continue }
        $d = Invoke-RestMethod -Uri $deepUrl -TimeoutSec 120
        $login = $d.data.smtp_login_ok
        Write-Host "       smtp_login_ok=$login profile=$($d.data.smtp_profile)"
        if ($login -eq $true) {
            Write-Host ""
            Write-Host "Producción OK. Prueba olvidé contraseña y login en citas.ferragro.vercel.app" -ForegroundColor Green
            exit 0
        }
    } catch {
        Write-Host "  [$i] desplegando..."
    }
}

Write-Host ""
Write-Host "Variables SMTP subidas; deploy puede tardar. Haz Manual Deploy si hace falta." -ForegroundColor Yellow
Write-Host "  $deepUrl"
exit 1
