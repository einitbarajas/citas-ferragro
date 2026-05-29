#Requires -Version 5.1
<#
  Deja correo y "Olvidé mi contraseña" funcionando en Render.

  Uso (recomendado):
    # Una vez: añade en .env → RENDER_API_KEY=rnd_...  (Render → Account → API Keys)
    .\scripts\dejar-correo-funcionando.ps1

  Sin API key: abre el panel para pegar smtp-render.env y desplegar.
#>
param(
    [string] $ApiKey = $env:RENDER_API_KEY,
    [switch] $SkipDeploy
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $repoRoot ".env"
$smtpExport = Join-Path $repoRoot "smtp-render.env"
$healthUrl = "https://ferragro-api.onrender.com/health"
$deepUrl = "https://ferragro-api.onrender.com/health/deep"
$serviceId = "srv-d82dvanaqgkc739362u0"

function Read-DotEnvKeys {
    param([string] $Path)
    $map = @{}
    if (-not (Test-Path -LiteralPath $Path)) { return $map }
    foreach ($line in Get-Content -LiteralPath $Path -Encoding UTF8) {
        $t = $line.Trim()
        if (-not $t -or $t.StartsWith("#")) { continue }
        if ($t -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$') {
            $map[$Matches[1]] = $Matches[2].Trim().Trim([char]0x22).Trim("'")
        }
    }
    return $map
}

function Get-ApiKey {
    param([string] $Explicit, [hashtable] $DotEnv)
    if ($Explicit -and $Explicit.Trim()) { return $Explicit.Trim() }
    if ($DotEnv["RENDER_API_KEY"] -and $DotEnv["RENDER_API_KEY"].Trim()) {
        return $DotEnv["RENDER_API_KEY"].Trim()
    }
    $keyFile = Join-Path $repoRoot ".render-api-key.local"
    if (Test-Path -LiteralPath $keyFile) {
        return (Get-Content -LiteralPath $keyFile -Raw).Trim()
    }
    return $null
}

function Wait-ProductionSmtp {
    param([string] $ExpectedBuildId, [int] $MaxAttempts = 30)
    for ($i = 1; $i -le $MaxAttempts; $i++) {
        Start-Sleep -Seconds 25
        try {
            $h = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 90
            $bid = $h.data.build_id
            Write-Host "  [$i] build_id=$bid"
            if ($ExpectedBuildId -and $bid -ne $ExpectedBuildId) { continue }
            $d = Invoke-RestMethod -Uri $deepUrl -TimeoutSec 120
            $login = $d.data.smtp_login_ok
            Write-Host "       smtp_login_ok=$login"
            if ($login -eq $true) {
                return $true
            }
        } catch {
            Write-Host "  [$i] API desplegando..."
        }
    }
    return $false
}

Write-Host ""
Write-Host "=== Dejar correo + recuperar contraseña en producción ===" -ForegroundColor Cyan
Write-Host ""

$dot = Read-DotEnvKeys -Path $envFile
if (-not $dot["SMTP_HOST"]) {
    throw "Falta SMTP_* en .env (SMTP_HOST, SMTP_USER, SMTP_PASSWORD, SMTP_FROM_EMAIL)."
}

& (Join-Path $repoRoot "scripts\configurar-smtp-render.ps1") -EnvFile $envFile -ApiKey $ApiKey -SkipDeploy:$SkipDeploy
if ($LASTEXITCODE -ne 0) {
    $ApiKey = Get-ApiKey -Explicit $ApiKey -DotEnv $dot
    if (-not $ApiKey) {
        Write-Host ""
        Write-Host "Añade RENDER_API_KEY en .env y vuelve a ejecutar este script," -ForegroundColor Yellow
        Write-Host "o pega smtp-render.env en Render → Environment → Secret File smtp.env → Manual Deploy." -ForegroundColor Yellow
        Start-Process "https://dashboard.render.com/web/$serviceId/env"
        exit 1
    }
}

$expectedBuild = "2026-05-29-forgot-password-v2"
$mainPy = Join-Path $repoRoot "backend\app\main.py"
if (Test-Path -LiteralPath $mainPy) {
    if ($mainPy -match 'API_BUILD_ID\s*=\s*"([^"]+)"') {
        $expectedBuild = $Matches[1]
    }
}

if (-not $SkipDeploy) {
    Write-Host ""
    Write-Host "Esperando build_id=$expectedBuild y smtp_login_ok=true ..." -ForegroundColor Cyan
    if (Wait-ProductionSmtp -ExpectedBuildId $expectedBuild) {
        Write-Host ""
        Write-Host "Listo: correo y recuperación de contraseña operativos en producción." -ForegroundColor Green
        exit 0
    }
}

Write-Host ""
Write-Host "SMTP subido o pendiente de deploy. Verifica Manual Deploy en Render." -ForegroundColor Yellow
Write-Host "  $deepUrl  → smtp_login_ok debe ser true"
exit 1
