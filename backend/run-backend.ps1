#Requires -Version 5.1
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

$marker = Join-Path $here ".venv_external"
if (Test-Path $marker) {
  $venvPath = (Get-Content $marker -Raw).Trim()
  $py = Join-Path $venvPath "Scripts\python.exe"
  if (Test-Path $py) {
    Write-Host "Usando venv externo: $venvPath" -ForegroundColor Cyan
    & $py $here\main.py @args
    exit $LASTEXITCODE
  }
}

Write-Host "No hay .venv_external o la ruta no existe. Ejecuta primero: .\setup-external-venv.ps1" -ForegroundColor Yellow
& py $here\main.py @args
