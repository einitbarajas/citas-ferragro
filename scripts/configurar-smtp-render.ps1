#Requires -Version 5.1
<#
  Configura SMTP en Render (ferragro-api) leyendo variables desde .env del repo.
  Requiere API key: https://dashboard.render.com/u/settings#api-keys

  Uso:
    $env:RENDER_API_KEY = "rnd_..."
    .\scripts\configurar-smtp-render.ps1

    # o guardar la key en .render-api-key.local (una linea, no se sube a Git)
    .\scripts\configurar-smtp-render.ps1
#>
param(
    [string] $ApiKey = $env:RENDER_API_KEY,
    [string] $ServiceId = "srv-d82dvanaqgkc739362u0",
    [string] $EnvFile = "",
    [switch] $SkipDeploy
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($EnvFile)) {
    $EnvFile = Join-Path $repoRoot ".env"
}

function Read-DotEnv {
    param([string] $Path)
    $map = @{}
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "No existe: $Path"
    }
    foreach ($line in Get-Content -LiteralPath $Path -Encoding UTF8) {
        $t = $line.Trim()
        if (-not $t -or $t.StartsWith("#")) { continue }
        if ($t -notmatch "^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$") { continue }
        $k = $Matches[1]
        $v = $Matches[2].Trim().Trim([char]0x22).Trim("'")
        $map[$k] = $v
    }
    return $map
}

function Get-ApiKey {
    param([string] $Explicit, [hashtable] $DotEnv = @{})
    if (-not [string]::IsNullOrWhiteSpace($Explicit)) { return $Explicit.Trim() }
    if ($DotEnv["RENDER_API_KEY"] -and $DotEnv["RENDER_API_KEY"].Trim()) {
        return $DotEnv["RENDER_API_KEY"].Trim()
    }
    $keyFile = Join-Path $repoRoot ".render-api-key.local"
    if (Test-Path -LiteralPath $keyFile) {
        $fromFile = (Get-Content -LiteralPath $keyFile -Raw).Trim()
        if ($fromFile) { return $fromFile }
    }
    return $null
}

function Set-RenderSecretFile {
    param(
        [string] $FileName,
        [string] $Content,
        [string] $Token,
        [string] $Service
    )
    $uri = "https://api.render.com/v1/services/$Service/secret-files/$FileName"
    $body = @{ name = $FileName; content = $Content } | ConvertTo-Json -Compress
    $headers = @{
        Authorization = "Bearer $Token"
        Accept        = "application/json"
        "Content-Type" = "application/json"
    }
    Invoke-RestMethod -Uri $uri -Method Put -Headers $headers -Body $body | Out-Null
}

function Set-RenderEnvVar {
    param(
        [string] $Key,
        [string] $Value,
        [string] $Token,
        [string] $Service
    )
    $uri = "https://api.render.com/v1/services/$Service/env-vars/$Key"
    $body = (@{ key = $Key; value = $Value } | ConvertTo-Json -Compress)
    $headers = @{
        Authorization = "Bearer $Token"
        Accept        = "application/json"
        "Content-Type" = "application/json"
    }
    Invoke-RestMethod -Uri $uri -Method Put -Headers $headers -Body $body | Out-Null
}

function Invoke-RenderDeployHook {
    param([string] $RepoRoot, [hashtable] $DotEnv = @{})
    $hookFile = Join-Path $RepoRoot ".render-hook.local"
    $hook = $env:RENDER_DEPLOY_HOOK
    if (-not $hook -and $DotEnv["RENDER_DEPLOY_HOOK"]) {
        $hook = $DotEnv["RENDER_DEPLOY_HOOK"].Trim()
    }
    if (-not $hook -and (Test-Path -LiteralPath $hookFile)) {
        $hook = (Get-Content -LiteralPath $hookFile -Raw).Trim()
    }
    if ([string]::IsNullOrWhiteSpace($hook)) { return $false }
    Invoke-WebRequest -Uri $hook -Method POST -UseBasicParsing | Out-Null
    return $true
}

function Invoke-RenderApiDeploy {
    param([string] $Token, [string] $Service)
    $uri = "https://api.render.com/v1/services/$Service/deploys"
    $headers = @{
        Authorization  = "Bearer $Token"
        Accept         = "application/json"
        "Content-Type" = "application/json"
    }
    Invoke-RestMethod -Uri $uri -Method Post -Headers $headers -Body "{}" | Out-Null
}

