#Requires -Version 5.1
<#
  Copia smtp-render.env al portapapeles y abre Render para pegarlo en Secret File smtp.env.
  Uso: .\scripts\pegar-smtp-en-render.ps1
#>
$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$smtpPath = Join-Path $repoRoot "smtp-render.env"
$serviceId = "srv-d82dvanaqgkc739362u0"

if (-not (Test-Path -LiteralPath $smtpPath)) {
    throw "No existe smtp-render.env en la raíz del repo."
}

Set-Clipboard -Value (Get-Content -LiteralPath $smtpPath -Raw)
Write-Host ""
Write-Host "smtp-render.env copiado al portapapeles." -ForegroundColor Green
Write-Host ""
Write-Host "En Render (ferragro-api):" -ForegroundColor Cyan
Write-Host "  1. Environment -> Secret Files -> smtp.env -> pegar -> Save"
Write-Host "  2. Manual Deploy -> Deploy latest commit"
Write-Host "  3. Espera 2-3 min y prueba en citas.ferragro.vercel.app"
Write-Host ""
Write-Host "Correo de cuenta registrado: nataliabarajas412@gmail.com (una sola L en natalia)." -ForegroundColor Yellow
Start-Process "https://dashboard.render.com/web/$serviceId/env"
