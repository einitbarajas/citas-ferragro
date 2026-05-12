param(
  [switch]$InstallFrontend
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $root "backend"
$frontendDir = Join-Path $root "frontend"

if (-not (Test-Path $backendDir)) {
  throw "No se encontro la carpeta backend en $backendDir"
}
if (-not (Test-Path $frontendDir)) {
  throw "No se encontro la carpeta frontend en $frontendDir"
}

function Stop-ListeningProcess {
  param(
    [Parameter(Mandatory = $true)]
    [int]$Port
  )

  $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
  if (-not $connections) {
    return
  }

  $pids = $connections |
    Select-Object -ExpandProperty OwningProcess -Unique |
    Where-Object { $_ -and $_ -ne 0 }

  foreach ($pid in $pids) {
    try {
      $proc = Get-Process -Id $pid -ErrorAction Stop
      Write-Host "Liberando puerto $Port (PID $pid - $($proc.ProcessName))..." -ForegroundColor DarkYellow
      Stop-Process -Id $pid -Force -ErrorAction Stop
    } catch {
      Write-Warning "No se pudo detener el proceso PID $pid en el puerto $Port: $($_.Exception.Message)"
    }
  }
}

Write-Host "Verificando puertos en uso..." -ForegroundColor Cyan
Stop-ListeningProcess -Port 8000
Stop-ListeningProcess -Port 2711

if ($InstallFrontend) {
  Write-Host "Instalando frontend (npm install)..." -ForegroundColor Cyan
  Push-Location $frontendDir
  try {
    npm install
  } finally {
    Pop-Location
  }
}

$backendPy = Join-Path $backendDir ".venv\Scripts\python.exe"
$backendCmd = if (Test-Path $backendPy) {
  "& '$backendPy' .\main.py"
} else {
  "py .\main.py"
}

$backendArgs = @(
  "-NoExit",
  "-Command",
  "cd '$backendDir'; $backendCmd"
)
$frontendArgs = @(
  "-NoExit",
  "-Command",
  "cd '$frontendDir'; npm run dev"
)

Write-Host "Iniciando backend en una ventana nueva..." -ForegroundColor Green
Start-Process powershell -ArgumentList $backendArgs | Out-Null

Start-Sleep -Seconds 2

Write-Host "Iniciando frontend en una ventana nueva..." -ForegroundColor Green
Start-Process powershell -ArgumentList $frontendArgs | Out-Null

Write-Host ""
Write-Host "Listo. Backend -> http://127.0.0.1:8000 | Frontend -> http://localhost:2711" -ForegroundColor Yellow
Write-Host "Ejecuta: .\run-all.ps1 -InstallFrontend  (si quieres reinstalar frontend antes de arrancar)"
