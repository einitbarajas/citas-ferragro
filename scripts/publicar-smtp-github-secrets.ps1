#Requires -Version 5.1
<#
  Publica variables SMTP en GitHub Actions (una vez) y dispara sync-smtp-to-render.

  Requiere: gh auth login
  Uso: .\scripts\publicar-smtp-github-secrets.ps1
#>
$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $repoRoot ".env"

function Read-DotEnv {
    param([string] $Path)
    $map = @{}
    foreach ($line in Get-Content -LiteralPath $Path -Encoding UTF8) {
        $t = $line.Trim()
        if (-not $t -or $t.StartsWith("#")) { continue }
        if ($t -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$') {
            $map[$Matches[1]] = $Matches[2].Trim().Trim([char]0x22).Trim("'")
        }
    }
    return $map
}

$map = Read-DotEnv -Path $envFile
$required = @("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM_EMAIL")
foreach ($k in $required) {
    if ([string]::IsNullOrWhiteSpace($map[$k])) {
        throw "Falta $k en .env"
    }
}
if ([string]::IsNullOrWhiteSpace($map["RENDER_API_KEY"])) {
    throw "Falta RENDER_API_KEY en .env (Render → API Keys)."
}

gh auth status | Out-Null

$secrets = @{
    RENDER_API_KEY   = $map["RENDER_API_KEY"]
    SMTP_HOST        = $map["SMTP_HOST"]
    SMTP_USER        = $map["SMTP_USER"]
    SMTP_PASSWORD    = ($map["SMTP_PASSWORD"] -replace '\s', '')
    SMTP_FROM_EMAIL  = $map["SMTP_FROM_EMAIL"]
    SMTP_PORT        = if ($map["SMTP_PORT"]) { $map["SMTP_PORT"] } else { "587" }
    SMTP_FROM_NAME   = if ($map["SMTP_FROM_NAME"]) { $map["SMTP_FROM_NAME"] } else { "Ferragro" }
    SMTP_USE_TLS     = if ($map["SMTP_USE_TLS"]) { $map["SMTP_USE_TLS"] } else { "true" }
}
if ($map["RENDER_DEPLOY_HOOK"]) { $secrets["RENDER_DEPLOY_HOOK"] = $map["RENDER_DEPLOY_HOOK"] }
if ($map["RESEND_API_KEY"]) {
    $secrets["RESEND_API_KEY"] = $map["RESEND_API_KEY"].Trim()
    $secrets["RESEND_SANDBOX"] = if ($map["RESEND_SANDBOX"]) { $map["RESEND_SANDBOX"] } else { "true" }
}

foreach ($entry in $secrets.GetEnumerator()) {
    $entry.Value | gh secret set $entry.Key
    Write-Host "OK secret $($entry.Key)"
}

Write-Host "Disparando workflow Sync SMTP to Render..." -ForegroundColor Cyan
gh workflow run "Sync SMTP to Render"
Write-Host "Sigue el progreso: gh run watch"
