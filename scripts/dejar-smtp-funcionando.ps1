#Requires -Version 5.1
<#
  Deja el correo operativo en Render (SMTP en .env + Resend en producción).

  Render FREE bloquea Gmail SMTP; este script sube SMTP y, si indicas Resend, activa envío HTTPS.

  Uso:
    # 1) Añade en .env: RENDER_API_KEY=rnd_...
    # 2) Opcional: RESEND_API_KEY=re_... (resend.com/api-keys, sin dominio si RESEND_SANDBOX=true)
    .\scripts\dejar-smtp-funcionando.ps1
#>
$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $repoRoot ".env"

Write-Host ""
Write-Host "=== Dejar SMTP/correo funcionando en producción ===" -ForegroundColor Cyan
Write-Host ""

$map = @{}
foreach ($line in Get-Content -LiteralPath $envFile -Encoding UTF8) {
    $t = $line.Trim()
    if (-not $t -or $t.StartsWith("#")) { continue }
    if ($t -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$') {
        $map[$Matches[1]] = $Matches[2].Trim().Trim([char]0x22).Trim("'")
    }
}

if (-not $map["RESEND_API_KEY"] -or -not $map["RESEND_API_KEY"].Trim()) {
    Write-Host "Render FREE no permite Gmail SMTP (puerto 587)." -ForegroundColor Yellow
    Write-Host "Pega tu API key de Resend (solo API Keys, NO Domains):" -ForegroundColor Yellow
    $re = Read-Host "RESEND_API_KEY (re_...)"
    if ($re -and $re.Trim()) {
        $map["RESEND_API_KEY"] = $re.Trim()
        $map["RESEND_SANDBOX"] = "true"
        Add-Content -LiteralPath $envFile -Value ""
        Add-Content -LiteralPath $envFile -Value "RESEND_API_KEY=$($re.Trim())"
        Add-Content -LiteralPath $envFile -Value "RESEND_SANDBOX=true"
        Write-Host "Guardado en .env" -ForegroundColor Green
    }
}

& (Join-Path $repoRoot "scripts\configurar-smtp-render.ps1") -EnvFile $envFile
exit $LASTEXITCODE
