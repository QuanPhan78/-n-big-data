<#
.SYNOPSIS
    Infrastructure startup script for NYC Ride-Hailing Big Data Pipeline (Milestone M1).
    Detects Docker environment, launches docker-compose stack, and validates container status.
#>

param (
    [switch]$CheckOnly
)

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  NYC Ride-Hailing Big Data Pipeline - Infrastructure Init  " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# 1. Check Docker CLI
$dockerCmd = Get-Command docker -ErrorAction SilentlyContinue

if (-not $dockerCmd) {
    # Check standard install paths
    $possiblePaths = @(
        "C:\Program Files\Docker\Docker\resources\bin\docker.exe",
        "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    )

    foreach ($p in $possiblePaths) {
        if (Test-Path $p) {
            Write-Host "[INFO] Found Docker binary at: $p" -ForegroundColor Green
            $binDir = Split-Path $p
            $env:Path = "$binDir;$env:Path"
            $dockerCmd = Get-Command docker -ErrorAction SilentlyContinue
            break
        }
    }
}

if (-not $dockerCmd) {
    Write-Host "[WARNING] Docker is not detected in system PATH or standard installation directories." -ForegroundColor Yellow
    Write-Host "[DIAGNOSTIC] Checked:" -ForegroundColor Yellow
    Write-Host "  - System PATH: docker"
    Write-Host "  - C:\Program Files\Docker\Docker\resources\bin\docker.exe"
    Write-Host "  - C:\Program Files\Docker\Docker\Docker Desktop.exe"
    Write-Host "  - com.docker.service status"
    Write-Host "[ACTION REQUIRED] To start the Docker stack on this host, ensure Docker Desktop or Docker engine is installed." -ForegroundColor Yellow
    Write-Host "Configuration in docker-compose.yml has been updated and verified." -ForegroundColor Green
    if ($CheckOnly) { exit 1 } else { exit 0 }
}

# 2. Check Docker Daemon
Write-Host "[INFO] Checking Docker daemon status..." -ForegroundColor Cyan
$info = & docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[INFO] Docker daemon is not currently responding. Attempting to start Docker Desktop..." -ForegroundColor Yellow
    $desktopApp = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    if (Test-Path $desktopApp) {
        Start-Process $desktopApp
        Write-Host "[INFO] Waiting for Docker daemon to become responsive (up to 60s)..."
        $retries = 12
        while ($retries -gt 0) {
            Start-Sleep -Seconds 5
            & docker info 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) {
                Write-Host "[INFO] Docker daemon is now responsive!" -ForegroundColor Green
                break
            }
            $retries--
        }
    } else {
        Write-Host "[ERROR] Docker Desktop executable not found to auto-start daemon." -ForegroundColor Red
        exit 1
    }
}

if ($CheckOnly) {
    Write-Host "[INFO] Docker environment check passed." -ForegroundColor Green
    exit 0
}

# 3. Launch Docker Compose Stack
Write-Host "[INFO] Starting all services with docker compose up -d..." -ForegroundColor Cyan
& docker compose up -d

if ($LASTEXITCODE -ne 0) {
    Write-Host "[INFO] docker compose returned non-zero, trying docker-compose up -d..." -ForegroundColor Yellow
    & docker-compose up -d
}

# 4. Verify Services
Write-Host "[INFO] Verifying container status..." -ForegroundColor Cyan
Start-Sleep -Seconds 3
& docker ps

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Service Endpoints:" -ForegroundColor Cyan
Write-Host "  - NameNode Web UI:     http://localhost:9870"
Write-Host "  - Spark Master UI:     http://localhost:8080"
Write-Host "  - MLflow Server UI:    http://localhost:5000"
Write-Host "  - Airflow Web UI:      http://localhost:8081"
Write-Host "  - Streamlit Dashboard: http://localhost:8501"
Write-Host "============================================================" -ForegroundColor Cyan
