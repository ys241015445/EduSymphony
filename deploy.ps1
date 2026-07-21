# =============================================================================
# One-click full-stack deploy (Windows local)
#   backend + frontend + vmq (V-mian-qian) + vmq-db all via docker
#   Usage:  powershell -ExecutionPolicy Bypass -File .\deploy.ps1
#   (ASCII-only on purpose: Windows PowerShell mis-decodes non-ASCII .ps1)
# =============================================================================
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

function Test-Docker {
    try { docker info *> $null; return ($LASTEXITCODE -eq 0) } catch { return $false }
}

if (-not (Test-Docker)) {
    Write-Host "[deploy] Docker not running, launching Docker Desktop ..." -ForegroundColor Yellow
    $paths = @(
        (Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "Docker\Docker\Docker Desktop.exe")
    )
    $exe = $paths | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($exe) {
        Start-Process $exe
    } else {
        Write-Host "[deploy] Docker Desktop not found. Please start it manually, then re-run." -ForegroundColor Red
        exit 1
    }

    Write-Host "[deploy] Waiting for Docker engine (up to 180s) ..." -ForegroundColor Yellow
    $ok = $false
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Seconds 3
        if (Test-Docker) { $ok = $true; break }
    }
    if (-not $ok) {
        Write-Host "[deploy] Docker engine did not become ready. Make sure Docker Desktop is running." -ForegroundColor Red
        exit 1
    }
}

Write-Host "[deploy] Building and starting full stack (backend + frontend + vmq + vmq-db) ..." -ForegroundColor Cyan
docker compose up -d --build
if ($LASTEXITCODE -ne 0) {
    Write-Host "[deploy] docker compose failed" -ForegroundColor Red
    exit 1
}

Write-Host "[deploy] Waiting for services to become healthy ..." -ForegroundColor Yellow
Start-Sleep -Seconds 8
docker compose ps

Write-Host ""
Write-Host "================ DONE ================" -ForegroundColor Green
Write-Host " App frontend :  http://localhost:3002"
Write-Host " V-mian-qian  :  http://localhost:8080   (login: lzf / lzf122406!)"
Write-Host " Phone monitor app -> http://<your-LAN-IP>:8080   key: see setting.key in vmq/vmq.sql"
Write-Host "=====================================" -ForegroundColor Green