function Wait-EmailEnabled {
    param([int] $MaxAttempts = 24, [string] $ExpectedBuildId = "")
    $healthUrl = "https://ferragro-api.onrender.com/health"
    $deepUrl = "https://ferragro-api.onrender.com/health/deep"
    for ($i = 1; $i -le $MaxAttempts; $i++) {
        Start-Sleep -Seconds 20
        try {
            $h = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 90
            $enabled = $h.data.email_enabled
            $smtpHost = $h.data.smtp_host
            $buildId = $h.data.build_id
            Write-Host "  intento $i : email_enabled=$enabled build_id=$buildId"
            if ($ExpectedBuildId -and $buildId -ne $ExpectedBuildId) { continue }
            if ($enabled) {
                try {
                    $d = Invoke-RestMethod -Uri $deepUrl -TimeoutSec 120
                    $loginOk = $d.data.smtp_login_ok
                    Write-Host "           smtp_login_ok=$loginOk"
                    if ($loginOk -eq $true) { return $h.data }
                } catch {
                    Write-Host "           /health/deep aun no disponible"
                }
                if (-not $ExpectedBuildId) { return $h.data }
            }
        } catch {
            Write-Host "  intento $i : API aun desplegando..."
        }
    }
    return $null
}

$smtpRenderPath = Join-Path $repoRoot "smtp-render.env"
if (-not (Test-Path -LiteralPath $EnvFile)) {
    if (Test-Path -LiteralPath $smtpRenderPath) {
        $EnvFile = $smtpRenderPath
        Write-Host "Usando $smtpRenderPath (no hay .env con SMTP)." -ForegroundColor Cyan
    }
}
$envMap = Read-DotEnv -Path $EnvFile
$required = @("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM_EMAIL")
$missing = @($required | Where-Object { [string]::IsNullOrWhiteSpace($envMap[$_]) })
if ($missing.Count -gt 0 -and (Test-Path -LiteralPath $smtpRenderPath)) {
    $smtpMap = Read-DotEnv -Path $smtpRenderPath
    foreach ($k in $required) {
        if ([string]::IsNullOrWhiteSpace($envMap[$k]) -and $smtpMap[$k]) {
            $envMap[$k] = $smtpMap[$k]
        }
    }
    $missing = @($required | Where-Object { [string]::IsNullOrWhiteSpace($envMap[$_]) })
}
foreach ($k in $missing) {
    throw "Falta $k en $EnvFile (o en smtp-render.env)"
}

$toSet = @{
    SMTP_PROFILE      = if ($envMap["SMTP_PROFILE"]) { $envMap["SMTP_PROFILE"] } else { "gmail" }
    SMTP_HOST         = $envMap["SMTP_HOST"]
    SMTP_PORT         = if ($envMap["SMTP_PORT"]) { $envMap["SMTP_PORT"] } else { "587" }
    SMTP_USER         = $envMap["SMTP_USER"]
    SMTP_PASSWORD     = ($envMap["SMTP_PASSWORD"] -replace '\s', '')
    SMTP_FROM_EMAIL   = $envMap["SMTP_FROM_EMAIL"]
    SMTP_FROM_NAME    = if ($envMap["SMTP_FROM_NAME"]) { $envMap["SMTP_FROM_NAME"] } else { "Ferragro" }
    SMTP_USE_TLS      = if ($null -ne $envMap["SMTP_USE_TLS"]) { $envMap["SMTP_USE_TLS"] } else { "true" }
    SMTP_USE_SSL      = if ($null -ne $envMap["SMTP_USE_SSL"]) { $envMap["SMTP_USE_SSL"] } else { "false" }
}
if ($toSet["SMTP_FROM_EMAIL"] -ne $toSet["SMTP_USER"]) {
    Write-Host "Aviso: SMTP_FROM_EMAIL se igualara a SMTP_USER (requerido por Gmail)." -ForegroundColor Yellow
    $toSet["SMTP_FROM_EMAIL"] = $toSet["SMTP_USER"]
}
if ($envMap["SMTP_REPLY_TO"]) { $toSet["SMTP_REPLY_TO"] = $envMap["SMTP_REPLY_TO"] }
if ($envMap["SMTP_PROFILE"]) { $toSet["SMTP_PROFILE"] = $envMap["SMTP_PROFILE"] }

