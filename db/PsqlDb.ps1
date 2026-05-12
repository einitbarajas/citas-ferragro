# Funciones compartidas para scripts psql en esta carpeta (dot-source desde otros .ps1).
# No ejecutar este archivo directamente.

# Consola UTF-8 (Windows PowerShell 5.1: evita "ConexiÃ³n" en lugar de "Conexión").
if (-not (Get-Variable FerragroDbConsoleUtf8 -Scope Global -ErrorAction SilentlyContinue)) {
  $global:FerragroDbConsoleUtf8 = $true
  try {
    if ($env:OS -match 'Windows') {
      $null = cmd.exe /c "chcp 65001>nul 2>&1"
    }
    $utf8 = [System.Text.UTF8Encoding]::new($false)
    [Console]::OutputEncoding = $utf8
    $OutputEncoding = $utf8
  } catch { }
}

function Read-DatabaseUrlFromEnv {
  param([string] $Path)
  if (-not (Test-Path -LiteralPath $Path)) {
    throw "No se encontró el archivo .env: $Path"
  }
  foreach ($line in Get-Content -LiteralPath $Path -Encoding UTF8) {
    if ($line -match '^\s*DATABASE_URL\s*=\s*(.+)\s*$') {
      $v = $Matches[1].Trim().Trim([char]0x22).Trim("'")
      if (-not [string]::IsNullOrWhiteSpace($v)) { return $v }
    }
  }
  throw "DATABASE_URL no está definido en: $Path"
}

function Resolve-PsqlExecutable {
  $cmd = Get-Command psql -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }

  $roots = @(
    ${env:ProgramFiles},
    ${env:ProgramFiles(x86)}
  ) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }

  $candidates = @()
  foreach ($root in $roots) {
    $pg = Join-Path $root "PostgreSQL"
    if (-not (Test-Path -LiteralPath $pg)) { continue }
    foreach ($dir in Get-ChildItem -LiteralPath $pg -Directory -ErrorAction SilentlyContinue) {
      $exe = Join-Path $dir.FullName "bin\psql.exe"
      if (Test-Path -LiteralPath $exe) { $candidates += $exe }
    }
  }

  if ($candidates.Count -eq 0) {
    throw "psql no está en el PATH ni en Program Files\PostgreSQL\*\bin. Instala PostgreSQL o añade bin al PATH."
  }

  return (
    $candidates |
      Sort-Object {
        $leaf = Split-Path (Split-Path $_ -Parent) -Leaf
        $n = 0
        if ([int]::TryParse($leaf, [ref]$n)) { $n } else { -1 }
      } -Descending |
      Select-Object -First 1
  )
}

function Invoke-FerragroSqlFile {
  param(
    [Parameter(Mandatory)][string] $DatabaseUrl,
    [Parameter(Mandatory)][string] $PsqlExe,
    [Parameter(Mandatory)][string] $SqlPath,
    [string] $Label = ""
  )
  if (-not (Test-Path -LiteralPath $SqlPath)) {
    throw "Archivo SQL no encontrado: $SqlPath"
  }
  $name = if ($Label) { $Label } else { Split-Path $SqlPath -Leaf }
  Write-Host "  psql -> $name" -ForegroundColor Yellow
  & $PsqlExe $DatabaseUrl -v ON_ERROR_STOP=1 -f $SqlPath
  if ($LASTEXITCODE -ne 0) {
    throw "Error en psql (codigo de salida $LASTEXITCODE). Archivo: $SqlPath"
  }
}
