#Requires -Version 5.1
<#
.SYNOPSIS
  Crea un entorno virtual FUERA de la carpeta del repo (evita bloqueos de antivirus/Defender en C:\dev).

.DESCRIPTION
  Si `pip.exe` o `_pydantic_core*.pyd` devuelven "Acceso denegado" dentro de `.venv312`/`.venv`,
  ejecuta este script una vez y luego activa el venv indicado al final.

  No modifica archivos del proyecto salvo backend\.venv_external (ruta al venv).
#>
$ErrorActionPreference = "Stop"
$backendRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$reqFile = Join-Path $backendRoot "requirements.txt"
if (-not (Test-Path $reqFile)) {
  throw "No se encuentra requirements.txt en: $backendRoot"
}

$venvRoot = Join-Path $env:USERPROFILE ".venvs"
$venvPath = Join-Path $venvRoot "ferragro-backend-py312"
New-Item -ItemType Directory -Force -Path $venvRoot | Out-Null

Write-Host "Entorno virtual destino: $venvPath" -ForegroundColor Cyan

$py = $null
foreach ($exe in @(
    (Join-Path ${env:LocalAppData} "Programs\Python\Python312\python.exe"),
    (Join-Path ${env:ProgramFiles} "Python312\python.exe")
  )) {
  if (Test-Path $exe) {
    $py = $exe
    break
  }
}
if (-not $py) {
  $pyVersion = & py -3.12 -c "import sys; print(sys.executable)" 2>$null
  if ($LASTEXITCODE -eq 0 -and $pyVersion) {
    $py = $pyVersion.Trim()
  }
}
if (-not $py -or -not (Test-Path $py)) {
  throw "No se encontró Python 3.12. Instálalo desde https://www.python.org/downloads/ o asegura que 'py -3.12' funcione."
}

Write-Host "Usando interprete: $py" -ForegroundColor Gray

if (Test-Path $venvPath) {
  Write-Host "Eliminando venv anterior en $venvPath ..." -ForegroundColor Yellow
  Remove-Item -Recurse -Force $venvPath
}

& $py -m venv $venvPath
if ($LASTEXITCODE -ne 0) {
  throw "Fallo al crear el venv con: $py -m venv"
}

$venvPython = Join-Path $venvPath "Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
  throw "No apareció Scripts\python.exe tras crear el venv."
}

Write-Host "Instalando pip y dependencias (puede tardar)..." -ForegroundColor Cyan
& $venvPython -m ensurepip --upgrade
& $venvPython -m pip install --upgrade pip setuptools wheel
& $venvPython -m pip install -r $reqFile
if ($LASTEXITCODE -ne 0) {
  throw "pip install falló. Revisa antivirus / exclusiones o ejecuta PowerShell como administrador."
}

$marker = Join-Path $backendRoot ".venv_external"
$venvPath | Set-Content -Path $marker -Encoding utf8
Write-Host ""
Write-Host "Listo. Ruta guardada en: $marker" -ForegroundColor Green
Write-Host ""
Write-Host "Activar en cada sesion:" -ForegroundColor Green
Write-Host "  Set-Location `"$backendRoot`""
Write-Host "  & `"$venvPath\Scripts\Activate.ps1`""
Write-Host ""
Write-Host "Arrancar API (reload desactivado por defecto; ver main.py):" -ForegroundColor Green
Write-Host "  .\run-backend.ps1"
Write-Host "  (o) & `"$venvPath\Scripts\python.exe`" `"$backendRoot\main.py`""
Write-Host "Hot-reload solo si hace falta y no bloquea DLLs: `$env:UVICORN_RELOAD='1'; .\run-backend.ps1"