$ApiKey = Get-ApiKey -Explicit $ApiKey -DotEnv $envMap
if ($envMap["RENDER_DEPLOY_HOOK"] -and -not $env:RENDER_DEPLOY_HOOK) {
    $env:RENDER_DEPLOY_HOOK = $envMap["RENDER_DEPLOY_HOOK"].Trim()
}
$exportPath = Join-Path $repoRoot "smtp-render.env"
$lines = @()
foreach ($entry in $toSet.GetEnumerator() | Sort-Object Name) {
    $lines += "$($entry.Key)=$($entry.Value)"
}
$smtpFileBody = $lines -join "`n"
[System.IO.File]::WriteAllText($exportPath, $smtpFileBody, [System.Text.UTF8Encoding]::new($false))

if (-not $ApiKey) {
    $clipPath = Join-Path $repoRoot "ARREGLAR-CORREO-AHORA.md"
    if (Test-Path -LiteralPath $clipPath) { Start-Process $clipPath }
    Write-Host ""
    Write-Host "Falta RENDER_API_KEY. Archivo listo:" -ForegroundColor Yellow
    Write-Host "  $exportPath"
    Write-Host ""
    Write-Host "Opcion A (1 min): Render -> ferragro-api -> Environment -> Add from .env -> smtp-render.env -> Save"
    Write-Host "Opcion B: Secret File nombre smtp.env con el mismo contenido (el API lo lee en /etc/secrets/smtp.env)"
    Write-Host ""
    Write-Host "Para automatizar: API key en https://dashboard.render.com/u/settings#api-keys" -ForegroundColor Cyan
    Write-Host '  Añade en .env: RENDER_API_KEY=rnd_...  (o $env:RENDER_API_KEY = "rnd_...")'
    Write-Host "  .\scripts\configurar-smtp-render.ps1"
    Start-Process "https://dashboard.render.com/web/$ServiceId/env"
    exit 1
}

Write-Host "Configurando SMTP en Render ($ServiceId)..." -ForegroundColor Cyan
foreach ($entry in $toSet.GetEnumerator()) {
    Set-RenderEnvVar -Key $entry.Key -Value $entry.Value -Token $ApiKey -Service $ServiceId
    Write-Host "  OK env $($entry.Key)"
}
try {
    Set-RenderSecretFile -FileName "smtp.env" -Content $smtpFileBody -Token $ApiKey -Service $ServiceId
    Write-Host "  OK secret file smtp.env"
} catch {
    Write-Host "  Aviso: no se pudo subir secret file (las env vars SMTP siguen aplicadas)." -ForegroundColor Yellow
}

if (-not $SkipDeploy) {
    $deployed = $false
    if (Invoke-RenderDeployHook -RepoRoot $repoRoot -DotEnv $envMap) {
        Write-Host "Deploy disparado (hook)." -ForegroundColor Green
        $deployed = $true
    }
    try {
        Invoke-RenderApiDeploy -Token $ApiKey -Service $ServiceId
        Write-Host "Deploy disparado (Render API)." -ForegroundColor Green
        $deployed = $true
    } catch {
        if (-not $deployed) {
            Write-Host "Sin deploy hook/API: haz Manual Deploy en Render." -ForegroundColor Yellow
            Start-Process "https://dashboard.render.com/web/$ServiceId"
        }
    }
    $expectedBuild = ""
    $mainPy = Join-Path $repoRoot "backend\app\main.py"
    if (Test-Path -LiteralPath $mainPy) {
        $content = Get-Content -LiteralPath $mainPy -Raw
        if ($content -match 'API_BUILD_ID\s*=\s*"([^"]+)"') { $expectedBuild = $Matches[1] }
    }
    Write-Host "Esperando email_enabled y smtp_login_ok en /health..."
    $ok = Wait-EmailEnabled -ExpectedBuildId $expectedBuild
    if ($ok) {
        Write-Host "Correo activo en produccion." -ForegroundColor Green
        exit 0
    }
    Write-Host "Variables guardadas; el API aun no muestra email_enabled. Revisa deploy en Render." -ForegroundColor Yellow
    exit 1
}

Write-Host "Variables SMTP guardadas (sin redeploy)." -ForegroundColor Green
