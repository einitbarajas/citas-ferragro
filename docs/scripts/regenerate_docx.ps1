#Requires -Version 5.1
<#
.SYNOPSIS
  Regenera los .docx de docs/ (requiere copias .md temporales o editar Word directamente).
  La documentacion oficial del proyecto esta en .docx; ver docs/README.txt.
#>
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Py = Join-Path $RepoRoot "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $Py)) {
  $Py = "python"
}

Push-Location $RepoRoot
try {
  & $Py -m pip install python-docx -q 2>$null

  Write-Host "=== Guía operación ===" -ForegroundColor Cyan
  & $Py (Join-Path $RepoRoot "docs\scripts\md_to_docx_guia.py")

  Write-Host "=== Operación continuidad ===" -ForegroundColor Cyan
  & $Py (Join-Path $RepoRoot "docs\scripts\md_to_docx_operacion.py")

  $PruebasScript = Join-Path $RepoRoot "scripts\pruebas_md_to_docx.py"
  $Pairs = @(
    @("docs\PRUEBAS.md", "docs\PRUEBAS.docx"),
    @("docs\CUMPLIMIENTO_REQ.md", "docs\CUMPLIMIENTO_REQ.docx"),
    @("docs\DICCIONARIO_DATOS_FERRAGRO.md", "docs\DICCIONARIO_DATOS_FERRAGRO.docx"),
    @("docs\MANUAL_USUARIO_PORTAL.md", "docs\MANUAL_USUARIO_Y_DOCUMENTACION.docx"),
    @("docs\INFORME_ANALISIS.md", "docs\INFORME DE ANALISIS.docx")
  )
  foreach ($pair in $Pairs) {
    Write-Host "=== $($pair[0]) ===" -ForegroundColor Cyan
    & $Py $PruebasScript $pair[0] $pair[1]
  }

  Write-Host "`n=== Documentos Word regenerados en docs/ ===" -ForegroundColor Green
}
finally {
  Pop-Location
}
