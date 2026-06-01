#Requires -Version 5.1
<#
  Activa correo: sube secrets a GitHub + Render y despliega.
  Requiere: gh auth login, RENDER_API_KEY en .env o -RenderApiKey
#>
param([string] $RenderApiKey = "")

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot

function Read-DotEnv([string] $Path) {
    $map = @{}
    if (-not (Test-Path $Path)) { return $map }
    foreach ($line in Get-Content -LiteralPath $Path -Encoding UTF8) {
        $t = $line.Trim()
        if (-not $t -or $t.StartsWith("#")) { continue }
        if ($t -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$') {
            $map[$Matches[1]] = $Matches[2].Trim().Trim([char]0x22).Trim("'")
        }
    }
    return $map
}

$map = Read-DotEnv (Join-Path $repoRoot ".env")
$smtp = Read-DotEnv (Join-Path $repoRoot "smtp-render.env")
foreach ($k in $smtp.Keys) {
    if (-not $map[$k]) { $map[$k] = $smtp[$k] }
}

if (-not $RenderApiKey) {
    $RenderApiKey = $map["RENDER_API_KEY"]
    if (-not $RenderApiKey -and (Test-Path (Join-Path $repoRoot ".render-api-key.local"))) {
        $RenderApiKey = (Get-Content (Join-Path $repoRoot ".render-api-key.local") -Raw).Trim()
    }
}
if (-not $RenderApiKey) {
    Write-Host "Pega RENDER_API_KEY (rnd_...) de https://dashboard.render.com/u/settings#api-keys" -ForegroundColor Yellow
    $RenderApiKey = Read-Host "RENDER_API_KEY"
}
if (-not $RenderApiKey) { throw "Sin RENDER_API_KEY no se puede configurar Render." }

if (-not $map["RESEND_API_KEY"]) { throw "Falta RESEND_API_KEY en .env o smtp-render.env" }

Set-Content -LiteralPath (Join-Path $repoRoot ".render-api-key.local") -Value $RenderApiKey.Trim() -NoNewline
$env:RENDER_API_KEY = $RenderApiKey.Trim()

# 1) Render directo (más rápido)
Write-Host "`n[1/2] Subiendo a Render..." -ForegroundColor Cyan
python (Join-Path $repoRoot "scripts\push_resend_to_render.py")
if ($LASTEXITCODE -eq 0) {
    Write-Host "`nCorreo activo en Render." -ForegroundColor Green
    exit 0
}

# 2) GitHub Actions (respaldo)
Write-Host "`n[2/2] Intentando GitHub Actions..." -ForegroundColor Cyan
try {
    gh auth status | Out-Null
} catch {
    Write-Host "gh no autenticado. Usa Manual Deploy tras pegar smtp-render.env en Render." -ForegroundColor Yellow
    & (Join-Path $repoRoot "scripts\abrir-render-correo.ps1")
    exit 1
}

$secrets = @{
    RENDER_API_KEY  = $RenderApiKey.Trim()
    SMTP_HOST       = $map["SMTP_HOST"]
    SMTP_USER       = $map["SMTP_USER"]
    SMTP_PASSWORD   = ($map["SMTP_PASSWORD"] -replace '\s', '')
    SMTP_FROM_EMAIL = $map["SMTP_FROM_EMAIL"]
    RESEND_API_KEY  = $map["RESEND_API_KEY"].Trim()
    RESEND_SANDBOX  = if ($map["RESEND_SANDBOX"]) { $map["RESEND_SANDBOX"] } else { "true" }
}
foreach ($e in $secrets.GetEnumerator()) {
    $e.Value | gh secret set $e.Key
    Write-Host "OK secret $($e.Key)"
}
gh workflow run "Sync SMTP to Render"
gh workflow run "Deploy Render API"
Write-Host "Ejecuta: gh run watch" -ForegroundColor Cyan
