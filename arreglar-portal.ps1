# Arreglo produccion: esquema BD (014-022) + admin login.
Write-Host "Paso 1/2: migraciones BD Render (IdBodega, AdminBodega, muelles)..." -ForegroundColor Cyan
& (Join-Path $PSScriptRoot "db\arreglar-esquema-produccion.ps1")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "`nPaso 2/2: credencial admin..." -ForegroundColor Cyan
& (Join-Path $PSScriptRoot "db\ejecutar-ENTRAR-AHORA.ps1")
