#Requires -Version 5.1
<#
  Prepara correo en Render: genera smtp-render.env, abre el panel y opcionalmente sube con API key.

  Uso:
    .\scripts\activar-correo-ahora.ps1
    $env:RENDER_API_KEY = "rnd_..."
    .\scripts\activar-correo-ahora.ps1 -SubirAutomatico
#>
param([switch] $SubirAutomatico)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$exportPath = Join-Path $repoRoot "smtp-render.env"
$renderEnv = "https://dashboard.render.com/web/srv-d82dvanaqgkc739362u0/env"
$health = "https://ferragro-api.onrender.com/health"

Write-Host ""
Write-Host "=== Activar correo en Render (Ferragro) ===" -ForegroundColor Cyan
Write-Host ""

& (Join-Path $repoRoot "scripts\configurar-smtp-render.ps1")
if ($LASTEXITCODE -ne 0 -and -not $SubirAutomatico) {
    Write-Host ""
    Write-Host "Paso manual obligatorio:" -ForegroundColor Yellow
    Write-Host "  1. En el panel que se abrio: Add from .env"
    Write-Host "  2. Archivo: $exportPath"
    Write-Host "  3. Save Changes -> espera deploy Live"
    Write-Host "  4. Manual Deploy -> Deploy latest commit (main)"
    Write-Host "  5. Verifica: $health"
    try {
        Set-Clipboard -Path $exportPath
        Write-Host ""
        Write-Host "Ruta copiada al portapapeles." -ForegroundColor Green
    } catch {
        Write-Host "Copia manualmente la ruta del archivo .env." -ForegroundColor DarkGray
    }
    exit 1
}

if ($SubirAutomatico -or $env:RENDER_API_KEY) {
    & (Join-Path $repoRoot "scripts\configurar-smtp-render.ps1")
}

Write-Host ""
Write-Host "Comprobando $health ..." -ForegroundColor Cyan
try {
    $h = Invoke-RestMethod -Uri $health -TimeoutSec 90
    $d = $h.data
    Write-Host "  build_id       : $($d.build_id)"
    Write-Host "  email_enabled  : $($d.email_enabled)"
    Write-Host "  smtp_host      : $($d.smtp_host)"
    if ($d.email_enabled) {
        Write-Host ""
        Write-Host "Correo activo en Render." -ForegroundColor Green
        exit 0
    }
} catch {
    Write-Host "  No se pudo leer /health (cold start?)." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Si email_enabled sigue en false:" -ForegroundColor Yellow
Write-Host "  - Importa smtp-render.env en Render Environment"
Write-Host "  - Manual Deploy del ultimo commit en main"
Write-Host "  - Vercel no envia correos; solo necesita VITE_API_URL al API"
exit 1
